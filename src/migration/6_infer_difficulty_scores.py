import sqlite3
import pandas as pd
from tqdm import tqdm
import sys
from pathlib import Path
import logging
import math

# Ensure src is in path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
CSV_PATH = PROCESSED_DIR / "kelly.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def calculate_kds(lemma_text, frequency_score, cefr_level):
    """
    Calculates the Kombyphantike Difficulty Score (KDS).

    Algorithm:
    1. Base Score: 50.
    2. Kelly Bonus (if CEFR level exists):
       - A1: 10
       - A2: 20
       - B1: 30
       - B2: 40
       - C1: 50
       - C2: 60
    3. Frequency Fallback (if no CEFR level):
       - frequency_score > 500: 30 (Common)
       - frequency_score < 5 (or None): 80 (Rare)
       - Else: Keep Base (50)
    4. Length Penalty:
       - Add len(word) / 2
    5. Clamp:
       - Ensure score is between 1 and 100.
    """
    score = 50.0  # Base Score

    # Normalize CEFR level (handle NaN/None/whitespace)
    if isinstance(cefr_level, str):
        cefr_level = cefr_level.strip().upper()
    else:
        cefr_level = None

    # Kelly Bonus
    if cefr_level in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
        if cefr_level == 'A1': score = 10.0
        elif cefr_level == 'A2': score = 20.0
        elif cefr_level == 'B1': score = 30.0
        elif cefr_level == 'B2': score = 40.0
        elif cefr_level == 'C1': score = 50.0
        elif cefr_level == 'C2': score = 60.0
    else:
        # Frequency Fallback
        # If frequency_score is None, treat as 0 (Rare)
        freq = frequency_score if frequency_score is not None else 0
        if freq > 500:
            score = 30.0
        elif freq < 5:
            score = 80.0
        # Else keep base 50

    # Length Penalty
    if lemma_text:
        score += len(lemma_text) / 2.0

    # Clamp and Round
    final_score = int(round(score))
    return max(1, min(100, final_score))

def infer_difficulty_scores():
    if not CSV_PATH.exists():
        logging.error(f"Kelly CSV not found at {CSV_PATH}")
        # Proceeding without Kelly map means all fallback logic
        kelly_map = {}
    else:
        logging.info(f"Loading Kelly data from {CSV_PATH}...")
        try:
            df = pd.read_csv(CSV_PATH)
            # Identify Lemma column
            lemma_col = 'Lemma' if 'Lemma' in df.columns else 'Λημμα (Lemma)'
            if lemma_col not in df.columns:
                logging.warning(f"Could not find Lemma column in {CSV_PATH}. Columns: {df.columns}")
                kelly_map = {}
            else:
                # Create map: Lemma -> CEFR Level
                # Drop duplicates, keeping first? Or handle duplicates?
                # We'll just take the last valid one if duplicates exist, or drop_duplicates
                df_clean = df.dropna(subset=[lemma_col])
                kelly_map = df_clean.set_index(lemma_col)['CEF level'].to_dict()
        except Exception as e:
            logging.error(f"Failed to read CSV: {e}")
            kelly_map = {}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Add column if not exists
    logging.info("Checking schema...")
    cursor.execute("PRAGMA table_info(lemmas)")
    columns = {row[1] for row in cursor.fetchall()}

    if "kds_score" not in columns:
        logging.info("Adding column kds_score (INTEGER) to lemmas table.")
        cursor.execute("ALTER TABLE lemmas ADD COLUMN kds_score INTEGER")
    else:
        logging.info("Column kds_score already exists.")

    # 2. Fetch all lemmas
    logging.info("Fetching lemmas...")
    cursor.execute("SELECT id, lemma_text, frequency_score FROM lemmas")
    rows = cursor.fetchall()

    logging.info(f"Found {len(rows)} lemmas. calculating scores...")

    updates = []

    for row in tqdm(rows, desc="Calculating KDS"):
        lemma_id = row[0]
        lemma_text = row[1]
        frequency_score = row[2]

        cefr_level = kelly_map.get(lemma_text)

        score = calculate_kds(lemma_text, frequency_score, cefr_level)
        updates.append((score, lemma_id))

    # 3. Update in bulk
    logging.info("Updating database...")
    cursor.executemany("UPDATE lemmas SET kds_score = ? WHERE id = ?", updates)

    conn.commit()
    conn.close()
    logging.info(f"Done. Updated {len(updates)} lemmas.")

if __name__ == "__main__":
    infer_difficulty_scores()
