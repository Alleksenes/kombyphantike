import pandas as pd
import json
import logging
from typing import Dict, Generator, Any
from src.config import KELLY_FILE, KAIKKI_FILE, COL_LEMMA

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class DataIngestor:
    def __init__(self):
        self.kelly_df = None

    def load_kelly_list(self) -> pd.DataFrame:
        logger.info(f"Loading Kelly List from {KELLY_FILE}...")
        try:
            # Check extension
            if str(KELLY_FILE).endswith(".xlsx"):
                self.kelly_df = pd.read_excel(KELLY_FILE, dtype=str)
            else:
                self.kelly_df = pd.read_csv(KELLY_FILE, dtype=str)

            # Clean column names
            self.kelly_df.columns = [c.strip() for c in self.kelly_df.columns]

            # DYNAMIC MAPPING
            # Find the column that contains "Lemma" or "Λήμμα"
            lemma_col = next(
                (c for c in self.kelly_df.columns if "Lemma" in c or "Λήμμα" in c), None
            )

            if not lemma_col:
                raise ValueError(
                    f"Could not find Lemma column. Columns: {self.kelly_df.columns}"
                )

            # Rename to standard "Lemma"
            self.kelly_df = self.kelly_df.rename(columns={lemma_col: COL_LEMMA})

            # Find CEFR
            cefr_col = next((c for c in self.kelly_df.columns if "CEF" in c), None)
            if cefr_col:
                self.kelly_df = self.kelly_df.rename(columns={cefr_col: "CEFR"})

            # Drop empty rows
            self.kelly_df = self.kelly_df.dropna(subset=[COL_LEMMA])
            self.kelly_df[COL_LEMMA] = self.kelly_df[COL_LEMMA].str.strip()

            # Drop duplicates
            self.kelly_df = self.kelly_df.drop_duplicates(
                subset=[COL_LEMMA], keep="first"
            )

            logger.info(f"Successfully loaded {len(self.kelly_df)} words.")
            return self.kelly_df

        except Exception as e:
            logger.error(f"Failed to load Kelly List: {e}")
            raise

    # ... (Rest of class remains same) ...
    def stream_kaikki_dictionary(self) -> Generator[Dict[str, Any], None, None]:
        logger.info(f"Streaming Dictionary from {KAIKKI_FILE}...")
        try:
            with open(KAIKKI_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        if entry.get("lang_code") == "el":
                            yield entry
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            logger.error(f"Dictionary file not found at {KAIKKI_FILE}")
            raise

    def create_lookup_table(self, target_lemmas: set) -> Dict[str, Dict]:
        logger.info("Building optimized lookup table...")
        lookup = {}
        for entry in self.stream_kaikki_dictionary():
            word = entry.get("word")
            if word in target_lemmas:
                lookup[word] = entry
        logger.info(f"Lookup table built. Found data for {len(lookup)} words.")
        return lookup
