import sqlite3
import unicodedata
import logging
import sys
from pathlib import Path

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Determine the database path
DB_PATH = Path("data/processed/kombyphantike_v2.db")

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

def main():
    if not DB_PATH.exists():
        logger.error(f"Database file not found at {DB_PATH}")
        sys.exit(1)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lsj_entries'")
        if not cursor.fetchone():
            logger.error("Table 'lsj_entries' does not exist. Please run migration 2 first.")
            sys.exit(1)

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lemmas'")
        if not cursor.fetchone():
            logger.error("Table 'lemmas' does not exist. Please run migration 1b first.")
            sys.exit(1)

        logger.info("Loading LSJ Headwords...")
        cursor.execute("SELECT id, headword FROM lsj_entries")
        lsj_rows = cursor.fetchall()

        lsj_map = {}
        duplicates = 0
        for row in lsj_rows:
            lsj_id, headword = row
            if not headword:
                continue

            normalized = normalize_greek(headword)
            if normalized in lsj_map:
                duplicates += 1
                # Strategy: Keep the first one encountered (often lowest ID)
                continue

            lsj_map[normalized] = (lsj_id, headword)

        logger.info(f"Loaded {len(lsj_map)} unique normalized LSJ headwords. (Ignored {duplicates} duplicates)")

        logger.info("Loading Modern Lemmas (where lsj_id is NULL)...")
        cursor.execute("SELECT id, lemma_text FROM lemmas WHERE lsj_id IS NULL")
        lemma_rows = cursor.fetchall()

        updates = []
        linked_count = 0

        logger.info("Matching...")
        for row in lemma_rows:
            lemma_id, lemma_text = row
            if not lemma_text:
                continue

            normalized_lemma = normalize_greek(lemma_text)

            if normalized_lemma in lsj_map:
                lsj_id, ancient_headword = lsj_map[normalized_lemma]
                updates.append((lsj_id, lemma_id))
                linked_count += 1
                logger.info(f"Linked '{lemma_text}' to '{ancient_headword}' (ID: {lsj_id})")

        if updates:
            logger.info(f"Applying {len(updates)} updates to the database...")
            cursor.executemany("UPDATE lemmas SET lsj_id = ? WHERE id = ?", updates)
            conn.commit()
            logger.info("Database updated successfully.")
        else:
            logger.info("No new links found.")

        conn.close()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
