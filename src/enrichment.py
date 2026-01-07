import pandas as pd
import logging, re, unicodedata, difflib
from typing import Dict, Any
from src.lemmatizer import AncientLemmatizer

logger = logging.getLogger(__name__)


class Enricher:
    def __init__(self, lsj_oracle=None):
        self.lsj_oracle = lsj_oracle
        self.lemmatizer = AncientLemmatizer(use_stanza=True, use_odycy=True)
        # Capture ALL Greek words
        self.greek_word_pattern = re.compile(
            r"([\u0370-\u03FF\u1F00-\u1FFF]+)", re.IGNORECASE
        )

    def clean_ipa(self, sounds: list) -> str:
        if not sounds:
            return ""
        for s in sounds:
            if "ipa" in s:
                return (
                    s["ipa"].replace("/", "").replace("[", "").replace("]", "").strip()
                )
        return ""

    def sanitize_greek(self, word):
        """Removes Macrons (¯) and Breves (˘)."""
        if not word:
            return ""
        decomp = unicodedata.normalize("NFD", word)
        # Filter Macrons (0304), Breves (0306), and also Circumflex variations if needed
        filtered = "".join([c for c in decomp if c not in ["\u0304", "\u0306"]])
        return unicodedata.normalize("NFC", filtered)

    def calculate_similarity(self, word_a, word_b):
        clean_a = self.sanitize_greek(word_a).lower()
        clean_b = self.sanitize_greek(word_b).lower()
        return difflib.SequenceMatcher(None, clean_a, clean_b).ratio()

    def check_oracle(self, word):
        """Helper to check if a word exists in LSJ."""
        if not self.lsj_oracle:
            return None
        clean = self.sanitize_greek(word)
        data = self.lsj_oracle.get_data(clean)
        if data.get("def"):
            return clean
        return None

    def mutation_engine(self, lemma):
        """
        The Clever Workaround.
        Reconstructs Ancient forms from Modern forms by reversing common phonetic shifts.
        """
        candidates = []

        # 1. VERB RESTORATION (-ώ -> -έω, -όω, -άω)
        if lemma.endswith("ώ") or lemma.endswith("άω") or lemma.endswith("ω"):
            stem = lemma.rstrip("άω").rstrip("ώ").rstrip("ω")
            candidates.append(stem + "έω")
            candidates.append(stem + "όω")
            candidates.append(stem + "άω")
            candidates.append(stem + "ω")

        # 2. NEW: -ώνω RESTORATION (e.g. μετανιώνω -> μετανοέω)
        if lemma.endswith("ώνω"):
            stem = lemma[:-3]  # Remove 'ώνω'
            if stem.endswith("ι"):
                stem_no_i = stem[:-1]
                candidates.append(stem_no_i + "οέω")  # metan-oeo
                candidates.append(stem_no_i + "έω")
                candidates.append(stem_no_i + "όω")

            candidates.append(stem + "όω")  # plhr-ono -> plhr-ow
            candidates.append(stem + "έω")

        # 3. APHERESIS RESTORATION
        prefixes = ["ε", "α", "ο", "η"]
        base_candidates = [lemma] + candidates
        final_candidates = []
        final_candidates.extend(base_candidates)

        for cand in base_candidates:
            for p in prefixes:
                final_candidates.append(p + cand)

        # 4. CHECK ALL CANDIDATES
        for cand in final_candidates:
            valid = self.check_oracle(cand)
            if valid:
                return valid

        return ""

    def extract_antecedent(self, lemma: str, etymology: str) -> str:
        """
        Tournament -> Hail Mary -> Mutation Engine
        """
        best_candidate = ""

        # --- PHASE 1: TEXT EXTRACTION (Tournament) ---
        if etymology:
            raw_candidates = self.greek_word_pattern.findall(etymology)
            candidates = [
                c for c in raw_candidates if len(c) > 1 or c in ["ο", "η", "το"]
            ]

            valid_candidates = []
            if self.lsj_oracle:
                for cand in candidates:
                    if self.check_oracle(cand):
                        valid_candidates.append(cand)

            if valid_candidates:
                best_score = -1.0
                for cand in valid_candidates:
                    score = self.calculate_similarity(lemma, cand)
                    if score > best_score:
                        best_score = score
                        best_candidate = cand

            elif candidates:
                # Fallback Lemmatization on candidates
                primary = candidates[0]
                clean_primary = self.sanitize_greek(primary)
                lemma_cand = self.lemmatizer.lemmatize(clean_primary)
                if self.check_oracle(lemma_cand):
                    best_candidate = lemma_cand

        if best_candidate:
            return best_candidate

        # --- PHASE 2: HAIL MARY (Direct Lemma Check) ---
        if self.check_oracle(lemma):
            return lemma

        lemma_of_lemma = self.lemmatizer.lemmatize(self.sanitize_greek(lemma))
        if self.check_oracle(lemma_of_lemma):
            return lemma_of_lemma

        # --- PHASE 3: MUTATION ENGINE (The Workaround) ---
        mutated = self.mutation_engine(lemma)
        if mutated:
            return mutated

        return ""

    def enrich_data(
        self, kelly_df: pd.DataFrame, lookup: Dict[str, Any]
    ) -> pd.DataFrame:
        logger.info("Enriching Kelly List (Tournament + Mutation)...")

        enrichment_data = []
        total = len(kelly_df)
        count = 0

        for lemma in kelly_df["Lemma"]:
            count += 1
            if count % 100 == 0:
                logger.info(f"Processing {count}/{total}...")

            # Clean Lemma
            clean_lemma = lemma.replace('"', "").replace("'", "").split(",")[0].strip()

            entry = lookup.get(clean_lemma)
            if not entry:
                entry = lookup.get(lemma)

            if entry:
                ipa = self.clean_ipa(entry.get("sounds", []))
                etym_text = entry.get("etymology_text", "")

                # EXTRACT
                antecedent = self.extract_antecedent(clean_lemma, etym_text)

                definition = ""
                if "senses" in entry and len(entry["senses"]) > 0:
                    definition = entry["senses"][0].get("glosses", [""])[0]

                enrichment_data.append(
                    {
                        "Lemma": lemma,
                        "IPA": ipa,
                        "AG_Antecedent": antecedent,
                        "Etymology_Snippet": etym_text[:100],
                        "Modern_Def": definition,
                    }
                )
            else:
                enrichment_data.append(
                    {
                        "Lemma": lemma,
                        "IPA": "",
                        "AG_Antecedent": "",
                        "Etymology_Snippet": "Not found in dictionary",
                        "Modern_Def": "",
                    }
                )

        enriched_df = pd.DataFrame(enrichment_data)
        final_df = pd.merge(kelly_df, enriched_df, on="Lemma", how="left")

        return final_df
