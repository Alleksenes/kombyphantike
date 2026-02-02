import pandas as pd
import json
import logging
from src.config import KAIKKI_EL_FILE, KELLY_FILE, PROCESSED_DIR

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ParadigmExtractor")

NOUN_OUTPUT = PROCESSED_DIR / "noun_declensions.csv"
VERB_OUTPUT = PROCESSED_DIR / "verb_conjugations.csv"
KELLY_CSV = PROCESSED_DIR / "kelly.csv"


class ParadigmExtractor:
    def __init__(self):
        self.target_lemmas = set()

    def load_targets(self):
        """Loads target lemmas from Kelly (CSV preferred) to avoid processing obscure words."""
        logger.info(f"Loading targets...")
        if KELLY_CSV.exists():
            df = pd.read_csv(KELLY_CSV, dtype=str)
        else:
            logger.warning(f"{KELLY_CSV} not found, falling back to {KELLY_FILE}")
            df = pd.read_excel(KELLY_FILE, dtype=str)

        # Try to find Lemma column
        cols = [c for c in df.columns if "Lemma" in c or "Λήμμα" in c]
        if cols:
            lemma_col = cols[0]
            self.target_lemmas = set(
                df[lemma_col]
                .str.replace('"', "")
                .str.replace("'", "")
                .str.split(",")
                .str[0]
                .str.strip()
            )
        logger.info(f"Targeting {len(self.target_lemmas)} lemmas.")

    def extract_structured_forms(self, entry):
        forms_list = entry.get("forms", [])
        valid_forms = []
        for f in forms_list:
            tags = f.get("tags", [])
            raw_tags = f.get("raw_tags", [])
            form_text = f.get("form", "")

            # Filter garbage
            if "romanization" in tags or "table-tags" in tags:
                continue
            if not form_text:
                continue

            # Enhanced Junk Filtering
            if form_text.startswith("Formed using") or "el-conjug" in form_text:
                continue

            valid_forms.append({
                "form": form_text,
                "tags": tags,
                "raw_tags": raw_tags
            })
        return valid_forms

    def extract_all(self):
        """
        Main method to return all paradigms as a dictionary.
        Returns: { "lemma": [ ...forms... ] }
        """
        self.load_targets()
        logger.info(f"Scanning Kaikki dictionary...")
        paradigms = {}
        seen_lemmas = set()

        with open(KAIKKI_EL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    word = entry.get("word")
                    # No POS restriction anymore

                    if word not in self.target_lemmas:
                        continue
                    if word in seen_lemmas:
                        continue

                    # Extract for ANY word that has forms
                    if "forms" in entry and entry["forms"]:
                        structured_forms = self.extract_structured_forms(entry)

                        if structured_forms:
                            # New Structure: Direct list
                            paradigms[word] = structured_forms
                            seen_lemmas.add(word)

                except json.JSONDecodeError:
                    continue

        return paradigms

    def run(self):
        """
        Runs the extraction and saves to paradigms.json.
        """
        paradigms = self.extract_all()
        logger.info(f"Extracted paradigms for {len(paradigms)} lemmas.")

        OUTPUT_JSON = PROCESSED_DIR / "paradigms.json"
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(paradigms, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved paradigms to {OUTPUT_JSON}")


if __name__ == "__main__":
    extractor = ParadigmExtractor()
    extractor.run()
