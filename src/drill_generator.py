import pandas as pd
import json
import logging
from src.config import KELLY_FILE, KAIKKI_EL_FILE, DRILLS_FILE

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("DrillGen")


class DrillGenerator:
    def __init__(self):
        self.drills = []
        # Load targets from Kelly
        try:
            kdf = pd.read_csv(KELLY_FILE, dtype=str, encoding="utf-8-sig")
        except:
            kdf = pd.read_csv(KELLY_FILE, dtype=str)  # Fallback

        # Find Lemma col
        lemma_col = next((c for c in kdf.columns if "Lemma" in c or "Λήμμα" in c), None)
        if not lemma_col:
            logger.error("Kelly Lemma column not found.")
            exit()

        self.targets = set(kdf[lemma_col].str.strip().unique())

    def is_clean(self, text):
        if not text:
            return False
        if "-" in text and len(text) < 3:
            return False
        if "el-κλίσ" in text:
            return False
        return True

    def extract_verb(self, entry):
        lemma = entry.get("word")
        forms = entry.get("forms", [])

        extracted = {}

        for f in forms:
            form = f.get("form")
            raw_tags = f.get("raw_tags", [])

            if not self.is_clean(form):
                continue

            # Convert list to string for easier searching
            tag_str = " ".join(raw_tags)

            # AORIST (Simple Past) - 1st Sg
            if (
                "Αόριστος" in tag_str
                and "α' ενικ." in tag_str
                and "Παθητική" not in tag_str
                and "παθ." not in tag_str
            ):
                extracted["Aorist (Past)"] = form

            # FUTURE (Simple) - 1st Sg (Tha grapso)
            if "Συνοπτ. Μέλλ." in tag_str and "α' ενικ." in tag_str:
                extracted["Future Simple"] = form

            # SUBJUNCTIVE (Simple) - 1st Sg (Na grapso)
            if (
                "Υποτακτική" in tag_str
                and "Συνοπτικοί" in tag_str
                and "α' ενικ." in tag_str
            ):
                extracted["Subjunctive Simple"] = form

            # PASSIVE AORIST - 1st Sg
            if (
                "Αόριστος" in tag_str
                and "α' ενικ." in tag_str
                and (
                    "Παθητική" in tag_str
                    or "παθ." in tag_str
                    or "Passive" in str(f.get("tags"))
                )
            ):
                extracted["Passive Aorist"] = form

            # PARTICIPLE (Passive Perfect) - grammenos
            if "μετοχή" in tag_str.lower() or "μτχ" in tag_str.lower():
                if "παθ" in tag_str.lower() or "passive" in str(f.get("tags")):
                    extracted["Passive Participle"] = form

        for label, val in extracted.items():
            self.drills.append(
                {
                    "Lemma": lemma,
                    "POS": "Verb",
                    "Drill_Type": label,
                    "Front": f"{lemma} ({label})",
                    "Back": val,
                }
            )

    def extract_noun(self, entry):
        lemma = entry.get("word")
        forms = entry.get("forms", [])
        extracted = {}

        for f in forms:
            form = f.get("form")
            raw_tags = f.get("raw_tags", [])
            tag_str = " ".join(raw_tags)

            if not self.is_clean(form):
                continue

            # Genitive Singular
            if "γενική" in tag_str and "ενικός" in tag_str:
                extracted["Genitive Sg"] = form

            # Nominative Plural
            if "ονομαστική" in tag_str and "πληθυντικός" in tag_str:
                extracted["Nominative Pl"] = form

            # Genitive Plural
            if "γενική" in tag_str and "πληθυντικός" in tag_str:
                extracted["Genitive Pl"] = form

        for label, val in extracted.items():
            self.drills.append(
                {
                    "Lemma": lemma,
                    "POS": "Noun",
                    "Drill_Type": label,
                    "Front": f"{lemma} ({label})",
                    "Back": val,
                }
            )

    def run(self):
        logger.info(f"Scanning Kaikki-EL for {len(self.targets)} words...")

        with open(KAIKKI_EL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    word = entry.get("word")
                    if word not in self.targets:
                        continue

                    pos = entry.get("pos")
                    if pos == "verb":
                        self.extract_verb(entry)
                    elif pos == "noun":
                        self.extract_noun(entry)

                except:
                    continue

        df = pd.DataFrame(self.drills).drop_duplicates()
        df.to_csv(DRILLS_FILE, index=False, encoding="utf-8-sig")
        logger.info(f"Generated {len(df)} drills. Saved to {DRILLS_FILE}")


if __name__ == "__main__":
    gen = DrillGenerator()
    gen.run()
