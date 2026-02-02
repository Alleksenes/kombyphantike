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
        # Deprecated storage for CSVs
        self.noun_data = []
        self.verb_data = []

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

            # 1. Filter Garbage
            # Exclude romanizations and table tags
            if "romanization" in tags or "table-tags" in tags:
                continue

            # Check for junk in text
            if not form_text:
                continue

            # Junk templates often leaked into form text
            if form_text.startswith("el-conjug") or \
               "Formed using" in form_text or \
               form_text.startswith("-"): # Optional: suffixes often not useful as independent forms, but maybe keep?
                                          # Requirement said "clean all junk".
                                          # I'll stick to the specific examples + reasonable heuristic.
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
        Returns: { "lemma": [ { "form": "...", "tags": [...], "raw_tags": [...] } ] }
        """
        self.load_targets()
        logger.info(f"Scanning Kaikki dictionary...")
        paradigms = {}

        # Reset internal storage for CSV generation (Deprecated but kept for safety/structure)
        self.noun_data = []
        self.verb_data = []
        seen_lemmas = set()

        with open(KAIKKI_EL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    word = entry.get("word")

                    # Filter by target list
                    if word not in self.target_lemmas:
                        continue
                    if word in seen_lemmas:
                        continue

                    # We now accept ANY word that has forms (Noun, Verb, Adjective, etc.)
                    # Check if 'forms' exists and is not empty
                    if not entry.get("forms"):
                        continue

                    # Extract Structured Forms (Lossless)
                    structured_forms = self.extract_structured_forms(entry)

                    if structured_forms:
                        # New Structure: Direct List
                        paradigms[word] = structured_forms
                        seen_lemmas.add(word)

                except json.JSONDecodeError:
                    continue

        return paradigms

    def run(self):
        """
        Legacy run method.
        CSV generation is now deprioritized/disabled to focus on JSON source of truth.
        """
        self.extract_all()
        logger.info("Paradigm extraction complete. CSV generation skipped (Deprecated).")

        # Legacy CSV code commented out per instructions:
        # Save Nouns
        # df_noun = pd.DataFrame(self.noun_data)
        # if not df_noun.empty:
        #     ... (saving logic)

        # Save Verbs
        # df_verb = pd.DataFrame(self.verb_data)
        # if not df_verb.empty:
        #     ... (saving logic)


if __name__ == "__main__":
    extractor = ParadigmExtractor()
    extractor.run()
