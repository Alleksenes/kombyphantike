import pandas as pd
import json
import logging
import re
from src.config import KELLY_FILE, KAIKKI_FILE, PROCESSED_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DRILL_OUTPUT = PROCESSED_DIR / "modern_drills.csv"


class DrillGenerator:
    def __init__(self):
        self.target_lemmas = set()
        self.drills = []

    def load_targets(self):
        try:
            df = pd.read_excel(KELLY_FILE, dtype=str)
        except UnicodeDecodeError:
            df = pd.read_excel(KELLY_FILE, dtype=str)
        if "Λήμμα (Lemma)" in df.columns:
            self.target_lemmas = set(df["Λήμμα (Lemma)"].str.strip().unique())

    def is_clean(self, text):
        """Rejects template garbage like '-o}' or empty strings."""
        if not text:
            return False
        if "}" in text or "{" in text:
            return False
        if "-" in text and len(text) < 3:
            return False  # Skip suffixes
        return True

    def extract_verb_forms(self, entry):
        lemma = entry["word"]
        forms = entry.get("forms", [])

        extracted = {}

        for f in forms:
            form_text = f.get("form")
            tags = f.get("tags", [])

            if not self.is_clean(form_text):
                continue

            # 1. Aorist Active (1st Person Singular)
            # We look for "past" AND "1s" (first person singular) AND NOT "passive"
            if "past" in tags and "1s" in tags and "active" in tags:
                extracted["Aorist (1sg)"] = form_text

            # 2. Passive Present (1st Person Singular)
            if "present" in tags and "1s" in tags and "passive" in tags:
                extracted["Passive Present (1sg)"] = form_text

            # 3. Passive Aorist (1st Person Singular)
            if "past" in tags and "1s" in tags and "passive" in tags:
                extracted["Passive Aorist (1sg)"] = form_text

            # 4. Active Participle (The -ontas form)
            if "participle" in tags and "active" in tags:
                # Participles don't have person, so just grab it
                extracted["Active Participle"] = form_text

            # 5. Passive Participle (The -menos form)
            if "participle" in tags and "passive" in tags and "perfect" in tags:
                # We usually want the perfect passive participle (grammenos)
                extracted["Passive Participle"] = form_text

        for label, value in extracted.items():
            self.drills.append(
                {
                    "Λήμμα (Lemma)": lemma,
                    "POS": "Verb",
                    "Drill_Type": label,
                    "Front": f"{lemma} ({label})",
                    "Back": value,
                }
            )

    def extract_noun_forms(self, entry):
        lemma = entry["word"]
        forms = entry.get("forms", [])
        extracted = {}

        for f in forms:
            form_text = f.get("form")
            tags = f.get("tags", [])
            if not self.is_clean(form_text):
                continue

            if "nominative" in tags and "plural" in tags:
                extracted["Plural"] = form_text
            if "genitive" in tags and "singular" in tags:
                extracted["Genitive Singular"] = form_text

        for label, value in extracted.items():
            self.drills.append(
                {
                    "Λήμμα (Lemma)": lemma,
                    "POS": "Noun",
                    "Drill_Type": label,
                    "Front": f"{lemma} ({label})",
                    "Back": value,
                }
            )

    def extract_adjective_forms(self, entry):
        lemma = entry["word"]
        forms = entry.get("forms", [])
        extracted = {}

        for f in forms:
            form_text = f.get("form")
            tags = f.get("tags", [])
            if not self.is_clean(form_text):
                continue

            # Exclude comparatives/superlatives to avoid "westerner" vs "western" confusion
            if "comparative" in tags or "superlative" in tags:
                continue

            # Fem Sing
            if "feminine" in tags and "nominative" in tags and "singular" in tags:
                extracted["Feminine"] = form_text

            # Neut Sing
            if "neuter" in tags and "nominative" in tags and "singular" in tags:
                extracted["Neuter"] = form_text

        for label, value in extracted.items():
            self.drills.append(
                {
                    "Λήμμα (Lemma)": lemma,
                    "POS": "Adjective",
                    "Drill_Type": label,
                    "Front": f"{lemma} ({label})",
                    "Back": value,
                }
            )

    def generate(self):
        self.load_targets()
        logger.info(f"Scanning Kaikki for {len(self.target_lemmas)} target words...")

        with open(KAIKKI_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    word = entry.get("word")
                    if word not in self.target_lemmas:
                        continue

                    pos = entry.get("pos")

                    if pos == "verb":
                        self.extract_verb_forms(entry)
                    elif pos == "noun":
                        self.extract_noun_forms(entry)
                    elif pos == "adj" or pos == "adjective":
                        self.extract_adjective_forms(entry)

                except json.JSONDecodeError:
                    continue

        df = pd.DataFrame(self.drills)
        # Drop duplicates and sort
        df = df.drop_duplicates(subset=["Λήμμα (Lemma)", "Drill_Type"])
        df = df.sort_values(by=["Λήμμα (Lemma)", "POS"])

        logger.info(f"Generated {len(df)} clean drills.")
        df.to_csv(DRILL_OUTPUT, index=False, encoding="utf-8-sig")
        logger.info(f"Saved to {DRILL_OUTPUT}")


if __name__ == "__main__":
    gen = DrillGenerator()
    gen.generate()
