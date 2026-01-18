import gspread
import pandas as pd
import logging, sys, os, json, traceback
from datetime import datetime
from dotenv import load_dotenv
from src.config import BASE_DIR, DATA_DIR

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("CloudSync")

# CONFIGURATION
WORKSHEET_PATH = DATA_DIR / "kombyphantike_worksheet.csv"
PROGRESS_FILE = DATA_DIR / "user_progress.json"
CREDENTIALS_FILE = "kombyphantike-google-key.json"

# Load Env
load_dotenv(dotenv_path=BASE_DIR / ".env")

SHEET_KEY = os.getenv("GOOGLE_SHEET_ID")
if not SHEET_KEY:
    logger.error("❌ GOOGLE_SHEET_ID not found in .env")
    sys.exit(1)

# *** THE TARGET TAB NAME ***
TARGET_TAB_NAME = "SENTENCES"


class CloudBridge:
    def __init__(self):
        self.gc = None
        self.sh = None
        self.worksheet = None
        self.connect()

    def connect(self):
        try:
            logger.info(f"Authenticating with local file: {CREDENTIALS_FILE}...")
            self.gc = gspread.service_account(filename=CREDENTIALS_FILE)

            # Open Sheet
            logger.info(f"Targeting Sheet Key: '{SHEET_KEY}'...")
            self.sh = self.gc.open_by_key(SHEET_KEY)

            logger.info(f"Connected to Document: {self.sh.title}")

            try:
                self.worksheet = self.sh.worksheet(TARGET_TAB_NAME)
                logger.info(f"✅ Locked onto tab: '{TARGET_TAB_NAME}'")
            except gspread.WorksheetNotFound:
                logger.error(f"❌ Tab '{TARGET_TAB_NAME}' NOT FOUND.")
                sys.exit(1)

        except Exception as e:
            logger.error(f"Connection failed.")
            logger.error(traceback.format_exc())
            sys.exit(1)

    def push_local_to_cloud(self):
        logger.info("--- STARTING PUSH (LOCAL -> CLOUD) ---")

        if not WORKSHEET_PATH.exists():
            logger.error("Local worksheet not found.")
            return

        try:
            # Robust CSV Reading with Error Reporting
            df = pd.read_csv(
                WORKSHEET_PATH, engine="python", on_bad_lines="error", quotechar='"'
            ).fillna("")
        except Exception as e:
            logger.error("❌ CSV PARSING ERROR: Likely unquoted commas.")
            logger.error(f"Details: {e}")
            logger.info(
                '👉 ACTION: Open the CSV. Wrap sentences with commas in "double quotes".'
            )
            return

        target_col = "Greek Translation / Target Sentence"

        if target_col not in df.columns:
            logger.error(f"Column '{target_col}' missing.")
            return

        # Filter completed rows (length > 1)
        completed = df[df[target_col].astype(str).str.strip().str.len() > 1]

        if completed.empty:
            logger.warning("No completed sentences to upload.")
            return

        logger.info(f"Uploading {len(completed)} rows to '{TARGET_TAB_NAME}'...")

        try:
            # append_rows automatically finds the first empty row at the bottom
            self.worksheet.append_rows(
                completed.values.tolist(), value_input_option="USER_ENTERED"
            )
            logger.info("✅ Push Complete. Rows appended to bottom.")
        except Exception as e:
            logger.error(f"Upload failed: {e}")

    def pull_stats_from_cloud(self):
        logger.info(f"--- STARTING PULL (CLOUD -> LOCAL STATS) ---")

        try:
            raw_data = self.worksheet.get_all_records()
        except Exception as e:
            logger.error(f"Failed to download data: {e}")
            return

        df = pd.DataFrame(raw_data)
        if df.empty:
            logger.warning("Cloud sheet is empty.")
            return

        logger.info(f"Downloaded {len(df)} rows of history.")

        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress = json.load(f)
        else:
            progress = {"words": {}, "knots": {}}

        # Ensure structure
        if "words" not in progress:
            progress["words"] = {}
        if "knots" not in progress:
            progress["knots"] = {}

        # 1. WORD STATS
        vocab_cols = [
            "Core Vocab (Verb)",
            "Core Vocab (Adjective)",
            "Optional Core Vocab (Praepositio)",
            "Optional Core Vocab (Adverb)",
        ]
        available_cols = [c for c in vocab_cols if c in df.columns]

        cloud_word_counts = {}
        for _, row in df.iterrows():
            for col in available_cols:
                word = str(row[col]).replace("*", "").strip()
                if word:
                    cloud_word_counts[word] = cloud_word_counts.get(word, 0) + 1

        updates_w = 0
        for word, count in cloud_word_counts.items():
            if word not in progress["words"]:
                progress["words"][word] = {"count": 0, "last_used": ""}

            if count > progress["words"][word]["count"]:
                progress["words"][word]["count"] = count
                updates_w += 1

        # 2. KNOT STATS (New Feature)
        cloud_knot_counts = {}
        if "Knot ID" in df.columns:
            for kid in df["Knot ID"]:
                kid = str(kid).strip()
                if kid:
                    cloud_knot_counts[kid] = cloud_knot_counts.get(kid, 0) + 1

        updates_k = 0
        for kid, count in cloud_knot_counts.items():
            if kid not in progress["knots"]:
                progress["knots"][kid] = {"count": 0, "last_used": ""}

            if count > progress["knots"][kid]["count"]:
                progress["knots"][kid]["count"] = count
                updates_k += 1

        # Save
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        logger.info(
            f"✅ Sync Complete. Updated {updates_w} words and {updates_k} knots."
        )


if __name__ == "__main__":
    bridge = CloudBridge()

    print("1. Push (Local -> Cloud)")
    print("2. Pull (Cloud -> Local Stats)")
    choice = input("Choose (1/2): ")

    if choice == "1":
        bridge.push_local_to_cloud()
    elif choice == "2":
        bridge.pull_stats_from_cloud()
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)
