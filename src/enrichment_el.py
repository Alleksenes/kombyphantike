import re
import pandas as pd
import logging
import unicodedata
import difflib
from src.lemmatizer import AncientLemmatizer
from src.enrichment_lsj import LSJEnricher

logger = logging.getLogger(__name__)


class HellenicEnricher:
    def __init__(self):
        self.lsj_oracle = LSJEnricher()
        self.lemmatizer = AncientLemmatizer(use_stanza=True)

        # ANCHORS (The signals of ancestry)
        self.anchors = [
            "αρχαία",
            "αρχ.",
            "ελληνική",
            "ελλ.",
            # "μεσαιωνική",
            # "μσν.",
        ]

        self.blacklist = [
            "ελληνικός",
            "ελληνική",
            "αρχαίος",
            "αρχαία",
            "κοινός",
            "κοινή",
            "νέα",
            "νέος",
            "μεσαιωνικός",
        ]

    def sanitize_greek(self, word):
        if not word:
            return ""
        # Remove anything that is not a Greek letter or hyphen
        word = re.sub(r"[^\w\u0370-\u03FF\u1F00-\u1FFF\-]", "", word)
        return unicodedata.normalize("NFC", word.strip())

    def check_oracle(self, word):
        clean = self.sanitize_greek(word)
        data = self.lsj_oracle.get_data(clean)
        # We accept if it has a definition OR a citation
        if data.get("def") or data.get("cit"):
            return clean
        return None

    def heuristic_ancient_forms(self, lemma):
        """
        Attempts to reconstruct Ancient forms from Modern morphology.
        """
        candidates = []

        # 1. -νύω -> -νυμι (e.g. αναδεικνύω -> ἀναδείκνυμι)
        if lemma.endswith("νύω"):
            stem = lemma[:-3]
            candidates.append(stem + "νυμι")
            candidates.append(stem + "νύω")

        # 2. -άω -> -ῶ (Contracted)
        if lemma.endswith("άω"):
            stem = lemma[:-2]
            candidates.append(stem + "ῶ")
            candidates.append(stem + "άω")

        # 3. -ώ -> -έω / -όω (Contracted)
        if lemma.endswith("ώ"):
            stem = lemma[:-1]
            candidates.append(stem + "έω")
            candidates.append(stem + "όω")
            candidates.append(stem + "άω")

        # 4. -μαι (Passive) -> -omai (Ancient)
        if lemma.endswith("μαι"):
            candidates.append(lemma)

        # 5. Neuter -ον -> -ος (Adjective root)
        if lemma.endswith("ον"):
            stem = lemma[:-2]
            candidates.append(stem + "ος")
        elif lemma.endswith("ο"):
            stem = lemma[:-1]
            candidates.append(stem + "ος")

        return candidates

    def extract_antecedent(self, lemma, etym_text):
        candidates = []

        etym_text = etym_text.replace(
            "διαχρονικό δάνειο",
            "διαχρονικό_δάνειο",
        )  # Tokenize as one unit

        # 1. WINDOW SCAN (The Smart Hunt)
        if etym_text:
            # Split by space to preserve sequence for window scanning
            raw_tokens = etym_text.split()

            for i, raw_token in enumerate(raw_tokens):
                clean_token = self.sanitize_greek(raw_token)

                if clean_token.lower() in self.anchors:
                    # Look ahead 1-3 words
                    for offset in range(1, 4):
                        if i + offset >= len(raw_tokens):
                            break

                        target_raw = raw_tokens[i + offset]
                        target = self.sanitize_greek(target_raw)

                        if target in self.blacklist:
                            continue

                        if len(target) < 2:
                            continue

                        # --- STRATEGY A: Direct Check ---
                        # e.g. θεολόγος -> θεολόγος
                        if self.check_oracle(target):
                            sim = difflib.SequenceMatcher(None, lemma, target).ratio()
                            candidates.append((target, sim))
                            continue

                        # --- STRATEGY B: Lemmatized Check ---
                        # e.g. ἀγαθόν -> ἀγαθός
                        lem = self.lemmatizer.lemmatize(target)
                        if lem and lem != target:
                            if self.check_oracle(lem):
                                candidates.append((lem, 0.9))
                                continue

        # 2. HAIL MARY (Modern == Ancient?)
        if self.check_oracle(lemma):
            candidates.append((lemma, 1.0))

        # 3. HEURISTICS (Morphological Reconstruction)
        heuristics = self.heuristic_ancient_forms(lemma)
        for h in heuristics:
            if self.check_oracle(h):
                candidates.append((h, 0.95))

        # 4. COMPOUND DECONSTRUCTION (The Splitter)
        # e.g. προβαίνω -> βαίνω
        stems = self.lemmatizer.deconstruct_compound(lemma)
        for stem in stems:
            if self.check_oracle(stem):
                candidates.append((stem, 0.7))  # Lower confidence but valid root

        # 5. LEMMATIZATION OF INPUT (The Stanza Fix)
        # e.g. ωραία -> ωραίος
        lem_input = self.lemmatizer.lemmatize(lemma)
        if lem_input and lem_input != lemma:
            if self.check_oracle(lem_input):
                candidates.append((lem_input, 0.85))

        if not candidates:
            return ""

        # Sort by Score (Similarity / Confidence)
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def recursive_hunt(self, lemma, etym_text, master_lookup, depth=0):
        if depth > 2:
            return ""  # Prevent infinite loops

        # 1. Try standard extraction on current text
        direct_hit = self.extract_antecedent(lemma, etym_text)
        if direct_hit:
            return direct_hit

        # 2. If failed, look for Modern Parents in the text
        # Pattern: "< [ModernWord]" or "from [ModernWord]"
        # We scan for ANY word in the text that exists in master_lookup
        tokens = re.split(r"[^\w\u0370-\u03FF\u1F00-\u1FFF]+", etym_text)

        for token in tokens:
            clean_token = self.sanitize_greek(token)
            if len(clean_token) < 3:
                continue

            # Is this token a Modern Word in our dictionary?
            if clean_token in master_lookup:
                parent_entry = master_lookup[clean_token]
                parent_etym = parent_entry.get("etymology_text_el", "")

                # RECURSE
                ancestor = self.recursive_hunt(
                    clean_token, parent_etym, master_lookup, depth + 1
                )
                if ancestor:
                    return ancestor

        return ""

    def enrich_data(self, kelly_df, master_lookup):
        logger.info("Enriching via Hellenic Core (Smart Scan)...")

        lemma_col = "Lemma"
        # Ensure we find the right column
        if lemma_col not in kelly_df.columns:
            lemma_col = next(
                (c for c in kelly_df.columns if "Lemma" in c or "Λήμμα" in c), None
            )

        enrichment_data = []
        total = len(kelly_df)
        count = 0

        for lemma in kelly_df[lemma_col]:
            count += 1
            if count % 100 == 0:
                logger.info(f"Processing {count}/{total}...")

            entry = master_lookup.get(lemma)

            if entry:
                etym_text = entry.get("etymology_text_el", "")

                # Check for Parent (Compound Mining from Ingestion)
                parent = entry.get("parent_lemma")
                if parent and not etym_text:
                    # Use parent's etymology if we mined it
                    parent_entry = master_lookup.get(parent)
                    if parent_entry:
                        etym_text = parent_entry.get("etymology_text_el", "")
                        # Note: We still run extract_antecedent on the LEMMA (child),
                        # but Strategy 4 (Deconstruction) will catch the root.

                antecedent = self.recursive_hunt(lemma, etym_text, master_lookup)

                # --- DEFINITION HANDLING ---
                # English Senses
                senses_en = entry.get("senses_en", [])
                def_en_texts = [s["text"] for s in senses_en if isinstance(s, dict)]
                def_en_texts += [s for s in senses_en if isinstance(s, str)]
                def_en_str = "; ".join(def_en_texts[:2])

                # Greek Senses
                senses_el = entry.get("senses_el", [])
                def_el_texts = [s["text"] for s in senses_el if isinstance(s, dict)]
                def_el_texts += [s for s in senses_el if isinstance(s, str)]
                def_el_str = "; ".join(def_el_texts[:2])

                # Examples
                examples = entry.get("examples", [])
                examples_str = " || ".join(examples[:3])

                # Synonyms
                synonyms = ", ".join(entry.get("synonyms", [])[:3])

                enrichment_data.append(
                    {
                        "Lemma": lemma,
                        "AG_Antecedent": antecedent,
                        "Modern_Def": def_en_str,
                        "Greek_Def": def_el_str,
                        "Modern_Examples": examples_str,
                        "Synonyms": synonyms,
                        "Etymology_Snippet": etym_text[:100],
                    }
                )
            else:
                enrichment_data.append(
                    {
                        "Lemma": lemma,
                        "AG_Antecedent": "",
                        "Etymology_Snippet": "",
                        "Modern_Def": "",
                        "Greek_Def": "",
                        "Modern_Examples": "",
                        "Synonyms": "",
                    }
                )

        enriched_df = pd.DataFrame(enrichment_data)
        final_df = pd.merge(
            kelly_df, enriched_df, left_on=lemma_col, right_on="Lemma", how="left"
        )

        return final_df
