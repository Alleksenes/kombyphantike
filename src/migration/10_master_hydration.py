import sqlite3
import json
import re
import unicodedata
import logging
import sys
from pathlib import Path
from transliterate import translit

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- REGEX PATTERNS ---
# Abbreviations to strip
ABBREV_PATTERN = re.compile(
    r'\b(?:freq\.|abs\.|acc\.|opp\.|e\.g\.|i\.e\.|etc\.|al\.|ib\.|Id\.|v\.|Skt\.|Lat\.|q\.v\.|Comp\.|Adv\.|Gramm\.|Astrol\.|Medic\.|Rhet\.)',
    re.IGNORECASE
)

# Citations: e.g., "Pi. P. 4.102", "Hdt. 1.51", "S. OT 1430"
# Pattern: Capitalized Author (maybe abbreviated) + Work (maybe abbreviated) + Numbers
CITATION_PATTERN = re.compile(r'\b[A-Z][a-z]*\.?\s+(?:[A-Z][A-Za-z]*\.?\s+)*\d+(?:\.\d+)*')

# Line numbers: e.g., "15.267"
LINE_NUMBER_PATTERN = re.compile(r'\b\d+\.\d+\b')


def normalize_greek(text: str) -> str:
    """
    Normalizes a Greek string by:
    1. Converting to NFD form.
    2. Stripping non-spacing marks (diacritics).
    3. Lowercasing the result.
    """
    if not text:
        return ""

    # Normalize to NFD form
    normalized = unicodedata.normalize('NFD', text)

    # Filter out non-spacing marks
    stripped = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')

    # Normalize back to NFC (optional, but good for consistency)
    final = unicodedata.normalize('NFC', stripped)

    return final.lower()


def clean_definition(text: str) -> str:
    """
    Applies the Cleaning Protocol to a definition string.
    """
    if not text:
        return ""

    # 1. Strip Abbreviations
    text = ABBREV_PATTERN.sub('', text)

    # 2. Strip Citations
    text = CITATION_PATTERN.sub('', text)

    # 3. Strip Line Numbers
    text = LINE_NUMBER_PATTERN.sub('', text)

    # 4. Clean Whitespace & Punctuation
    # Replace newlines/multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading/trailing punctuation and whitespace
    text = text.strip(" .,;:")

    return text


def get_golden_paraphrase(senses: list) -> str:
    """
    Combines the top 2-3 cleaned definitions into a single string.
    """
    definitions = []
    count = 0
    for sense in senses:
        raw_def = sense.get("definition", "")
        cleaned = clean_definition(raw_def)
        if cleaned:
            definitions.append(cleaned)
            count += 1
            if count >= 3: # Limit to top 3
                break

    return "; ".join(definitions)


