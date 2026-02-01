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

    def get_gender(self, entry):
        head_templates = entry.get("head_templates", [])
        if not head_templates:
            return ""
        args = head_templates[0].get("args", {})
        g = args.get("g") or args.get("1") or ""
        if "m" in g:
            return "Masc"
        if "f" in g:
            return "Fem"
        if "n" in g:
            return "Neut"
        return g

    def extract_noun_forms(self, entry):
        lemma = entry.get("word")
        forms_list = entry.get("forms", [])
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

        def is_greek(tags):
            return "romanization" not in tags and "table-tags" not in tags

        for f in forms_list:
            tags = f.get("tags", [])
            form_text = f.get("form", "")
            if not form_text or not is_greek(tags):
                continue

            if "singular" in tags:
                if "nominative" in tags:
                    row["Nom_Sg"] = form_text
                elif "genitive" in tags:
                    row["Gen_Sg"] = form_text
                elif "accusative" in tags:
                    row["Acc_Sg"] = form_text
                elif "vocative" in tags:
                    row["Voc_Sg"] = form_text
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

    def extract_verb_forms(self, entry):
        lemma = entry.get("word")
        forms_list = entry.get("forms", [])

        # Focus on Present Active Indicative for now + basic Past
        row = {
            "Lemma": lemma,
            "Pres_Act_1Sg": "",
            "Pres_Act_2Sg": "",
            "Pres_Act_3Sg": "",
            "Pres_Act_1Pl": "",
            "Pres_Act_2Pl": "",
            "Pres_Act_3Pl": "",
            "Past_Act_1Sg": "",  # Aorist or Imperfect
            "Future_Act_1Sg": "",
        }

        def is_greek(tags):
            return "romanization" not in tags and "table-tags" not in tags

        for f in forms_list:
            tags = f.get("tags", [])
            form_text = f.get("form", "")
            if not form_text or not is_greek(tags):
                continue

            # Active Voice
            if (
                "active" in tags or "passive" not in tags
            ):  # Default to active if unspecified? Safe assumption for now
                if "indicative" in tags:
                    if "present" in tags:
                        if "first-person" in tags and "singular" in tags:
                            row["Pres_Act_1Sg"] = form_text
                        if "second-person" in tags and "singular" in tags:
                            row["Pres_Act_2Sg"] = form_text
                        if "third-person" in tags and "singular" in tags:
                            row["Pres_Act_3Sg"] = form_text
                        if "first-person" in tags and "plural" in tags:
                            row["Pres_Act_1Pl"] = form_text
                        if "second-person" in tags and "plural" in tags:
                            row["Pres_Act_2Pl"] = form_text
                        if "third-person" in tags and "plural" in tags:
                            row["Pres_Act_3Pl"] = form_text

                    if (
                        ("past" in tags or "imperfect" in tags or "perfective" in tags)
                        and "first-person" in tags
                        and "singular" in tags
                    ):
                        # Prioritize Aorist (perfective past) if available, else Imperfect
                        if not row["Past_Act_1Sg"] or "perfective" in tags:
                            row["Past_Act_1Sg"] = form_text

                    if (
                        "future" in tags
                        and "first-person" in tags
                        and "singular" in tags
                    ):
                        row["Future_Act_1Sg"] = form_text

        return row

    def run(self):
        self.load_targets()
        logger.info(f"Scanning Kaikki dictionary...")
        seen_lemmas = set()

        with open(KAIKKI_EL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    word = entry.get("word")
                    pos = entry.get("pos")

                    if word not in self.target_lemmas:
                        continue
                    if word in seen_lemmas:
                        continue  # Simple dedup

                    if pos == "noun":
                        self.noun_data.append(self.extract_noun_forms(entry))
                        seen_lemmas.add(word)
                    elif pos == "verb":
                        self.verb_data.append(self.extract_verb_forms(entry))
                        seen_lemmas.add(word)

                except json.JSONDecodeError:
                    continue

        # Save Nouns
        df_noun = pd.DataFrame(self.noun_data)
        if not df_noun.empty:
            df_noun = df_noun.sort_values(by="Lemma")
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
            # Ensure cols exist
            for c in cols:
                if c not in df_noun.columns:
                    df_noun[c] = ""
            df_noun = df_noun[cols]
            df_noun.to_csv(NOUN_OUTPUT, index=False, encoding="utf-8-sig")
            logger.info(f"Saved {len(df_noun)} nouns to {NOUN_OUTPUT}")

        # Save Verbs
        df_verb = pd.DataFrame(self.verb_data)
        if not df_verb.empty:
            df_verb = df_verb.sort_values(by="Lemma")
            cols = [
                "Lemma",
                "Pres_Act_1Sg",
                "Pres_Act_2Sg",
                "Pres_Act_3Sg",
                "Pres_Act_1Pl",
                "Pres_Act_2Pl",
                "Pres_Act_3Pl",
                "Past_Act_1Sg",
                "Future_Act_1Sg",
            ]
            # Ensure cols exist
            for c in cols:
                if c not in df_verb.columns:
                    df_verb[c] = ""
            df_verb = df_verb[cols]
            df_verb.to_csv(VERB_OUTPUT, index=False, encoding="utf-8-sig")
            logger.info(f"Saved {len(df_verb)} verbs to {VERB_OUTPUT}")


if __name__ == "__main__":
    extractor = ParadigmExtractor()
    extractor.run()
