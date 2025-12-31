import gspread
import pandas as pd
import logging, sys, os, json, traceback
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

# CONFIGURATION
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
            logger.info(f"Authenticating with {CREDENTIALS_FILE}...")
            self.gc = gspread.service_account(filename=CREDENTIALS_FILE)

            logger.info(f"Targeting Sheet Key: '{SHEET_KEY}'...")
            self.sh = self.gc.open_by_key(SHEET_KEY)

            logger.info(f"Connected to Document: {self.sh.title}")

            # Target the specific tab "SENTENCES"
            try:
                self.worksheet = self.sh.worksheet(TARGET_TAB_NAME)
                logger.info(f"✅ Locked onto tab: '{TARGET_TAB_NAME}'")
            except gspread.WorksheetNotFound:
                logger.error(f"❌ Tab '{TARGET_TAB_NAME}' NOT FOUND in this sheet.")
                logger.info(
                    f"Available tabs: {[s.title for s in self.sh.worksheets()]}"
                )
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
            # Robust CSV Reading
            df = pd.read_csv(
                WORKSHEET_PATH,
                engine="python",
                on_bad_lines="warn",  # Skip bad lines, don't crash
            ).fillna("")
        except Exception as e:
            logger.error(f"Critical CSV Error: {e}")
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
        logger.info(f"--- STARTING PULL (CLOUD '{TARGET_TAB_NAME}' -> LOCAL STATS) ---")

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
            progress = {}

        # Define columns that contain vocabulary
        vocab_cols = [
            "Core Vocab (Verb)",
            "Core Vocab (Adjective)",
            "Optional Core Vocab (Praepositio)",
            "Optional Core Vocab (Adverb)",
        ]

        available_cols = [c for c in vocab_cols if c in df.columns]

        # Calculate totals from Cloud
        cloud_counts = {}
        for _, row in df.iterrows():
            for col in available_cols:
                word = str(row[col]).replace("*", "").strip()
                if word:
                    cloud_counts[word] = cloud_counts.get(word, 0) + 1

        updates = 0
        for word, count in cloud_counts.items():
            if word not in progress:
                progress[word] = {
                    "count": 0,
                    "last_used": datetime.now().strftime("%Y-%m-%d"),
                }

            # Sync count (Cloud is Master)
            if count > progress[word]["count"]:
                progress[word]["count"] = count
                updates += 1

        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Sync Complete. Updated stats for {updates} words.")


if __name__ == "__main__":
    bridge = CloudBridge()

    print("1. Push (Local -> Cloud)")
    print("2. Pull (Cloud -> Local Stats)")
    choice = input("Choose (1/2): ")

    if choice == "1":
        bridge.push_local_to_cloud()
    elif choice == "2":
        bridge.pull_stats_from_cloud()
