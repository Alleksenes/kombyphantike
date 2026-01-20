import pandas as pd
import numpy as np
import math, spacy, logging, random, re, json, os, warnings
from datetime import datetime
from collections import Counter
from src.config import PROCESSED_DIR, DATA_DIR
from src.knot_loader import KnotLoader

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

        # PRE-PROCESSING SCORES
        self.kelly["ID"] = pd.to_numeric(self.kelly["ID"], errors="coerce")
        self.kelly = self.kelly[self.kelly["ID"].notna()]
        max_rank = self.kelly["ID"].max()
        self.kelly["Freq_Score"] = 1 - (self.kelly["ID"] / max_rank)
        self.kelly["Similarity_Score"] = pd.to_numeric(
            self.kelly["Similarity_Score"], errors="coerce"
        ).fillna(0)

        try:
            from sentence_transformers import SentenceTransformer, util

            print("Loading Neural Semantic Model...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self.use_transformer = True
        except:
            print("SentenceTransformer not found. Falling back to SpaCy.")
            try:
                self.nlp = spacy.load("en_core_web_md")
                self.use_transformer = False
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

    # --- KNOT FATIGUE ---
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
            candidates = candidates[candidates["Modern_Def"].notna()]
            definitions = candidates["Modern_Def"].tolist()
            from sentence_transformers import util

            theme_emb = self.model.encode(theme, convert_to_tensor=True)
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
                    import re

                    if re.search(regex, lemma):
                        knot_counts[knot["Knot_ID"]] += 1
                        knot_map[knot["Knot_ID"]] = knot
                        if "Example_Word" in knot and knot["Example_Word"] == lemma:
                            knot_counts[knot["Knot_ID"]] += 10
                except:
                    continue

        num_morpho = math.ceil(target_knot_count * 0.7)
        num_syntax = target_knot_count - num_morpho

        # Sort Morpho Knots by Fatigue (Least Used First)
        candidates = []
        for kid, _ in knot_counts.most_common():
            candidates.append(knot_map[kid])

        candidates.sort(key=lambda k: self.get_knot_usage(k["Knot_ID"]))

        # Diversity Filter (Max 2 per Parent)
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
            # Sort syntax by fatigue too
            syntax_list = [row for _, row in syntax_pool.iterrows()]
            syntax_list.sort(key=lambda k: self.get_knot_usage(k["Knot_ID"]))
            top_syntax = syntax_list[:num_syntax]
        else:
            top_syntax = []

        return top_morpho + top_syntax

    def compile_curriculum(self, theme, target_sentences):
        SENTENCES_PER_KNOT = 4
        POOL_MULTIPLIER = 1.5

        target_knot_count = math.ceil(target_sentences / SENTENCES_PER_KNOT)
        target_word_count = int(target_sentences * POOL_MULTIPLIER)

        print(f"--- CONFIGURATION ---")
        print(f"Target Sentences: {target_sentences}")

        words_df = self.select_words(theme, target_word_count)
        selected_knots = self.select_strategic_knots(words_df, target_knot_count)

        # Build Session Data
        session_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "theme": theme,
            "words": words_df.to_dict(orient="records"),
            "knots": [k.to_dict() for k in selected_knots],
        }

        rows = []
        print(f"--- WEAVING CURRICULUM ---")

        used_heroes = set()

        for knot in selected_knots:
            self.update_knot_usage(knot["Knot_ID"])  # TRACK KNOT FATIGUE

            candidates = []
            if knot["Regex_Ending"]:
                regex = self.knot_loader.construct_regex(knot["Regex_Ending"])
                import re

                matches = words_df[
                    words_df["Lemma"].str.contains(regex, regex=True, na=False)
                ]

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

                # STRICT CONTEXT FETCH
                hero_row = words_df[words_df["Lemma"] == hero].iloc[0]
                raw_ctx = hero_row.get("Ancient_Context", "")

                # ANTI-HALLUCINATION
                if pd.isna(raw_ctx) or str(raw_ctx).strip() == "":
                    ancient_ctx = "NO_CITATION_FOUND"
                else:
                    ancient_ctx = raw_ctx

                core_v = hero if knot["POS_Tag"] == "Verb" else ""
                core_adj = hero if knot["POS_Tag"] == "Adjective" else ""

                row = {
                    "Source Sentence": "",
                    "Greek Translation / Target Sentence": "",
                    "Knot ID": knot["Knot_ID"],
                    "Parent Concept": knot["Parent_Concept"],
                    "The Specific Sub-Condition / Nuance": knot["Nuance"],
                    "Core Vocab (Verb)": core_v,
                    "Core Vocab (Adjective)": core_adj,
                    "Optional Core Vocab (Praepositio)": "",
                    "Optional Core Vocab (Adverb)": "",
                    "Ancient Context": ancient_ctx,
                    "Theme": f"{theme} (Focus: {hero})",
                }
                rows.append(row)

        instruction_text = self.generate_ai_instruction(theme, target_sentences, words_df)

        return {
            "worksheet_data": rows,
            "instruction_text": instruction_text,
            "session_data": session_data
        }

    def generate_worksheet(self, theme, target_sentences):
        result = self.compile_curriculum(theme, target_sentences)
        rows = result["worksheet_data"]
        instruction_text = result["instruction_text"]
        session_data = result["session_data"]

        # Save Session
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        df = pd.DataFrame(rows)
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
            "Theme",
        ]
        for c in cols:
            if c not in df.columns:
                df[c] = ""

        df = df[cols]
        df.to_csv(WORKSHEET_OUTPUT, index=False, encoding="utf-8-sig")

        self.save_progress()

        with open(PROMPT_INSTRUCTION_FILE, "w", encoding="utf-8") as f:
            f.write(instruction_text)
        print(f"Worksheet generated: {WORKSHEET_OUTPUT}")

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
### MISSION PROFILE: PROJECT KOMBYPHANTIKE ###

**ROLE:** Diachronic Greek Philologist & Logic Weaver.
**THEME:** **{theme}**
**GOAL:** Complete the attached CSV worksheet ({count} rows).

### THE RESOURCE POOL (YOUR INGREDIENTS)
You have access to this curated vocabulary. **Use these words to fill the blank slots.**
{pool_string}

### EXECUTION PROTOCOL FOR EACH ROW

1.  **IDENTIFY THE HERO:** Look at the 'Theme' column.
2.  **CHECK THE ANCIENT CONTEXT:**
    *   Column 'Ancient Context' contains the citation.
    *   **IF "NO_CITATION_FOUND":** Do NOT invent a citation.
    *   **IF CITATION EXISTS:** Use it to inform the tone.
3.  **OBEY THE KNOT (CRITICAL):**
    *   Read 'The Specific Sub-Condition'. The sentence must demonstrate this rule using the Hero word.
4.  **SELECT SUPPORT:** 
    *   Pick words from the Pool.
    *   *If the Pool lacks a fitting word, YOU MAY INTRODUCE A NEW ONE.*
5.  **FILL THE ROW:**
    *   **Greek Translation:** The Modern Greek sentence.
    *   **Source Sentence:** The English translation.
    *   **FORMATTING:** Wrap sentences in **DOUBLE QUOTES ("")** if they contain commas.

**OUTPUT:** Provide the full CSV code block.
"""
        return text


if __name__ == "__main__":
    engine = KombyphantikeEngine()
    t = input("Enter Theme: ")
    try:
        c = int(input("Enter number of sentences (e.g. 60): "))
    except ValueError:
        c = 60
    engine.generate_worksheet(t, c)
