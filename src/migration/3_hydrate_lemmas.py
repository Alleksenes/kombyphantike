import sqlite3
import pandas as pd
from tqdm import tqdm
import sys
from pathlib import Path
import logging

# Ensure src is in path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
CSV_PATH = PROCESSED_DIR / "kelly.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def hydrate_lemmas():
    if not CSV_PATH.exists():
        logging.error(f"CSV file not found at {CSV_PATH}")
        return

    logging.info(f"Loading data from {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create schema if it doesn't exist (including standard columns + new columns)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT NOT NULL UNIQUE,
            pos TEXT,
            ipa TEXT,
            etymology_json TEXT,
            modern_def TEXT,
            greek_def TEXT,
            shift_type TEXT,
            semantic_warning TEXT,
            frequency_score REAL
        )
    """
    )

    # Check for missing columns in existing table
    logging.info("Checking schema...")
    cursor.execute("PRAGMA table_info(lemmas)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    columns_to_add = {
        "modern_def": "TEXT",
        "greek_def": "TEXT",
        "shift_type": "TEXT",
        "semantic_warning": "TEXT",
        "frequency_score": "REAL"
    }

    for col_name, col_type in columns_to_add.items():
        if col_name not in existing_columns:
            logging.info(f"Adding column {col_name} ({col_type}) to lemmas table.")
            cursor.execute(f"ALTER TABLE lemmas ADD COLUMN {col_name} {col_type}")

    conn.commit()

    logging.info("Hydrating lemmas...")

    updates = 0
    inserts = 0
    records = df.to_dict('records')

    for row in tqdm(records, desc="Hydrating lemmas"):
        lemma_text = row.get("Lemma")
        if pd.isna(lemma_text):
            continue

        modern_def = row.get("Modern_Def")
        greek_def = row.get("Greek_Def")
        shift_type = row.get("Shift_Type")
        semantic_warning = row.get("Semantic_Warning")
        freq = row.get("Συχνότητα (Frequency)")

        # Handle NaNs
        modern_def = modern_def if not pd.isna(modern_def) else None
        greek_def = greek_def if not pd.isna(greek_def) else None
        shift_type = shift_type if not pd.isna(shift_type) else None
        semantic_warning = semantic_warning if not pd.isna(semantic_warning) else None

        try:
            frequency_score = float(freq) if not pd.isna(freq) else None
        except (ValueError, TypeError):
            frequency_score = None

        # Check if lemma exists
        cursor.execute("SELECT 1 FROM lemmas WHERE lemma_text = ?", (lemma_text,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute(
                """
                UPDATE lemmas
                SET modern_def = ?, greek_def = ?, shift_type = ?, semantic_warning = ?, frequency_score = ?
                WHERE lemma_text = ?
                """,
                (modern_def, greek_def, shift_type, semantic_warning, frequency_score, lemma_text)
            )
            updates += 1
        else:
            # Insert new lemma
            # We map "Μέρος του Λόγου (Part of speech)" to pos if available
            pos = row.get("Μέρος του Λόγου (Part of speech)")
            pos = pos if not pd.isna(pos) else None

            cursor.execute(
                """
                INSERT INTO lemmas (lemma_text, pos, modern_def, greek_def, shift_type, semantic_warning, frequency_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (lemma_text, pos, modern_def, greek_def, shift_type, semantic_warning, frequency_score)
            )
            inserts += 1

    conn.commit()
    conn.close()
    logging.info(f"Hydration complete. Updated {updates} lemmas. Inserted {inserts} lemmas.")

if __name__ == "__main__":
    hydrate_lemmas()
