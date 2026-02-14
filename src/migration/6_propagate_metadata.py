import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

# Default DB Path
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def propagate_metadata(db_path=DB_PATH):
    """
    Backfills child forms with metadata from their parent lemmas.
    Fields propagated: greek_def, modern_def, english_def, etymology_json, lsj_id, shift_type.
    Condition: Child definition is NULL/Empty OR is a morphological description (e.g., contains ' του ', ' της ').
    Uses SQLite UPDATE ... FROM syntax for efficiency.
    """
    if not db_path.exists():
        logging.error(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verify tables exist
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='lemmas'"
    )
    if not cursor.fetchone():
        logging.error("Table 'lemmas' not found. Skipping migration.")
        conn.close()
        return

    logging.info(f"Propagating metadata in {db_path}...")

    # The SQL Update Logic using UPDATE ... FROM syntax
    # We join lemmas (as child) with relations and lemmas (as parent)
    # We filter for 'form_of' relations and check if greek_def is empty or morphological description
    # We propagate all relevant metadata fields to avoid regression
    query = """
    UPDATE lemmas
    SET
        greek_def = parent.greek_def,
        modern_def = parent.modern_def,
        english_def = parent.english_def,
        etymology_json = parent.etymology_json,
        lsj_id = parent.lsj_id,
        shift_type = parent.shift_type
    FROM relations AS r
    JOIN lemmas AS parent ON r.parent_lemma_text = parent.lemma_text
    WHERE lemmas.id = r.child_lemma_id
      AND r.relation_type = 'form_of'
      AND (
           lemmas.greek_def IS NULL
        OR lemmas.greek_def = ''
        OR lemmas.greek_def LIKE '% του %'
        OR lemmas.greek_def LIKE '% της %'
      );
    """

    try:
        cursor.execute(query)
        # rowcount in SQLite for UPDATE returns the number of modified rows
        updates_count = cursor.rowcount
        conn.commit()
        logging.info(f"Propagation complete. Updated {updates_count} child lemmas.")
    except sqlite3.OperationalError as e:
        logging.error(f"Query failed: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    propagate_metadata()
