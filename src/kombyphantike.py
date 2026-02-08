from transliterate import translit
import pandas as pd
import spacy
import csv
import logging
import random
import numpy as np
import math
import re
import json
import os
import warnings
from datetime import datetime
from collections import Counter
from src.config import PROCESSED_DIR, DATA_DIR
from src.knot_loader import KnotLoader
from src.database import DatabaseManager
from src.models import ConstellationNode, ConstellationLink, ConstellationGraph

# Suppress warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Paths
KELLY_PATH = PROCESSED_DIR / "kelly.csv"
KNOTS_PATH = DATA_DIR / "knots.csv"
DECLENSIONS_PATH = PROCESSED_DIR / "noun_declensions.csv"
WORKSHEET_OUTPUT = DATA_DIR / "kombyphantike_worksheet.csv"
PROMPT_INSTRUCTION_FILE = DATA_DIR / "ai_instruction.txt"
PROGRESS_FILE = DATA_DIR / "user_progress.json"
SESSION_FILE = DATA_DIR / "current_session.json"
# PARADIGMS_PATH is no longer used

MORPH_MAP = {
    "Nom": "Nominative",
    "Gen": "Genitive",
    "Acc": "Accusative",
    "Voc": "Vocative",
    "Masc": "Masculine",
    "Fem": "Feminine",
    "Neut": "Neuter",
    "Sing": "Singular",
    "Plur": "Plural",
    "Pres": "Present",
    "Past": "Past",
    "Fut": "Future",
    "Act": "Active",
    "Pass": "Passive",
    "Ind": "Indicative",
    "Imp": "Imperative",
    "Sub": "Subjunctive",
    "Fin": "Finite",
    "Inf": "Infinitive",
    "Part": "Participle",
}


