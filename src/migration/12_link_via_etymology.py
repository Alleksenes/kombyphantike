import sqlite3
import re
import unicodedata
import json
import logging
import sys
from pathlib import Path

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
# Matches: "αρχαία ελληνική word", "αρχ. ελλ. word", "grc word"
# Capturing groups: 1=Prefix, 2=Word
ETYMOLOGY_PATTERN = re.compile(
    r'(αρχαία ελληνική|αρχ\. ελλ\.|grc)\s+([^\s,]+)',
    re.IGNORECASE
)

def normalize_greek(text: str) -> str:
    """
    Normalizes a Greek string by:
    1. Converting to NFD form.
    2. Stripping non-spacing marks (diacritics).
    3. Lowercasing the result.
    4. Stripping trailing punctuation.
    """
    if not text:
        return ""

    # Normalize to NFD form
    normalized = unicodedata.normalize('NFD', text)

    # Filter out non-spacing marks
    stripped = "".join(c for c in normalized if unicodedata.category(c) != 'Mn')

    # Normalize back to NFC (optional)
    final = unicodedata.normalize('NFC', stripped)

    # Lowercase and strip punctuation
    return final.lower().strip(".,;:")

def extract_ancient_word(text: str) -> str | None:
    """
    Applies regex to extract the Ancient Greek word.
    """
    if not text:
        return None

    match = ETYMOLOGY_PATTERN.search(text)
    if match:
        return match.group(2)
    return None

def extract_from_json(json_str: str) -> str | None:
    """
    Parses etymology_json to find an Ancient Greek (grc) source word.
    Expects a list of templates like:
    {'name': 'inh', 'args': {'1': 'el', '2': 'grc', '3': 'word'}}
    """
    if not json_str:
        return None

    try:
        templates = json.loads(json_str)
        if not isinstance(templates, list):
            return None

        for template in templates:
            args = template.get("args", {})
            # Check for 'grc' in values
            found_grc = False
            word_candidate = None

            # Common patterns:
            # 2=grc, 3=word (most common for inh/der)
            # lang=grc, word=word

            # Check positional args
            if args.get("2") == "grc":
                word_candidate = args.get("3")

            # Check named args if positional didn't work
            if not word_candidate:
                # heuristic: if any value is 'grc', look for 'word' or 'term' or next position
                for k, v in args.items():
                    if v == "grc":
                        found_grc = True
                        break

                if found_grc:
                    word_candidate = args.get("word") or args.get("term") or args.get("3")

            if word_candidate:
                return word_candidate

    except json.JSONDecodeError:
        return None

    return None


def run_migration(db_path=DB_PATH):
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        logger.info("--- Step 1: Loading LSJ Map ---")
        # Ensure lsj_entries table exists to avoid crash on partial DB
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lsj_entries'")
        if not cursor.fetchone():
            logger.error("Table 'lsj_entries' does not exist. Cannot link.")
            return

        cursor.execute("SELECT id, headword FROM lsj_entries")
        lsj_rows = cursor.fetchall()

        lsj_map = {}
        for lid, headword in lsj_rows:
            if headword:
                norm = normalize_greek(headword)
                if norm and norm not in lsj_map:
                    lsj_map[norm] = lid

        logger.info(f"Loaded {len(lsj_map)} LSJ entries.")

        logger.info("--- Step 2: Finding Links ---")
        # Ensure lemmas table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lemmas'")
        if not cursor.fetchone():
            logger.error("Table 'lemmas' does not exist.")
            return

        # Select candidates
        cursor.execute("""
            SELECT id, lemma_text, etymology_text, etymology_json
            FROM lemmas
            WHERE lsj_id IS NULL
        """)
        candidates = cursor.fetchall()

        updates = []

        for lid, lemma_text, etym_text, etym_json in candidates:
            # Try 1: Regex on text
            ancient_word = extract_ancient_word(etym_text)

            # Try 2: Parse JSON
            if not ancient_word:
                ancient_word = extract_from_json(etym_json)

            if ancient_word:
                norm_word = normalize_greek(ancient_word)
                if norm_word in lsj_map:
                    updates.append((lsj_map[norm_word], lid))

        if updates:
            logger.info(f"Linking {len(updates)} lemmas to LSJ entries via etymology...")
            cursor.executemany("UPDATE lemmas SET lsj_id = ? WHERE id = ?", updates)
            conn.commit()
        else:
            logger.info("No new etymological links found.")

        logger.info("Migration 12 Complete.")

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
