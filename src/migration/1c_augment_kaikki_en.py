import sqlite3
import json
import logging
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import KAIKKI_EN_FILE, PROCESSED_DIR

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
BATCH_SIZE = 5000

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def ensure_columns(cursor):
    """Ensures english_def and etymology_text columns exist."""
    # Check for english_def
    try:
        cursor.execute("ALTER TABLE lemmas ADD COLUMN english_def TEXT")
        logging.info("Added column: english_def")
    except sqlite3.OperationalError:
        pass # Column likely exists

    # Check for etymology_text
    try:
        cursor.execute("ALTER TABLE lemmas ADD COLUMN etymology_text TEXT")
        logging.info("Added column: etymology_text")
    except sqlite3.OperationalError:
        pass # Column likely exists

def run_migration(db_path=DB_PATH, jsonl_path=KAIKKI_EN_FILE):
    """
    Augments the database with English definitions and etymology text from Kaikki EN dump.
    """
    if not jsonl_path.exists():
        logging.error(f"File not found: {jsonl_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure schema is updated
    ensure_columns(cursor)
    conn.commit()

    logging.info("Counting lines...")
    try:
        total_lines = sum(1 for _ in open(jsonl_path, "r", encoding="utf-8"))
    except FileNotFoundError:
        logging.error(f"File not found during counting: {jsonl_path}")
        return

    logging.info(f"Augmenting database from {jsonl_path}...")
    count = 0
    updated_defs = 0
    updated_etyms = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in tqdm(f, total=total_lines, desc="Processing Kaikki EN"):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filter for Greek
            if entry.get("lang_code") != "el":
                continue

            word = entry.get("word")
            if not word:
                continue

            # Extract English Definition
            english_defs = []
            for sense in entry.get("senses", []):
                if "glosses" in sense:
                    english_defs.extend(sense["glosses"])

            english_def_str = " | ".join(english_defs) if english_defs else None

            # Extract Etymology Text
            # Kaikki sometimes puts etymology text in 'etymology_text' field
            etymology_text = entry.get("etymology_text")

            # Update DB - Definitions
            if english_def_str:
                cursor.execute(
                    """
                    UPDATE lemmas
                    SET english_def = ?
                    WHERE lemma_text = ?
                      AND (english_def IS NULL OR english_def = '')
                    """,
                    (english_def_str, word)
                )
                if cursor.rowcount > 0:
                    updated_defs += cursor.rowcount

            # Update DB - Etymologies (Bonus)
            if etymology_text:
                cursor.execute(
                    """
                    UPDATE lemmas
                    SET etymology_text = ?
                    WHERE lemma_text = ?
                      AND (etymology_text IS NULL OR etymology_text = '')
                    """,
                    (etymology_text, word)
                )
                if cursor.rowcount > 0:
                    updated_etyms += cursor.rowcount

            count += 1
            if count % BATCH_SIZE == 0:
                conn.commit()

    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    logging.info(f"Augmentation Complete. Updated {updated_defs} definitions and {updated_etyms} etymologies.")

if __name__ == "__main__":
    run_migration()