class KombyphantikeEngine:
    def __init__(self):
        print("Initializing the Curriculum Builder...")
        self.kelly = pd.read_csv(KELLY_PATH, dtype=str)
        self.knot_loader = KnotLoader()

        # Initialize Database Manager
        self.db = DatabaseManager()

        # DYNAMIC COLUMN DETECTION
        self.pos_col = next(
            (
                c
                for c in self.kelly.columns
                if "Part of speech" in c or "Μέρος του Λόγου" in c
            ),
            None,
        )
        if not self.pos_col:
            raise ValueError(
                "CRITICAL ERROR: Could not find 'Part of speech' column in Kelly data."
            )

        # Load Gender Data
        self.gender_map = {}
        if DECLENSIONS_PATH.exists():
            decls = pd.read_csv(DECLENSIONS_PATH, dtype=str).fillna("")
            self.gender_map = dict(zip(decls["Lemma"], decls["Gender"]))

        # Load User Progress
        self.progress = {}
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                self.progress = json.load(f)

        # Pre-processing Scores
        self.kelly["ID"] = pd.to_numeric(self.kelly["ID"], errors="coerce")
        self.kelly = self.kelly[self.kelly["ID"].notna()]
        max_rank = self.kelly["ID"].max()
        self.kelly["Freq_Score"] = 1 - (self.kelly["ID"] / max_rank)
        self.kelly["Similarity_Score"] = pd.to_numeric(
            self.kelly["Similarity_Score"], errors="coerce"
        ).fillna(0)

        # Tokenizer Models
        try:
            print("Loading Spacy Models...")
            self.nlp_el = spacy.load("el_core_news_lg")
            self.nlp_en = spacy.load("en_core_web_md")
        except Exception as e:
            print(
                f"CRITICAL WARNING: Spacy models missing. Tokenization will fail. {e}"
            )
            self.nlp_el = None
            self.nlp_en = None

        # Semantic Model Loading
        self.use_transformer = False
        self.vectors = None
        try:
            from sentence_transformers import SentenceTransformer, util
            import pickle

            print("Loading Neural Semantic Model...")
            self.model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
            self.use_transformer = True

            VECTORS_PATH = PROCESSED_DIR / "vectors.pkl"
            if VECTORS_PATH.exists():
                print("Loading pre-computed vectors...")
                with open(VECTORS_PATH, "rb") as f:
                    self.vectors = pickle.load(f)
        except Exception as e:
            print(f"SentenceTransformer not found or failed: {e}")
            if self.nlp_en:
                self.nlp = self.nlp_en
            else:
                try:
                    self.nlp = spacy.load("en_core_web_md")
                except:
                    print("Spacy missing. Semantic search will be degraded.")

    def transliterate_sentence(self, text: str) -> str:
        """
        Helper to transliterate a full Greek sentence to Latin characters.
        """
        if not text:
            return ""
        try:
            # "el" is the language code for Greek
            return translit(text, "el", reversed=True)
        except Exception as e:
            print(f"Transliteration Error: {e}")
            return text

    def _tokenize(self, text: str, lang: str) -> list:
        """
        Helper: Tokenizes text into structured objects.
        Links inflection paradigms if available in self.paradigms.
        """
        model = self.nlp_el if lang in ["el", "greek"] else self.nlp_en

        if not model:
            return []

        # Common auxiliaries to check if Spacy gets confused (e.g. lemma "είναι" -> "είμαι")
        AUXILIARIES = ["είμαι", "έχω"]

        doc = model(text)
        tokens = []
        for token in doc:
            # Process Morphology
            morph_dict = {}
            if hasattr(token.morph, "to_dict"):
                raw_morph = token.morph.to_dict()
                for k, v in raw_morph.items():
                    # Expand values if in map, else keep original
                    morph_dict[k] = MORPH_MAP.get(v, v)
            else:
                # Fallback for older Spacy versions
                morph_dict = {"raw": str(token.morph)}

            # Stringify for API safety (React crash prevention)
            morph_str = ", ".join(f"{k}: {v}" for k, v in morph_dict.items())

            token_dict = {
                "text": token.text,
                "lemma": token.lemma_,
                "pos": token.pos_,
                "tag": token.tag_,
                "dep": token.dep_,
                "is_alpha": token.is_alpha,
                "morphology": morph_str,
                "morphology_map": morph_dict,
                "transliteration": translit(token.text, "el", reversed=True)
                if lang in ["el", "greek"]
                else token.text,
            }

            # 1. Trust Spacy's lemma first
            lemma = token.lemma_
            paradigm = self.db.get_paradigm(lemma)

            # Fallback: Try lowercase lemma
            if paradigm is None:
                paradigm = self.db.get_paradigm(lemma.lower())

            # Metadata Injection from DB
            metadata = self.db.get_metadata(lemma)
            if not metadata:
                # Fallback: Look up by lower text
                metadata = self.db.get_metadata(token.text.lower())

            if metadata:
                # We prioritize Ancient Context and Etymology from DB.
                # Definitions are not explicitly available in DB unless in Ancient Context or derived.
                # The user instruction was specific about Ancient Context.
                # Note: 'definition' and 'semantic_shift' are lost unless we hack them back from somewhere else.
                # We will leave them empty or use fallback if critical, but for now we follow the DB stricture.

                token_dict["definition"] = "" # TODO: Restore from Kelly lookup if needed?
                token_dict["ancient_context"] = metadata.get("ancient_context", "")

                # Try to extract semantic shift from etymology or set empty?
                # The prompt did not specify how to handle semantic_shift replacement,
                # but removing word_map implies we lose access to the CSV 'Shift_Type' unless we query Kelly DF.
                # Since we still have self.kelly, we *could* look it up, but it's slow.
                token_dict["semantic_shift"] = ""

            # 2. Fallback / Correction for Auxiliary Irregulars
            # If paradigm missing OR lemma is suspiciously "είναι" (which is a form, not lemma)
            if paradigm is None or lemma in ["είναι", "ήταν"]:
                text_lower = token.text.lower()
                for aux in AUXILIARIES:
                    aux_paradigm = self.db.get_paradigm(aux)
                    if aux_paradigm:
                        # Paradigm is list of {form, tags}
                        forms = aux_paradigm

                        # Check if text exists as a form
                        found = any(f.get("form") == text_lower for f in forms)
                        if found:
                            paradigm = aux_paradigm
                            token_dict["lemma"] = aux
                            break

            # 3. Last Resort: Try looking up by text.lower() (if un-lemmatized input matches a lemma key)
            if paradigm is None:
                paradigm = self.db.get_paradigm(token.text.lower())

            token_dict["has_paradigm"] = paradigm is not None and len(paradigm) > 0
            token_dict["paradigm"] = paradigm

            tokens.append(token_dict)

            if paradigm:
                logger.info(f"Paradigm for {lemma}: {paradigm[:1]}")
        return tokens

    def tokenize_text(self, text: str, lang: str) -> list:
        """
        Public wrapper for tokenization.
        """
        if not text:
            return []
        return self._tokenize(text, lang)

    def save_progress(self):
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)

    def update_usage(self, lemma):
        today = datetime.now().strftime("%Y-%m-%d")
        if lemma not in self.progress:
            self.progress[lemma] = {"count": 0, "last_used": ""}
        self.progress[lemma]["count"] += 1
        self.progress[lemma]["last_used"] = today

    def get_usage_count(self, lemma):
        return self.progress.get(lemma, {}).get("count", 0)

    def update_knot_usage(self, knot_id):
        today = datetime.now().strftime("%Y-%m-%d")
        key = f"KNOT_{knot_id}"
        if key not in self.progress:
            self.progress[key] = {"count": 0, "last_used": ""}
        self.progress[key]["count"] += 1
        self.progress[key]["last_used"] = today

    def get_knot_usage(self, knot_id):
        return self.progress.get(f"KNOT_{knot_id}", {}).get("count", 0)

    def select_words(self, theme, target_word_count):
        print(f"Curating ~{target_word_count} words for theme: '{theme}'...")
        candidates = self.kelly.copy()

        # Semantic Scoring Logic
        if self.use_transformer:
            from sentence_transformers import util

            candidates["Target_Def"] = candidates["Greek_Def"].fillna(
                candidates["Modern_Def"]
            )
            theme_emb = self.model.encode(theme, convert_to_tensor=True)

            if self.vectors is not None:
                # Use pre-computed
                all_scores = util.cos_sim(theme_emb, self.vectors)[0].cpu().numpy()
                candidates["Semantic_Score"] = all_scores
                candidates = candidates[
                    candidates["Target_Def"].notna() & (candidates["Target_Def"] != "")
                ]
            else:
                # Live compute
                candidates = candidates[
                    candidates["Target_Def"].notna() & (candidates["Target_Def"] != "")
                ]
                definitions = candidates["Target_Def"].tolist()
                corpus_emb = self.model.encode(definitions, convert_to_tensor=True)
                scores = util.cos_sim(theme_emb, corpus_emb)[0].cpu().numpy()
                candidates["Semantic_Score"] = scores
        else:
            # Fallback to Spacy
            theme_doc = self.nlp(theme)
            candidates = candidates[candidates["Modern_Def"].notna()]
            candidates["Semantic_Score"] = candidates["Modern_Def"].apply(
                lambda text: (
                    theme_doc.similarity(self.nlp(text))
                    if isinstance(text, str)
                    else 0.0
                )
            )

        # Heritage Scoring
        def calc_heritage(row):
            shift = str(row["Shift_Type"])
            if "Direct Inheritance" in shift:
                return 1.0
            if "Morphological Evolution" in shift:
                return 0.8
            if "Semantic Shift" in shift:
                return 0.6
            return 0.2

        candidates["Heritage_Score"] = candidates.apply(calc_heritage, axis=1)

        # Weighted Formula
        candidates["Final_Score"] = (
            (0.10 * candidates["Freq_Score"])
            + (0.30 * candidates["Heritage_Score"])
            + (0.60 * candidates["Semantic_Score"])
        )

        pool = candidates.sort_values(by="Final_Score", ascending=False).head(
            target_word_count * 4
        )

        # POS Balancing
        limit_nouns = int(target_word_count * 0.40)
        limit_verbs = int(target_word_count * 0.30)
        limit_adjs = int(target_word_count * 0.20)
        limit_other = int(target_word_count * 0.10)

        final_selection = pd.concat(
            [
                pool[pool[self.pos_col].str.contains("Ουσιαστικό", na=False)].head(
                    limit_nouns
                ),
                pool[pool[self.pos_col].str.contains("Ρήμα", na=False)].head(
                    limit_verbs
                ),
                pool[pool[self.pos_col].str.contains("Επίθετο", na=False)].head(
                    limit_adjs
                ),
                pool[
                    pool[self.pos_col].str.contains(
                        "Επίρρημα|Πρόθεση|Σύνδεσμος", na=False
                    )
                ].head(limit_other),
            ]
        )

        # Ensure Verb count
        current_verbs = final_selection[
            final_selection[self.pos_col].str.contains("Ρήμα", na=False)
        ]
        if len(current_verbs) < limit_verbs:
            needed = limit_verbs - len(current_verbs)
            print(f"Injecting {needed} high-freq verbs...")
            filler_verbs = (
                self.kelly[self.kelly[self.pos_col].str.contains("Ρήμα", na=False)]
                .sort_values("Freq_Score", ascending=False)
                .head(needed)
            )
            final_selection = pd.concat([final_selection, filler_verbs])

        return final_selection

    def select_strategic_knots(self, words_df, target_knot_count):
        knot_counts = Counter()
        knot_map = {}

        for _, word in words_df.iterrows():
            lemma = word["Lemma"]
            pos = str(word[self.pos_col])
            target_pos = ""
            if "Ουσιαστικό" in pos:
                target_pos = "Noun"
            elif "Ρήμα" in pos:
                target_pos = "Verb"
            elif "Επίθετο" in pos:
                target_pos = "Adjective"
            if not target_pos:
                continue

            for _, knot in self.knot_loader.knots.iterrows():
                if knot["POS_Tag"] != target_pos:
                    continue
                if not knot["Regex_Ending"]:
                    continue

                if target_pos == "Noun" and knot.get("Morpho_Constraint"):
                    # Paranoid cast to string to prevent NoneType error
                    word_gender = str(self.gender_map.get(lemma, "")).strip()
                    knot_gender = str(knot["Morpho_Constraint"])

                    if word_gender and knot_gender and word_gender not in knot_gender:
                        continue

                regex = self.knot_loader.construct_regex(knot["Regex_Ending"])
                try:
                    if re.search(regex, lemma):
                        knot_counts[knot["Knot_ID"]] += 1
                        knot_map[knot["Knot_ID"]] = knot
                        if "Example_Word" in knot and knot["Example_Word"] == lemma:
                            knot_counts[knot["Knot_ID"]] += 10
                except:
                    continue

        num_morpho = math.ceil(target_knot_count * 0.7)
        num_syntax = target_knot_count - num_morpho

        # Prioritize knots with least fatigue
        candidates = []
        for kid, _ in knot_counts.most_common():
            candidates.append(knot_map[kid])
        candidates.sort(key=lambda k: self.get_knot_usage(k["Knot_ID"]))

        top_morpho = []
        parent_counts = Counter()
        for knot in candidates:
            parent = knot["Parent_Concept"]
            if parent_counts[parent] < 2:
                top_morpho.append(knot)
                parent_counts[parent] += 1
            if len(top_morpho) >= num_morpho:
                break

        syntax_pool = self.knot_loader.knots[
            self.knot_loader.knots["POS_Tag"] == "Syntax"
        ]
        if not syntax_pool.empty:
            syntax_list = [row for _, row in syntax_pool.iterrows()]
            syntax_list.sort(key=lambda k: self.get_knot_usage(k["Knot_ID"]))
            top_syntax = syntax_list[:num_syntax]
        else:
            top_syntax = []

        return top_morpho + top_syntax

    def _expand_word_pool(self, words_df):
        print("Expanding word pool with semantic relations...")
        new_rows = []
        original_lemmas = set(words_df["Lemma"].str.lower())

        # We limit the number of relations to avoid exploding the context window
        RELATIONS_LIMIT = 5

        for _, row in words_df.iterrows():
            lemma = row["Lemma"]
            if not lemma: continue

            relations = self.db.get_relations(lemma)
            # Flatten interesting relations
            candidates = []
            for rtype in ["synonyms", "related", "derived"]:
                 candidates.extend(relations.get(rtype, []))

            # Deduplicate and filter existing
            candidates = list(set(candidates))
            candidates = [c for c in candidates if c.lower() not in original_lemmas]

            # Limit
            candidates = candidates[:RELATIONS_LIMIT]

            for new_word in candidates:
                new_row = None

                # Get Metadata for POS
                meta = self.db.get_metadata(new_word)
                pos_raw = meta.get("pos", "noun") # Default to noun if unknown?

                # Map to Greek POS for consistency with generate_ai_instruction
                pos_greek = "Ουσιαστικό"
                if pos_raw and "verb" in pos_raw.lower(): pos_greek = "Ρήμα"
                elif pos_raw and "adj" in pos_raw.lower(): pos_greek = "Επίθετο"
                elif pos_raw and "adv" in pos_raw.lower(): pos_greek = "Επίρρημα"
                elif pos_raw and "noun" in pos_raw.lower(): pos_greek = "Ουσιαστικό"

                # Create a minimal row matching the schema required by generate_ai_instruction
                # It primarily needs 'Lemma' and self.pos_col
                new_row = row.copy() # Copy structure
                new_row["Lemma"] = new_word
                new_row[self.pos_col] = pos_greek
                # Clear other fields to avoid confusion
                new_row["Modern_Examples"] = ""
                new_row["Greek_Def"] = ""
                new_row["Modern_Def"] = ""

                # Try to fetch definition from DB if available
                if meta.get("definition"):
                     new_row["Modern_Def"] = meta["definition"]

                if new_row is not None:
                    new_rows.append(new_row)

                original_lemmas.add(new_word.lower()) # prevent re-adding

        if new_rows:
            expansion_df = pd.DataFrame(new_rows)
            # Combine and return
            print(f"Added {len(expansion_df)} related words to the pool.")
            return pd.concat([words_df, expansion_df], ignore_index=True)

        return words_df

    def compile_curriculum(self, theme, target_sentences):
        """
        THE CORE LOGIC.
        Returns a ConstellationGraph object.
        Does NOT save to files. This is used by both CLI and API.
        """
        SENTENCES_PER_KNOT = 4
        POOL_MULTIPLIER = 1.5

        target_knot_count = math.ceil(target_sentences / SENTENCES_PER_KNOT)
        target_word_count = int(target_sentences * POOL_MULTIPLIER)

        print(f"--- CONFIGURATION ---")
        print(f"Target Sentences: {target_sentences}")

        # 1. Index Corpus for Context
        print("Indexing Corpus for Cross-Reference...")
        corpus = []
        valid_examples = self.kelly[
            self.kelly["Modern_Examples"].notna()
            & (self.kelly["Modern_Examples"] != "")
        ]
        for ex_str in valid_examples["Modern_Examples"]:
            corpus.extend(str(ex_str).split(" || "))
        print(f"Corpus Size: {len(corpus)} sentences.")

        # 2. Select Words & Knots
        words_df = self.select_words(theme, target_word_count)

        # Expand Pool with Relations
        words_df = self._expand_word_pool(words_df)

        selected_knots = self.select_strategic_knots(words_df, target_knot_count)

        # 3. Build Session Data
        session_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "theme": theme,
            "words": words_df.to_dict(orient="records"),
            "knots": [
                k.to_dict() if hasattr(k, "to_dict") else k for k in selected_knots
            ],
        }

        # 4. Generate Instruction Text
        instruction_text = self.generate_ai_instruction(
            theme, target_sentences, words_df
        )

        # 5. Build Graph
        print(f"--- WEAVING CURRICULUM INTO CONSTELLATION ---")
        nodes = []
        links = []
        added_node_ids = set()

        # Center Node
        center_id = "center_theme"
        nodes.append(ConstellationNode(
            id=center_id,
            label=theme,
            type="theme",
            status="active",
            data={
                "instruction_text": instruction_text,
                "session_data": session_data,
                "words_df_json": words_df.to_dict(orient="records")
            }
        ))
        added_node_ids.add(center_id)

        used_heroes = set()

        for knot in selected_knots:
            self.update_knot_usage(knot["Knot_ID"])
            candidates = []

            # Find candidates for this knot
            if knot["Regex_Ending"]:
                regex = self.knot_loader.construct_regex(knot["Regex_Ending"])
                matches = words_df[
                    words_df["Lemma"].str.contains(regex, regex=True, na=False)
                ]

                if knot["POS_Tag"] == "Noun" and knot.get("Morpho_Constraint"):
                    target_gender = str(knot["Morpho_Constraint"])
                    valid_indices = []
                    for idx, row in matches.iterrows():
                        # Paranoid cast
                        g = str(self.gender_map.get(row["Lemma"], "")).strip()
                        if g and g in target_gender:
                            valid_indices.append(idx)
                    matches = matches.loc[valid_indices]
                candidates = matches["Lemma"].tolist()

            if not candidates:
                candidates = words_df["Lemma"].sample(min(5, len(words_df))).tolist()

            # Plural Check via Paradigms
            knot_desc = str(knot.get("Description", "")) + str(knot.get("Nuance", ""))
            if "plural" in knot_desc.lower() or "pl." in knot_desc.lower():
                candidates = [
                    c for c in candidates if self._check_paradigm_for_plural(c)
                ]

            candidates.sort(key=lambda w: self.get_usage_count(w))

            # Guard Clause: If candidates is still empty, skip this knot
            if not candidates:
                continue

            # Create Nodes
            for i in range(SENTENCES_PER_KNOT):
                row_data = None

                hero = next(
                    (c for c in candidates if c not in used_heroes),
                    candidates[i % len(candidates)],
                )
                used_heroes.add(hero)
                self.update_usage(hero)

                hero_row = words_df[words_df["Lemma"] == hero].iloc[0]

                # Contexts
                # Use DB for Ancient Context
                metadata = self.db.get_metadata(hero)
                ancient_ctx = metadata.get("ancient_context", "") if metadata else ""

                if not ancient_ctx or ancient_ctx.strip() == "":
                    ancient_ctx = "NO_CITATION_FOUND"

                modern_ctx = self._get_modern_context(hero, hero_row, corpus)

                row_data = {
                    "source_sentence": "",
                    "target_sentence": "",
                    "target_transliteration": "",
                    "knot_id": knot["Knot_ID"],
                    "parent_concept": knot["Parent_Concept"],
                    "nuance": knot["Nuance"],
                    "core_verb": hero if knot["POS_Tag"] == "Verb" else "",
                    "core_adj": hero if knot["POS_Tag"] == "Adjective" else "",
                    "optional_praepositio": "",
                    "optional_adverb": "",
                    "ancient_context": ancient_ctx,
                    "modern_context": modern_ctx,
                    "knot_definition": knot.get("Description", ""),
                    "knot_context": "",
                    "theme": f"{theme} (Focus: {hero})",
                }

                # Level 1 Node: The Word (Hero)
                word_id = f"lemma_{hero}"
                if word_id not in added_node_ids:
                    nodes.append(ConstellationNode(
                        id=word_id,
                        label=hero,
                        type="lemma",
                        status="pending",
                        data=hero_row.to_dict()
                    ))
                    added_node_ids.add(word_id)
                    # Link Center -> Word
                    links.append(ConstellationLink(source=center_id, target=word_id, value=1.0))

                # Level 2 Node: The Rule Instance
                rule_id = f"rule_{knot['Knot_ID']}_{hero}_{i}"
                rule_label = knot.get("Nuance") or knot.get("Description", "Rule")

                if row_data:
                    nodes.append(ConstellationNode(
                        id=rule_id,
                        label=rule_label,
                        type="rule",
                        status="pending",
                        data=row_data
                    ))
                    # Link Word -> Rule
                    links.append(ConstellationLink(source=word_id, target=rule_id, value=0.5))

        return ConstellationGraph(nodes=nodes, links=links)

    def _check_paradigm_for_plural(self, lemma):
        paradigm = self.db.get_paradigm(lemma)
        if not paradigm:
            return True  # Benefit of doubt

        # Paradigm is list of {form, tags}
        return any(
            "plural" in str(f.get("tags", [])).lower()
            # "raw_tags" is not currently returned by get_paradigm, but we could add it if needed.
            # get_paradigm returns "tags" which parses "tags_json".
            # If tags_json contained raw tags (it usually does as a list of strings), this works.
            for f in paradigm
        )

    def _get_modern_context(self, hero, hero_row, corpus):
        # 1. Own Examples
        raw_mod = hero_row.get("Modern_Examples", "")
        hero_context = []
        if pd.notna(raw_mod) and str(raw_mod).strip() not in ["", "nan"]:
            hero_context.extend(str(raw_mod).split(" || "))

        # 2. Cross-Mine Corpus
        hero_forms = {hero}
        paradigm = self.db.get_paradigm(hero)
        if paradigm:
            for f in paradigm:
                hero_forms.add(f["form"])

        found_count = 0
        for sentence in corpus:
            if found_count >= 3:
                break
            if sentence in hero_context:
                continue
            for form in hero_forms:
                if re.search(rf"\b{re.escape(form)}\b", sentence, re.IGNORECASE):
                    hero_context.append(sentence)
                    found_count += 1
                    break

        if hero_context:
            return " || ".join(hero_context[:5])

        # Fallbacks
        raw_def_el = hero_row.get("Greek_Def", "")
        if pd.notna(raw_def_el) and str(raw_def_el).strip() not in ["", "nan"]:
            return f"DEF (EL): {raw_def_el}"

        raw_def_en = hero_row.get("Modern_Def", "")
        if pd.notna(raw_def_en) and str(raw_def_en).strip() not in ["", "nan"]:
            return f"DEF (EN): {raw_def_en}"

        syns = hero_row.get("Synonyms", "")
        if pd.notna(syns) and str(syns).strip() not in ["", "nan"]:
            return f"SYN: {syns}"

        return "NO_CONTEXT_FOUND"

    def generate_ai_instruction(self, theme, count, words_df):
        pool_text = []
        for pos, group in words_df.groupby(self.pos_col):
            lemmas = ", ".join(group["Lemma"].tolist())
            clean_pos = (
                str(pos)
                .replace("Ουσιαστικό", "Nouns")
                .replace("Ρήμα", "Verbs")
                .replace("Επίθετο", "Adjectives")
                .replace("Επίρρημα", "Adverbs")
            )
            pool_text.append(f"**{clean_pos}**: {lemmas}")
        pool_string = "\n".join(pool_text)

        text = f"""
### SYSTEM OVERRIDE: KOMBYPHANTIKE MOBILE ENGINE ###

**ROLE:** You are the AI Engine for a high-level Greek Philology App.
**TASK:** Populate the provided JSON Data Structure with sentences.
**THEME:** {theme}

### THE RAW MATERIALS
You must prioritize these words in your sentences:
{pool_string}

### THE RULES OF ENGAGEMENT
1. **The Format:** You will receive a list of JSON objects (The Blueprint). You must return the SAME list, but with the `target_sentence` (Modern Greek), `source_sentence` (English), and `knot_context` fields filled.
2. **The Logic (The Knot):** Look at the `nuance` field in each row. The Greek sentence **MUST** demonstrate this specific grammar rule using the word in the `theme` field (The Hero Word).
3. **The Explanation (Knot Context):** For each sentence, write a 1-sentence explanation (`knot_context`) describing exactly how the Knot Rule was applied to the Hero word (e.g., 'Note how the stress moved to the ultimate syllable in the Genitive Plural').
4. **The Tone:**
   *   **Sophisticated but Concise:** These will appear on a mobile screen. Avoid overly long sentences.
   *   **Resonant:** Use the `ancient_context` field to inspire the meaning, but write modern, natural Greek.
5. **The Output:** Return **ONLY RAW JSON**. No Markdown formatting (```json), no conversational filler. Just the array.

### INPUT DATA TO PROCESS:
"""
        return text

    def _map_to_legacy_csv(self, rows):
        """Maps internal dictionary keys to the verbose CSV headers for local Excel use."""
        csv_rows = []
        for r in rows:
            csv_rows.append(
                {
                    "Source Sentence": r.get("source_sentence", ""),
                    "Greek Translation / Target Sentence": r.get("target_sentence", ""),
                    "Knot ID": r.get("knot_id", ""),
                    "Parent Concept": r.get("parent_concept", ""),
                    "The Specific Sub-Condition / Nuance": r.get("nuance", ""),
                    "Core Vocab (Verb)": r.get("core_verb", ""),
                    "Core Vocab (Adjective)": r.get("core_adj", ""),
                    "Optional Core Vocab (Praepositio)": r.get(
                        "optional_praepositio", ""
                    ),
                    "Optional Core Vocab (Adverb)": r.get("optional_adverb", ""),
                    "Ancient Context": r.get("ancient_context", ""),
                    "Modern Context": r.get("modern_context", ""),
                    "Knot Context": r.get("knot_context", ""),
                    "Theme": r.get("theme", ""),
                }
            )
        return csv_rows

    def generate_worksheet(self, theme, target_sentences):
        """
        CLI Entry Point.
        Generates data, saves to CSV, saves prompt to TXT.
        """
        # 1. Compile Graph
        graph = self.compile_curriculum(theme, target_sentences)

        # 2. Extract Data from Graph
        center_node = next(n for n in graph.nodes if n.type == "theme")
        instruction_text = center_node.data["instruction_text"]
        session_data = center_node.data["session_data"]

        # Extract rows from rule nodes
        worksheet_data = []
        for n in graph.nodes:
            if n.type == "rule" and n.data:
                worksheet_data.append(n.data)

        # 3. Save Session
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        # 4. Map to CSV & Save
        csv_rows = self._map_to_legacy_csv(worksheet_data)
        df = pd.DataFrame(csv_rows)
        # Ensure all columns exist
        cols = [
            "Source Sentence",
            "Greek Translation / Target Sentence",
            "Knot ID",
            "Parent Concept",
            "The Specific Sub-Condition / Nuance",
            "Core Vocab (Verb)",
            "Core Vocab (Adjective)",
            "Optional Core Vocab (Praepositio)",
            "Optional Core Vocab (Adverb)",
            "Ancient Context",
            "Modern Context",
            "Knot Context",
            "Theme",
        ]

        df = df.reindex(columns=cols, fill_value="")
        df.to_csv(
            WORKSHEET_OUTPUT, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL
        )

        self.save_progress()

        # 5. Save Prompt
        with open(PROMPT_INSTRUCTION_FILE, "w", encoding="utf-8") as f:
            f.write(instruction_text)

        print(f"Worksheet generated: {WORKSHEET_OUTPUT}")


if __name__ == "__main__":
    engine = KombyphantikeEngine()
    t = input("Enter Theme: ")
    try:
        c = int(input("Enter number of sentences (e.g. 60): "))
    except ValueError:
        c = 60
    engine.generate_worksheet(t, c)
