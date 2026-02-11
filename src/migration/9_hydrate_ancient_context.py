import sqlite3
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
BATCH_SIZE = 5000

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def clean_definition(text):
    if not text:
        return ""
    return text.strip()

def run_migration():
    if not DB_PATH.exists():
        logging.error(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check for lsj_entries table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lsj_entries'")
    if not cursor.fetchone():
        logging.error("Table 'lsj_entries' does not exist. Please run migration 2 first.")
        conn.close()
        return

    # Ensure etymology_text column exists
    try:
        cursor.execute("ALTER TABLE lemmas ADD COLUMN etymology_text TEXT")
        logging.info("Added column: etymology_text")
    except sqlite3.OperationalError:
        pass # Column likely exists

    logging.info("Fetching lemmas with LSJ links...")

    query = """
        SELECT l.id, l.lsj_id, l.etymology_text, l.etymology_json, j.entry_json
        FROM lemmas l
        JOIN lsj_entries j ON l.lsj_id = j.id
        WHERE l.lsj_id IS NOT NULL
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    logging.info(f"Processing {len(rows)} linked lemmas...")

    updates = []

    for row_idx, row in enumerate(rows):
        lemma_id, lsj_id, current_etym_text, current_etym_json, entry_json_str = row

        try:
            entry = json.loads(entry_json_str)
        except json.JSONDecodeError:
            logging.warning(f"Invalid JSON in lsj_entries for ID {lsj_id}")
            continue

        senses = entry.get("senses", [])
        definitions = []

        idx = 1
        for sense in senses:
            def_text = clean_definition(sense.get("definition", ""))
            if not def_text:
                continue

            citations = sense.get("citations", [])
            authors = set()
            for cit in citations:
                author = cit.get("author")
                if author:
                    authors.add(author)

            sorted_authors = sorted(list(authors))
            author_str = f" ({', '.join(sorted_authors)})" if sorted_authors else ""

            definitions.append(f"{idx}. {def_text}{author_str}")
            idx += 1

        final_text = "; ".join(definitions)

        # Determine etymology_json value
        new_etym_json = current_etym_json

        # Check if current_etym_json is effectively empty
        is_empty = False
        if not current_etym_json:
            is_empty = True
        else:
            try:
                parsed = json.loads(current_etym_json)
                if not parsed: # Empty list or dict
                    is_empty = True
            except json.JSONDecodeError:
                is_empty = True # Treat invalid JSON as empty/overwriteable

        if is_empty and final_text:
            new_etym_json = json.dumps([{"role": "Ancient", "definition": final_text}], ensure_ascii=False)

        if final_text:
            updates.append((final_text, new_etym_json, lemma_id))

        if (row_idx + 1) % BATCH_SIZE == 0:
            logging.info(f"Processed {row_idx + 1} rows...")

    if updates:
        logging.info(f"Applying {len(updates)} updates...")
        cursor.executemany(
            "UPDATE lemmas SET etymology_text = ?, etymology_json = ? WHERE id = ?",
            updates
        )
        conn.commit()
        logging.info("Update complete.")
    else:
        logging.info("No updates needed.")

    conn.close()

if __name__ == "__main__":
    run_migration()
