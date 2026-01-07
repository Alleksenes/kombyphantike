from pathlib import Path

# Define the Project Root
BASE_DIR = Path(__file__).resolve().parent.parent

# Data Paths
DATA_DIR = BASE_DIR / "data"
DICT_DIR = DATA_DIR / "dictionaries"
PROCESSED_DIR = DATA_DIR / "processed"
SESSIONS_DIR = DATA_DIR / "sessions"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

# 1. The Raw Input (Excel File in dictionaries folder)
KELLY_FILE = DICT_DIR / "KELLY_EL.xlsx"

# 2. The Master Output
OUTPUT_FILE = PROCESSED_DIR / "kelly.csv"

# 3. Dictionaries
KAIKKI_FILE = DICT_DIR / "kaikki.org-dictionary-Greek.jsonl"
LSJ_INDEX_FILE = DICT_DIR / "lsj_index.json"

# 4. Drills & Knots
DRILLS_FILE = PROCESSED_DIR / "modern_drills.csv"
KNOTS_PATH = DICT_DIR / "knots.csv"

# Column Mapping
COL_LEMMA = "Λημμα (Lemma)"