def run_migration(db_path=DB_PATH):
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # --- 1. KDS INHERITANCE ---
        logger.info("--- Step 1: KDS Inheritance ---")
        # Ensure kds_score exists (it should from migration 6, but check anyway)
        cursor.execute("PRAGMA table_info(lemmas)")
        columns = {row[1] for row in cursor.fetchall()}
        if "kds_score" not in columns:
            logger.warning("Column 'kds_score' missing. Adding it (default 50).")
            cursor.execute("ALTER TABLE lemmas ADD COLUMN kds_score INTEGER DEFAULT 50")

        # Logic: Inherit from parent if child score is worse (higher)
        query_kds = """
            SELECT child.id, parent.kds_score
            FROM relations r
            JOIN lemmas child ON r.child_lemma_id = child.id
            JOIN lemmas parent ON r.parent_lemma_text = parent.lemma_text
            WHERE r.relation_type = 'form_of'
              AND child.kds_score > parent.kds_score
        """
        cursor.execute(query_kds)
        kds_updates = cursor.fetchall()

        if kds_updates:
            logger.info(f"Applying {len(kds_updates)} KDS inheritance updates...")
            cursor.executemany("UPDATE lemmas SET kds_score = ? WHERE id = ?", [(s, i) for i, s in kds_updates])
            conn.commit()
        else:
            logger.info("No KDS inheritance updates needed.")


        # --- 2. FUZZY LINKING ---
        logger.info("--- Step 2: Fuzzy Linking ---")
        # Load LSJ Headwords
        cursor.execute("SELECT id, headword FROM lsj_entries")
        lsj_rows = cursor.fetchall()
        lsj_map = {}
        for lid, headword in lsj_rows:
            if headword:
                norm = normalize_greek(headword)
                if norm not in lsj_map: # Keep first encountered
                    lsj_map[norm] = lid

        # Find unlinked lemmas
        cursor.execute("SELECT id, lemma_text FROM lemmas WHERE lsj_id IS NULL")
        unlinked_rows = cursor.fetchall()

        link_updates = []
        for lid, text in unlinked_rows:
            if text:
                norm = normalize_greek(text)
                if norm in lsj_map:
                    link_updates.append((lsj_map[norm], lid))

        if link_updates:
            logger.info(f"Linking {len(link_updates)} lemmas to LSJ entries...")
            cursor.executemany("UPDATE lemmas SET lsj_id = ? WHERE id = ?", link_updates)
            conn.commit()
        else:
            logger.info("No new fuzzy links found.")


        # --- 3. LSJ EXCAVATION & CLEANING ---
        logger.info("--- Step 3: LSJ Excavation ---")
        # Ensure etymology_text exists
        if "etymology_text" not in columns:
             cursor.execute("ALTER TABLE lemmas ADD COLUMN etymology_text TEXT")

        cursor.execute("""
            SELECT l.id, j.entry_json
            FROM lemmas l
            JOIN lsj_entries j ON l.lsj_id = j.id
            WHERE l.lsj_id IS NOT NULL
        """)
        excavation_rows = cursor.fetchall()

        excavation_updates = []
        for lid, entry_json_str in excavation_rows:
            try:
                entry = json.loads(entry_json_str)
                senses = entry.get("senses", [])
                golden_text = get_golden_paraphrase(senses)
                if golden_text:
                    excavation_updates.append((golden_text, lid))
            except json.JSONDecodeError:
                continue

        if excavation_updates:
            logger.info(f"Updating etymology_text for {len(excavation_updates)} lemmas...")
            cursor.executemany("UPDATE lemmas SET etymology_text = ? WHERE id = ?", excavation_updates)
            conn.commit()
        else:
            logger.info("No excavation updates needed.")


        # --- 4. TRANSLITERATION ---
        logger.info("--- Step 4: Transliteration ---")
        # Add column if missing
        if "transliteration" not in columns:
            logger.info("Adding 'transliteration' column...")
            cursor.execute("ALTER TABLE lemmas ADD COLUMN transliteration TEXT")
            conn.commit() # Commit schema change

        # Select all lemmas (or just those needing update? Prompt implies "For every row")
        # We can optimize by selecting where transliteration is NULL, but "For every row" ensures consistency.
        # Let's target NULLs first for efficiency, but maybe run for all to fix bad ones?
        # "Add a new column... For every row... generate... Store it" implies population.
        # I'll update all to be safe, or check if it's already done.
        # Let's update all where transliteration IS NULL to save time on re-runs.

        cursor.execute("SELECT id, lemma_text FROM lemmas WHERE transliteration IS NULL")
        translit_rows = cursor.fetchall()

        translit_updates = []
        for lid, text in translit_rows:
            if text:
                try:
                    t_text = translit(text, 'el', reversed=True)
                    translit_updates.append((t_text, lid))
                except Exception:
                    # Fallback or skip if transliteration fails
                    continue

        if translit_updates:
            logger.info(f"Transliterating {len(translit_updates)} lemmas...")
            cursor.executemany("UPDATE lemmas SET transliteration = ? WHERE id = ?", translit_updates)
            conn.commit()
        else:
            logger.info("No transliteration updates needed.")

        logger.info("Master Hydration Complete.")

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
