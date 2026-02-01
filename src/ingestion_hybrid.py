import pandas as pd
import json
import logging
import unicodedata
from src.config import (
    KELLY_FILE,
    KAIKKI_EL_FILE,
    KAIKKI_EN_FILE,
    COL_LEMMA,
    PROCESSED_DIR,
)
from src.noun_declension_extractor import ParadigmExtractor

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("HybridIngestor")
PARADIGMS_FILE = PROCESSED_DIR / "paradigms.json"


class HybridIngestor:
    def __init__(self):
        self.kelly_df = None
        self.target_lemmas = set()
        self.master_lookup = {}

    def normalize(self, text):
        if not text:
            return ""
        return unicodedata.normalize("NFC", str(text).strip())

    def load_kelly(self):
        logger.info(f"Loading Kelly List from {KELLY_FILE}...")
        try:
            if str(KELLY_FILE).endswith(".xlsx"):
                df = pd.read_excel(KELLY_FILE, dtype=str)
            else:
                df = pd.read_csv(KELLY_FILE, dtype=str)

            df.columns = [c.strip() for c in df.columns]
            lemma_col = next(
                (c for c in df.columns if "Lemma" in c or "Λήμμα" in c), None
            )
            if not lemma_col:
                raise ValueError("Lemma column not found")

            df = df.rename(columns={lemma_col: COL_LEMMA})
            # In load_kelly:
            # If comma exists, take the first part
            df[COL_LEMMA] = df[COL_LEMMA].apply(lambda x: str(x).split(",")[0].strip())
            df[COL_LEMMA] = df[COL_LEMMA].apply(self.normalize)
            df = df.dropna(subset=[COL_LEMMA]).drop_duplicates(subset=[COL_LEMMA])

            self.kelly_df = df
            self.target_lemmas = set(df[COL_LEMMA].unique())
            logger.info(f"Targets identified: {len(self.target_lemmas)}")

        except Exception as e:
            logger.error(f"Kelly Load Failed: {e}")
            exit()

    def scan_hellenic_core(self):
        """Pass 1: Scan Kaikki-EL for Structure"""
        logger.info(f"Scanning Hellenic Core ({KAIKKI_EL_FILE})...")

        count = 0
        with open(KAIKKI_EL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("lang_code") != "el":
                        continue

                    word = self.normalize(entry.get("word"))
                    if word not in self.target_lemmas:
                        continue

                    # INITIALIZE IF NEW
                    if word not in self.master_lookup:
                        self.master_lookup[word] = {
                            "lemma": word,
                            "pos": entry.get("pos"),
                            "etymology_text_el": entry.get("etymology_text", ""),
                            # forms handled by ParadigmExtractor
                            "senses_el": [],
                            "senses_en": [],
                            "examples": [],
                            "synonyms": [],
                        }
                    else:
                        # MERGE ETYMOLOGY IF MISSING
                        if not self.master_lookup[word][
                            "etymology_text_el"
                        ] and entry.get("etymology_text"):
                            self.master_lookup[word]["etymology_text_el"] = entry.get(
                                "etymology_text"
                            )

                    # ALWAYS APPEND DATA
                    for sense in entry.get("senses", []):
                        tags = sense.get("tags", []) + sense.get("raw_tags", [])
                        for gloss in sense.get("glosses", []):
                            # Avoid duplicates
                            exists = any(
                                s["text"] == gloss
                                for s in self.master_lookup[word]["senses_el"]
                            )
                            if not exists:
                                self.master_lookup[word]["senses_el"].append(
                                    {"text": gloss, "tags": tags}
                                )

                        # EXTRACT EXAMPLES
                        for ex in sense.get("examples", []):
                            text = ex.get("text", "")
                            text = text.replace("'''", "")
                            if (
                                text
                                and text not in self.master_lookup[word]["examples"]
                            ):
                                self.master_lookup[word]["examples"].append(text)

                    if "synonyms" in entry:
                        for syn in entry["synonyms"]:
                            if (
                                "word" in syn
                                and syn["word"]
                                not in self.master_lookup[word]["synonyms"]
                            ):
                                self.master_lookup[word]["synonyms"].append(syn["word"])

                    count += 1
                except:
                    continue

        logger.info(f"Hellenic Pass Complete. Processed {count} entries.")

    def scan_english_gloss(self):
        """Pass 2: Scan Kaikki-EN for English Definitions"""
        logger.info(f"Scanning English Gloss ({KAIKKI_EN_FILE})...")

        hits = 0
        with open(KAIKKI_EN_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("lang_code") != "el":
                        continue

                    word = self.normalize(entry.get("word"))
                    if word not in self.master_lookup:
                        continue

                    for sense in entry.get("senses", []):
                        tags = sense.get("tags", []) + sense.get("raw_tags", [])
                        for gloss in sense.get("glosses", []):
                            exists = any(
                                s["text"] == gloss
                                for s in self.master_lookup[word]["senses_en"]
                            )
                            if not exists:
                                self.master_lookup[word]["senses_en"].append(
                                    {"text": gloss, "tags": tags}
                                )

                    if "sounds" in entry and "sounds" not in self.master_lookup[word]:
                        self.master_lookup[word]["sounds"] = entry["sounds"]

                    hits += 1
                except:
                    continue

        logger.info(f"English Pass Complete. Enriched {hits} words.")

    def run(self):
        self.load_kelly()
        self.scan_hellenic_core()
        self.scan_english_gloss()

        # Integrate ParadigmExtractor
        logger.info("Extracting Paradigms via ParadigmExtractor...")
        extractor = ParadigmExtractor()
        # Optimization: ParadigmExtractor re-loads targets, which is fine but we could pass them if we changed API
        paradigms = extractor.extract_all()

        with open(PARADIGMS_FILE, "w", encoding="utf-8") as f:
            json.dump(paradigms, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(paradigms)} paradigms to {PARADIGMS_FILE}")

        return self.master_lookup


if __name__ == "__main__":
    ingestor = HybridIngestor()
    data = ingestor.run()
