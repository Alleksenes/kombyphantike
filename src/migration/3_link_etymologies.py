import sqlite3
import json
import sys
import logging
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, desc=None):
        return iterable

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.beta_code import BetaCodeConverter
from src.config import PROCESSED_DIR

# Database Path
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def extract_ancient_word(etymology_json_str):
    """
    Parses etymology JSON to find the Ancient Greek source word.
    Supports both:
    1. User-specified format: [{'source': 'grc', 'word': '...'}]
    2. Standard Kaikki/Wiktionary template structure: {'args': {'1': 'el', '2': 'grc', '3': 'word'}, ...}
    """
    try:
        data = json.loads(etymology_json_str)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, list):
        return None

    for item in data:
        if not isinstance(item, dict):
            continue

        # Strategy 1: User specified format
        if item.get("source") == "grc" and item.get("word"):
            return item["word"]

        # Strategy 2: Kaikki template format
        # Check if 'grc' is in args
        args = item.get("args", {})
        if not args:
            continue

        # Values in args are strings. Keys are usually "1", "2", "3" etc.
        # We look for value == "grc" which indicates source language.
        is_ancient_source = False
        word_candidate = None

        for k, v in args.items():
            if v == "grc":
                is_ancient_source = True

        if is_ancient_source:
            # The word is usually in position 3 (if 'el' is 1 and 'grc' is 2)
            # Or just look for the first non-code argument
            word_candidate = args.get("3")
            if not word_candidate:
                # Fallback: look for other args that are not 'el' or 'grc'
                for k, v in args.items():
                    if v not in ["el", "grc"] and k not in ["1", "2"]:
                        word_candidate = v
                        break

        if is_ancient_source and word_candidate:
            return word_candidate

    return None

def link_etymologies():
    if not DB_PATH.exists():
        logging.error(f"Database not found at {DB_PATH}")
        return

    logging.info("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Add lsj_id column if not exists
    try:
        cursor.execute("ALTER TABLE lemmas ADD COLUMN lsj_id INTEGER REFERENCES lsj_entries(id)")
        logging.info("Added 'lsj_id' column to 'lemmas'.")
    except sqlite3.OperationalError:
        logging.info("'lsj_id' column already exists.")

    logging.info("Loading Beta Code Converter...")
    try:
        converter = BetaCodeConverter()
    except FileNotFoundError as e:
        logging.error(f"Failed to load BetaCodeConverter: {e}")
        conn.close()
        return

    logging.info("Fetching lemmas with etymology...")
    cursor.execute("SELECT id, etymology_json FROM lemmas WHERE etymology_json IS NOT NULL")
    rows = cursor.fetchall()

    total = len(rows)
    logging.info(f"Found {total} lemmas with etymology.")

    hit_count = 0
    updates = []

    for lemma_id, ety_json in tqdm(rows, desc="Linking Etymologies"):
        ancient_word = extract_ancient_word(ety_json)

        if not ancient_word:
            continue

        # Convert to Beta Code and Canonicalize
        beta = converter.to_beta_code(ancient_word)
        canonical = converter.canonicalize(beta)

        if not canonical:
            continue

        # Find in LSJ
        cursor.execute("SELECT id FROM lsj_entries WHERE canonical_key = ?", (canonical,))
        result = cursor.fetchone()

        if result:
            lsj_id = result[0]
            updates.append((lsj_id, lemma_id))
            hit_count += 1

        if len(updates) >= 1000:
            cursor.executemany("UPDATE lemmas SET lsj_id = ? WHERE id = ?", updates)
            conn.commit()
            updates = []

    if updates:
        cursor.executemany("UPDATE lemmas SET lsj_id = ? WHERE id = ?", updates)
        conn.commit()

    logging.info(f"Linked {hit_count} / {total} words.")
    conn.close()

if __name__ == "__main__":
    link_etymologies()
