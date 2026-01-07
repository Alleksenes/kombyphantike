import pandas as pd
import logging, json, unicodedata
from src.config import DICT_DIR
from src.beta_code import BetaCodeConverter

logger = logging.getLogger(__name__)


class LSJEnricher:
    def __init__(self):
        self.index_path = DICT_DIR / "lsj_index.json"
        self.converter = BetaCodeConverter()
        self.lsj_data = {}
        self._load_index()

    def _load_index(self):
        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                self.lsj_data = json.load(f)
        else:
            logger.warning("LSJ Index not found. Run 'src/lsj_fuzzy_indexer.py' first.")

    def sanitize_greek(self, word):
        """Removes Macrons (¯) and Breves (˘)."""
        if not word:
            return ""
        decomp = unicodedata.normalize("NFD", word)
        filtered = "".join([c for c in decomp if c not in ["\u0304", "\u0306"]])
        return unicodedata.normalize("NFC", filtered)

    def normalize_key(self, beta_key):
        """Matches the logic in the Indexer: Strip chars and lowercase."""
        if not beta_key:
            return ""
        clean = "".join([c for c in beta_key if c.isalpha()])
        return clean.lower()

    def get_data(self, ag_word):
        """
        Returns dict with 'def', 'aor', 'cit'.
        """
        if not ag_word or pd.isna(ag_word):
            return {"def": "", "aor": "", "cit": ""}

        # 1. Sanitize
        clean_word = self.sanitize_greek(ag_word)

        # 2. Beta Code
        beta_key = self.converter.to_beta_code(clean_word)

        # 3. Canonicalize
        query_key = self.converter.canonicalize(beta_key)

        return self.lsj_data.get(query_key, {"def": "", "aor": "", "cit": ""})

    def enrich(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Querying LSJ for Definitions, Morphology, and Poetry...")

        def lookup_row(word):
            data = self.get_data(word)
            return pd.Series(
                [data.get("def", ""), data.get("aor", ""), data.get("cit", "")]
            )

        # Apply to AG_Antecedent column
        df[["LSJ_Definition", "AG_Aorist", "Ancient_Context"]] = df[
            "AG_Antecedent"
        ].apply(lookup_row)

        return df
