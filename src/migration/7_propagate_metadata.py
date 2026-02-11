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
    Fields propagated: greek_def, english_def, etymology_json, lsj_id, shift_type.
    Condition: Child field is NULL/Empty AND Parent field is NOT NULL/NotEmpty.
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

    # We select all potential candidates.
    # Logic: Join Child -> Relations -> Parent
    query = """
    SELECT
        child.id,
        child.greek_def, child.english_def, child.etymology_json, child.lsj_id, child.shift_type,
        parent.greek_def, parent.english_def, parent.etymology_json, parent.lsj_id, parent.shift_type
    FROM lemmas AS child
    JOIN relations AS rel ON child.id = rel.child_lemma_id
    JOIN lemmas AS parent ON rel.parent_lemma_text = parent.lemma_text
    WHERE rel.relation_type = 'form_of'
    """

    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        logging.error(f"Query failed: {e}")
        conn.close()
        return

    updates_count = 0

    for row in rows:
        (
            c_id,
            c_greek,
            c_eng,
            c_etym,
            c_lsj,
            c_shift,
            p_greek,
            p_eng,
            p_etym,
            p_lsj,
            p_shift,
        ) = row

        # Calculate new values
        # Only update if child is missing (None or empty string) AND parent has value

        new_greek = p_greek if (not c_greek) and p_greek else c_greek
        new_eng = p_eng if (not c_eng) and p_eng else c_eng
        new_etym = p_etym if (not c_etym) and p_etym else c_etym
        # For LSJ ID (Integer), 0 is theoretically possible but usually IDs start at 1.
        # Safest is 'is None'.
        new_lsj = p_lsj if (c_lsj is None) and (p_lsj is not None) else c_lsj
        new_shift = p_shift if (not c_shift) and p_shift else c_shift

        # Check if any change is needed
        if (
            new_greek != c_greek
            or new_eng != c_eng
            or new_etym != c_etym
            or new_lsj != c_lsj
            or new_shift != c_shift
        ):
            cursor.execute(
                """
                UPDATE lemmas
                SET greek_def = ?, english_def = ?, etymology_json = ?, lsj_id = ?, shift_type = ?
                WHERE id = ?
            """,
                (new_greek, new_eng, new_etym, new_lsj, new_shift, c_id),
            )
            updates_count += 1

    conn.commit()
    conn.close()
    logging.info(f"Propagation complete. Updated {updates_count} child lemmas.")


if __name__ == "__main__":
    propagate_metadata()
