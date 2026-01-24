import pandas as pd
import spacy
import csv
import logging
import random
import numpy as np
import math
import sentence_transformers
import re
import json
import os
import warnings
import textwrap
from datetime import datetime
from collections import Counter
from src.config import PROCESSED_DIR, DATA_DIR
from src.knot_loader import KnotLoader

# Suppress warnings
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

KELLY_PATH = PROCESSED_DIR / "kelly.csv"
KNOTS_PATH = DATA_DIR / "knots.csv"
DECLENSIONS_PATH = PROCESSED_DIR / "noun_declensions.csv"
WORKSHEET_OUTPUT = DATA_DIR / "kombyphantike_worksheet.csv"
PROMPT_INSTRUCTION_FILE = DATA_DIR / "ai_instruction.txt"
PROGRESS_FILE = DATA_DIR / "user_progress.json"
SESSION_FILE = DATA_DIR / "current_session.json"
PARADIGMS_PATH = PROCESSED_DIR / "paradigms.json"


class KombyphantikeEngine:
    def __init__(self):
        print("Initializing the Curriculum Builder...")
        self.kelly = pd.read_csv(KELLY_PATH, dtype=str)
        self.knot_loader = KnotLoader()

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
            print("CRITICAL ERROR: Could not find 'Part of speech' column.")
            exit()

        # Load Gender Data
        self.gender_map = {}
        if DECLENSIONS_PATH.exists():
            decls = pd.read_csv(DECLENSIONS_PATH, dtype=str)
            self.gender_map = dict(zip(decls["Lemma"], decls["Gender"]))

        # Load User Progress
        self.progress = {}
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                self.progress = json.load(f)

        # Load Paradigms for Cross-Mining
        self.paradigms = {}
        if PARADIGMS_PATH.exists():
            with open(PARADIGMS_PATH, "r", encoding="utf-8") as f:
                self.paradigms = json.load(f)

        # PRE-PROCESSING SCORES
        self.kelly["ID"] = pd.to_numeric(self.kelly["ID"], errors="coerce")
        self.kelly = self.kelly[self.kelly["ID"].notna()]
        max_rank = self.kelly["ID"].max()
        self.kelly["Freq_Score"] = 1 - (self.kelly["ID"] / max_rank)
        self.kelly["Similarity_Score"] = pd.to_numeric(
            self.kelly["Similarity_Score"], errors="coerce"
        ).fillna(0)

        self.use_transformer = False
        self.vectors = None
        try:
            from sentence_transformers import SentenceTransformer, util
            import pickle

            print("Loading Neural Semantic Model...")
            # If you want to use local:
            # self.model = SentenceTransformer('./models/mpnet')
            # If you want to use cache (which you downloaded via git lfs):
            self.model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
            self.use_transformer = True

            VECTORS_PATH = PROCESSED_DIR / "vectors.pkl"
            if VECTORS_PATH.exists():
                print("Loading pre-computed vectors...")
                with open(VECTORS_PATH, "rb") as f:
                    self.vectors = pickle.load(f)
        except Exception as e:
            print(f"SentenceTransformer not found: {e}")
            try:
                self.nlp = spacy.load("en_core_web_md")
            except:
                print("Spacy missing.")
                exit()

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

    def calculate_heritage_score(self, row):
        shift = str(row["Shift_Type"])
        if "Direct Inheritance" in shift:
            return 1.0
        if "Morphological Evolution" in shift:
            return 0.8
        if "Semantic Shift" in shift:
            return 0.6
        return 0.2

    def select_words(self, theme, target_word_count):
        print(f"Curating ~{target_word_count} words for theme: '{theme}'...")
        candidates = self.kelly.copy()

        if self.use_transformer:
            from sentence_transformers import util

            # Prioritize Greek Def, fallback to English
            candidates["Target_Def"] = candidates["Greek_Def"].fillna(
                candidates["Modern_Def"]
            )

            theme_emb = self.model.encode(theme, convert_to_tensor=True)

            if self.vectors is not None:
                # Use pre-computed vectors (aligned with self.kelly)
                # Compute scores for ALL rows
                all_scores = util.cos_sim(theme_emb, self.vectors)[0].cpu().numpy()

                # Assign to candidates (which is a copy of self.kelly)
                # Since candidates is a direct copy, indices and order match self.vectors
                candidates["Semantic_Score"] = all_scores

                # Filter candidates after scoring
                candidates = candidates[
                    candidates["Target_Def"].notna() & (candidates["Target_Def"] != "")
                ]
            else:
                candidates = candidates[
                    candidates["Target_Def"].notna() & (candidates["Target_Def"] != "")
                ]
                definitions = candidates["Target_Def"].tolist()

                corpus_emb = self.model.encode(
                    definitions, convert_to_tensor=True, show_progress_bar=True
                )
                scores = util.cos_sim(theme_emb, corpus_emb)[0].cpu().numpy()
                candidates["Semantic_Score"] = scores
        else:
            theme_doc = self.nlp(theme)

            def get_score(text):
                if not isinstance(text, str) or text == "nan":
                    return 0.0
                return theme_doc.similarity(self.nlp(text))

            candidates = candidates[candidates["Modern_Def"].notna()]
            candidates["Semantic_Score"] = candidates["Modern_Def"].apply(get_score)

        candidates["Heritage_Score"] = candidates.apply(
            self.calculate_heritage_score, axis=1
        )

        candidates["Final_Score"] = (
            (0.10 * candidates["Freq_Score"])
            + (0.30 * candidates["Heritage_Score"])
            + (0.60 * candidates["Semantic_Score"])
        )

        pool = candidates.sort_values(by="Final_Score", ascending=False).head(
            target_word_count * 4
        )

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
                    word_gender = self.gender_map.get(lemma, "")
                    knot_gender = knot["Morpho_Constraint"]
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

    def compile_curriculum_data(self, theme, target_sentences):
        """
        Generates the raw curriculum data using standardized internal keys.
        This separates the data logic from the presentation layer (CSV/JSON).
        """
        SENTENCES_PER_KNOT = 4
        POOL_MULTIPLIER = 1.5

        target_knot_count = math.ceil(target_sentences / SENTENCES_PER_KNOT)
        target_word_count = int(target_sentences * POOL_MULTIPLIER)

        print(f"--- CONFIGURATION ---")
        print(f"Target Sentences: {target_sentences}")

        # 1. BUILD CORPUS FOR CROSS-MINING
        print("Indexing Corpus for Cross-Reference...")
        corpus = []
        # Optimization: Filter out empty examples
        valid_examples = self.kelly[
            self.kelly["Modern_Examples"].notna()
            & (self.kelly["Modern_Examples"] != "")
        ]
        for ex_str in valid_examples["Modern_Examples"]:
            sentences = str(ex_str).split(" || ")
            for s in sentences:
                corpus.append(s)
        print(f"Corpus Size: {len(corpus)} sentences.")

        words_df = self.select_words(theme, target_word_count)
        selected_knots = self.select_strategic_knots(words_df, target_knot_count)

        # Build Session Data
        session_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "theme": theme,
            "words": words_df.to_dict(orient="records"),
            "knots": [
                k.to_dict() if hasattr(k, "to_dict") else k for k in selected_knots
            ],
        }

        rows = []
        print(f"--- WEAVING CURRICULUM ---")

        used_heroes = set()

        for knot in selected_knots:
            self.update_knot_usage(knot["Knot_ID"])

            candidates = []
            if knot["Regex_Ending"]:
                regex = self.knot_loader.construct_regex(knot["Regex_Ending"])
                matches = words_df[
                    words_df["Lemma"].str.contains(regex, regex=True, na=False)
                ]
                candidates = matches["Lemma"].tolist()

                if knot["POS_Tag"] == "Noun" and knot.get("Morpho_Constraint"):
                    target_gender = knot["Morpho_Constraint"]
                    valid_indices = []
                    for idx, row in matches.iterrows():
                        g = self.gender_map.get(row["Lemma"])
                        if g and g in target_gender:
                            valid_indices.append(idx)
                    matches = matches.loc[valid_indices]

                candidates = matches["Lemma"].tolist()

            if not candidates:
                candidates = words_df["Lemma"].sample(min(5, len(words_df))).tolist()

            knot_desc = str(knot.get("Description", "")) + str(knot.get("Nuance", ""))
            requires_plural = (
                "plural" in knot_desc.lower() or "pl." in knot_desc.lower()
            )

            if requires_plural:
                valid_candidates = (
                    []
                )  # this will be enlarged as valid candidates require more filters
                for cand in candidates:
                    if cand in self.paradigms:
                        forms = self.paradigms[cand]
                        # Check if any form has 'plural' or 'πληθυντικός' tag
                        has_plural = any(
                            "plural" in str(f.get("tags", [])).lower()
                            or "πληθυντικός" in str(f.get("raw_tags", [])).lower()
                            for f in forms
                        )
                        if has_plural:
                            valid_candidates.append(cand)
                    else:
                        # If no paradigm found, keep it (benefit of doubt)
                        valid_candidates.append(cand)

                if valid_candidates:
                    candidates = valid_candidates

            candidates.sort(key=lambda w: self.get_usage_count(w))

            for i in range(SENTENCES_PER_KNOT):
                hero = ""
                for cand in candidates:
                    if cand not in used_heroes:
                        hero = cand
                        break
                if not hero:
                    hero = candidates[i % len(candidates)]

                used_heroes.add(hero)
                self.update_usage(hero)

                hero_row = words_df[words_df["Lemma"] == hero].iloc[0]

                # ANCIENT CONTEXT
                raw_ctx = hero_row.get("Ancient_Context", "")
                ancient_ctx = (
                    "NO_CITATION_FOUND"
                    if pd.isna(raw_ctx) or str(raw_ctx).strip() == ""
                    else raw_ctx
                )

                # MODERN CONTEXT (CROSS-MINING)
                modern_ctx = ""

                # 1. Own Examples
                raw_mod = hero_row.get("Modern_Examples", "")
                hero_context = []
                if pd.notna(raw_mod) and str(raw_mod).strip() not in ["", "nan"]:
                    hero_context.extend(str(raw_mod).split(" || "))

                # 2. Cross-Mine
                # Get forms
                hero_forms = set([hero])
                if hero in self.paradigms:
                    for f in self.paradigms[hero]:
                        hero_forms.add(f["form"])

                # Scan Corpus (Limit to 3 extra)
                found_count = 0
                for sentence in corpus:
                    if found_count >= 3:
                        break
                    if sentence in hero_context:
                        continue  # Skip dupes

                    # Regex Word Boundary Check
                    for form in hero_forms:
                        if re.search(
                            rf"\b{re.escape(form)}\b", sentence, re.IGNORECASE
                        ):
                            hero_context.append(sentence)
                            found_count += 1
                            break

                # Fallback to Definition if empty
                if hero_context:
                    modern_ctx = " || ".join(hero_context[:5])
                else:
                    # 2. Fallback to Greek Def
                    raw_def_el = hero_row.get("Greek_Def", "")
                    if pd.notna(raw_def_el) and str(raw_def_el).strip() not in [
                        "",
                        "nan",
                    ]:
                        modern_ctx = f"DEF (EL): {raw_def_el}"
                    else:
                        # 3. Fallback to English Def
                        raw_def_en = hero_row.get("Modern_Def", "")
                        if pd.notna(raw_def_en) and str(raw_def_en).strip() not in [
                            "",
                            "nan",
                        ]:
                            modern_ctx = f"DEF (EN): {raw_def_en}"
                        else:
                            # 4. Fallback to Synonyms
                            syns = hero_row.get("Synonyms", "")
                            if pd.notna(syns) and str(syns).strip() not in ["", "nan"]:
                                modern_ctx = f"SYN: {syns}"
                            else:
                                modern_ctx = "NO_CONTEXT_FOUND"

                core_v = hero if knot["POS_Tag"] == "Verb" else ""
                core_adj = hero if knot["POS_Tag"] == "Adjective" else ""

                row = {
                    "source_sentence": "",
                    "target_sentence": "",
                    "knot_id": knot["Knot_ID"],
                    "parent_concept": knot["Parent_Concept"],
                    "nuance": knot["Nuance"],
                    "core_verb": core_v,
                    "core_adj": core_adj,
                    "optional_praepositio": "",
                    "optional_adverb": "",
                    "ancient_context": ancient_ctx,
                    "modern_context": modern_ctx,
                    "theme": f"{theme} (Focus: {hero})",
                }
                rows.append(row)

        return {
            "worksheet_data": rows,
            "session_data": session_data,
            "words_df": words_df,
        }

    # Deprecated/Wrapper for backward compatibility if needed, but updated to use new data structure
    def compile_curriculum(self, theme, target_sentences):
        result = self.compile_curriculum_data(theme, target_sentences)

        # We need to map the data back to legacy keys for the old API signature if it expects it,
        # but since we are refactoring, we will update the usage.

        # Generate instruction using default JSON mode
        instruction_text = self.generate_ai_instruction(
            theme, target_sentences, result["words_df"], output_format="json"
        )

        return {
            "worksheet_data": result["worksheet_data"],
            "instruction_text": instruction_text,
            "session_data": result["session_data"]
        }

    def _map_to_legacy_csv(self, rows):
        """Maps internal dictionary keys to the verbose CSV headers."""
        csv_rows = []
        for r in rows:
            csv_rows.append({
                "Source Sentence": r.get("source_sentence", ""),
                "Greek Translation / Target Sentence": r.get("target_sentence", ""),
                "Knot ID": r.get("knot_id", ""),
                "Parent Concept": r.get("parent_concept", ""),
                "The Specific Sub-Condition / Nuance": r.get("nuance", ""),
                "Core Vocab (Verb)": r.get("core_verb", ""),
                "Core Vocab (Adjective)": r.get("core_adj", ""),
                "Optional Core Vocab (Praepositio)": r.get("optional_praepositio", ""),
                "Optional Core Vocab (Adverb)": r.get("optional_adverb", ""),
                "Ancient Context": r.get("ancient_context", ""),
                "Modern Context": r.get("modern_context", ""),
                "Theme": r.get("theme", ""),
            })
        return csv_rows

    def generate_worksheet(self, theme, target_sentences):
        result = self.compile_curriculum_data(theme, target_sentences)

        # Generate CSV-specific instruction
        instruction_text = self.generate_ai_instruction(
            theme, target_sentences, result["words_df"], output_format="csv"
        )

        session_data = result["session_data"]
        # Save Session
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        # Map to Legacy CSV format for saving
        csv_rows = self._map_to_legacy_csv(result["worksheet_data"])

        df = pd.DataFrame(csv_rows)
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
            "Theme",
        ]
        for c in cols:
            if c not in df.columns:
                df[c] = ""

        df = df[cols]
        df.to_csv(
            WORKSHEET_OUTPUT, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL
        )

        self.save_progress()

        with open(PROMPT_INSTRUCTION_FILE, "w", encoding="utf-8") as f:
            f.write(instruction_text)
        print(f"Worksheet generated: {WORKSHEET_OUTPUT}")

    def generate_ai_instruction(self, theme, count, words_df, output_format="json"):
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

        base_text = f"""
### SYSTEM DESIGNATION: DIGITAL HUMANITIES RESEARCH ASSOCIATE ###

**ROLE:** You are the Research Assistant to the Lead Classical Philologist of Project Kombyphantike.
**CONTEXT:** You are operating within a strict Python/Google Sheets data pipeline. The user (Lead Philologist) has established a scalable learning tool that bridges Ancient and Modern Greek.
**OPERATIONAL BOUNDARIES:** Your output will be parsed programmatically.

**THEME:** **{theme}**
**TASK:** Interpolate missing data for the attached data ({count} items).

### THE RESOURCE POOL (SEMANTIC INGREDIENTS)
**Instruction:** You must draw from this pool to construct natural, high-register sentences. Do not force "garbage" sentences; use these words to create meaningful scenarios relevant to the Theme.
{pool_string}

### EXECUTION PROTOCOL (STRICT COMPLIANCE)
"""

        if output_format == "json":
            protocol_text = """
1.  **PROTOCOL: DATA IMMUTABILITY (CRITICAL)**
    * **READ-ONLY ZONES:** You are strictly FORBIDDEN from modifying, deleting, or summarizing the following keys: `knot_id`, `parent_concept`, `ancient_context`, `modern_context`.
    * **PRESERVATION:** You must echo these keys back *exactly* as they appear in the input.

2.  **PROTOCOL: THE LIVING BRIDGE (CONTENT GENERATION)**
    * **The Hero Word:** Identify the hero word in the 'theme' key.
    * **The Syntax:** Construct a Modern Greek sentence (`target_sentence`) that strictly follows the morphological rule in the `knot_id` key.
    * **The Semantics:** The sentence should be colloquial yet educated.
    * **Resource Integration:** You MUST incorporate at least **2 additional words** from the Resource Pool into the sentence.

3.  **PROTOCOL: ANNOTATION**
    * **The Knot Note:** In the `nuance` key, RETAIN the original text and APPEND a note in brackets: `... [APPLIED: Genitive Plural for stress shift]`.
    * **Vocab Logging:** You MUST populate `core_verb` and `core_adj` with the exact words you used from the pool.

4.  **PROTOCOL: OUTPUT FORMAT**
    * Return **ONLY** a valid JSON list of objects.
    * Each object must have the following keys:
      - "source_sentence" (The English sentence)
      - "target_sentence" (The Modern Greek translation)
      - "knot_id" (Keep original)
      - "parent_concept" (Keep original)
      - "nuance" (Append your grammatical note here)
      - "core_verb" (Keep or Update)
      - "core_adj" (Keep or Update)
      - "optional_praepositio"
      - "optional_adverb"
      - "ancient_context" (Keep original)
      - "modern_context" (Keep original)
      - "theme" (Keep original)
    * **No Markdown/Chatter:** Do not provide conversational filler. Do not use markdown code blocks (```json). Just raw JSON.
"""
        else:
            # Legacy CSV Prompt
            protocol_text = """
1.  **PROTOCOL: DATA IMMUTABILITY (CRITICAL)**
    * **READ-ONLY ZONES:** You are strictly FORBIDDEN from modifying, deleting, or summarizing the following columns: `Knot ID`, `Parent Concept`, `The Specific Sub-Condition / Nuance`, `Ancient Context`, `Modern Context`.
    * **PRESERVATION:** You must echo these columns back *exactly* as they appear.

2.  **PROTOCOL: THE LIVING BRIDGE (CONTENT GENERATION)**
    * **The Hero Word:** Identify the hero word in the 'Theme' column.
    * **The Syntax:** Construct a Modern Greek sentence (`Greek Translation`) that strictly follows the morphological rule in the `Knot ID` column.
    * **The Semantics:** The sentence should be colloquial yet educated.
    * **Resource Integration:** You MUST incorporate at least **2 additional words** from the Resource Pool into the sentence.

3.  **PROTOCOL: ANNOTATION**
    * **The Knot Note:** In the `The Specific Sub-Condition / Nuance` column, RETAIN the original text and APPEND a note in brackets explaining your grammatical decision.
    * **Vocab Logging:** You MUST populate the `Core Vocab (Verb)` and `Core Vocab (Adjective)` columns.

4.  **PROTOCOL: OUTPUT FORMAT**
    * Return **ONLY** the raw CSV code block.
    * **Quote All Cells:** `"Sentence","Translation","Knot [Note]","Verb","Adj",...`
    * **No Markdown/Chatter:** Do not provide conversational filler before or after the CSV block.
"""

        return base_text + protocol_text


if __name__ == "__main__":
    engine = KombyphantikeEngine()
    t = input("Enter Theme: ")
    try:
        c = int(input("Enter number of sentences (e.g. 60): "))
    except ValueError:
        c = 60
    engine.generate_worksheet(t, c)
