import spacy
import pandas as pd
import logging
import warnings

# Suppress warnings from spaCy about small models if any
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class Analyzer:
    def __init__(self):
        logger.info("Loading English NLP model for semantic comparison...")
        try:
            # We load the English model because the definitions are in English
            self.nlp = spacy.load("en_core_web_md")
        except OSError:
            logger.error(
                "Model 'en_core_web_md' not found. Please run: python -m spacy download en_core_web_md"
            )
            raise

    def calculate_similarity(self, def1: str, def2: str) -> float:
        """Calculates semantic similarity between two English definitions."""
        if not def1 or not def2:
            return 0.0

        # Process texts
        doc1 = self.nlp(def1)
        doc2 = self.nlp(def2)

        return doc1.similarity(doc2)

    def analyze_row(self, row):
        lemma = row["Lemma"]
        antecedent = row.get("AG_Antecedent", "")
        modern_def = row.get("Modern_Def", "")
        ancient_def = row.get("LSJ_Definition", "")

        shift_type = "Unclassified"
        warning = ""
        score = 0.0

        # 1. Check for Ancestry
        if not antecedent:
            return pd.Series(["New Coinage / Loanword", "", 0.0])

        # 2. Check for Identity
        if lemma.lower() == antecedent.lower():
            shift_type = "Direct Inheritance"
        else:
            shift_type = "Morphological Evolution"

        # 3. The Semantic Judge (Vector Comparison)
        if modern_def and ancient_def:
            score = self.calculate_similarity(modern_def, ancient_def)

            # THRESHOLD TUNING
            # < 0.4 implies significant drift (False Friend territory)
            # > 0.7 implies high stability

            if score < 0.4:
                warning = f"HIGH DRIFT DETECTED (Score: {score:.2f})"
                shift_type = "Semantic Shift / False Friend"
            elif score < 0.6:
                warning = f"Moderate Drift (Score: {score:.2f})"
            else:
                warning = "Stable Meaning"

        return pd.Series([shift_type, warning, score])

    def apply_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Running AI Semantic Analysis...")

        # Apply analysis
        results = df.apply(self.analyze_row, axis=1)

        df["Shift_Type"] = results[0]
        df["Semantic_Warning"] = results[1]
        df["Similarity_Score"] = results[2]

        return df
