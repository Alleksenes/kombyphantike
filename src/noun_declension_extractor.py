import pandas as pd
import json
import logging
from src.config import KAIKKI_FILE, KELLY_FILE, PROCESSED_DIR

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("NounExtractor")

OUTPUT_FILE = PROCESSED_DIR / "noun_declensions.csv"


class NounDeclensionExtractor:
    def __init__(self):
        self.target_lemmas = set()
        self.data = []

    def load_targets(self):
        """Loads target lemmas from Kelly to avoid processing obscure words."""
        logger.info(f"Loading targets from {KELLY_FILE}...")
        df = pd.read_csv(KELLY_FILE, dtype=str)
        if "Lemma" in df.columns:
            # Clean lemmas (remove quotes, extra spaces)
            self.target_lemmas = set(
                df["Lemma"]
                .str.replace('"', "")
                .str.replace("'", "")
                .str.split(",")
                .str[0]
                .str.strip()
            )
        logger.info(f"Targeting {len(self.target_lemmas)} nouns.")

    def get_gender(self, entry):
        """Extracts gender from head_templates."""
        head_templates = entry.get("head_templates", [])
        if not head_templates:
            return ""

        # Usually in 'args' -> 'g' or '1'
        args = head_templates[0].get("args", {})
        g = args.get("g") or args.get("1") or ""

        # Normalize
        if "m" in g:
            return "Masc"
        if "f" in g:
            return "Fem"
        if "n" in g:
            return "Neut"
        return g

    def extract_forms(self, entry):
        lemma = entry.get("word")
        forms_list = entry.get("forms", [])

        # Initialize row structure
        row = {
            "Lemma": lemma,
            "Gender": self.get_gender(entry),
            "Nom_Sg": "",
            "Gen_Sg": "",
            "Acc_Sg": "",
            "Voc_Sg": "",
            "Nom_Pl": "",
            "Gen_Pl": "",
            "Acc_Pl": "",
            "Voc_Pl": "",
        }

        # Helper to check if a form is valid Greek (not romanization)
        def is_greek(tags):
            return (
                "romanization" not in tags
                and "table-tags" not in tags
                and "inflection-template" not in tags
            )

        for f in forms_list:
            tags = f.get("tags", [])
            form_text = f.get("form", "")

            if not form_text or not is_greek(tags):
                continue

            # MAPPING LOGIC
            # Singular
            if "singular" in tags:
                if "nominative" in tags:
                    row["Nom_Sg"] = form_text
                elif "genitive" in tags:
                    row["Gen_Sg"] = form_text
                elif "accusative" in tags:
                    row["Acc_Sg"] = form_text
                elif "vocative" in tags:
                    row["Voc_Sg"] = form_text

            # Plural
            elif "plural" in tags:
                if "nominative" in tags:
                    row["Nom_Pl"] = form_text
                elif "genitive" in tags:
                    row["Gen_Pl"] = form_text
                elif "accusative" in tags:
                    row["Acc_Pl"] = form_text
                elif "vocative" in tags:
                    row["Voc_Pl"] = form_text

        return row

    def run(self):
        self.load_targets()
        logger.info(f"Scanning Kaikki dictionary...")

        seen_lemmas = set()

        with open(KAIKKI_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    word = entry.get("word")
                    pos = entry.get("pos")

                    # Filter
                    if pos != "noun":
                        continue
                    if word not in self.target_lemmas:
                        continue
                    if word in seen_lemmas:
                        continue

                    # Extract
                    row = self.extract_forms(entry)

                    # Basic validation: If it has no forms other than lemma, skip?
                    # No keep it, maybe it's indeclinable.

                    self.data.append(row)
                    seen_lemmas.add(word)

                except json.JSONDecodeError:
                    continue

        # Convert to DataFrame and Save
        df = pd.DataFrame(self.data)

        # Sort by Lemma
        df = df.sort_values(by="Lemma")

        # Reorder columns for readability
        cols = [
            "Lemma",
            "Gender",
            "Nom_Sg",
            "Gen_Sg",
            "Acc_Sg",
            "Voc_Sg",
            "Nom_Pl",
            "Gen_Pl",
            "Acc_Pl",
            "Voc_Pl",
        ]
        df = df[cols]

        logger.info(f"Extracted declensions for {len(df)} nouns.")
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        logger.info(f"Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    extractor = NounDeclensionExtractor()
    extractor.run()
