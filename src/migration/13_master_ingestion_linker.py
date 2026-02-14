import sqlite3
import json
import logging
import sys
import re
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Mock pandas if not present (BetaCodeConverter uses it minimally)
try:
    import pandas
except ImportError:
    from unittest.mock import MagicMock
    m = MagicMock()
    m.isna.side_effect = lambda x: x is None
    sys.modules['pandas'] = m

from src.config import KAIKKI_EL_FILE, PROCESSED_DIR
from src.beta_code import BetaCodeConverter

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
BATCH_SIZE = 5000

# --- TIER DEFINITIONS (from Inspiration) ---
TIER_GOD = [
    "Soph.", "S.", "Aesch.", "A.", "Eur.", "E.",
    "Hom.", "Il.", "Od.", "Pind.", "Pi.", "Hes."
]
TIER_PHIL = ["Pl.", "Arist.", "X."]
TIER_HIST = ["Hdt.", "Th.", "D.H.", "Plb."]

def get_author_tier(author_str):
    if not author_str:
        return 4  # Standard
    for a in TIER_GOD:
        if a in author_str:
            return 1
    for a in TIER_PHIL:
        if a in author_str:
            return 2
    for a in TIER_HIST:
        if a in author_str:
            return 3
    if "IG" in author_str or "Schol." in author_str:
        return 5  # Trash
    return 4

def create_schema(cursor):
    """Destroys and Rebuilds the World."""
    logger.info("Dropping old tables...")
    cursor.execute("DROP TABLE IF EXISTS relations")
    cursor.execute("DROP TABLE IF EXISTS forms")
    cursor.execute("DROP TABLE IF EXISTS lemmas")

    logger.info("Creating new schema...")
    # Lemmas: With LSJ ID
    cursor.execute(
        """
        CREATE TABLE lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT NOT NULL UNIQUE,
            pos TEXT,
            ipa TEXT,
            etymology_json TEXT,
            etymology_text TEXT, -- Populated by Enrichment
            greek_def TEXT,
            english_def TEXT,
            lsj_id INTEGER, -- The Primary Key to the Ancient World
            FOREIGN KEY(lsj_id) REFERENCES lsj_entries(id)
        )
    """
    )

    # Forms
    cursor.execute(
        """
        CREATE TABLE forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_id INTEGER NOT NULL,
            form_text TEXT NOT NULL,
            tags_json TEXT,
            FOREIGN KEY(lemma_id) REFERENCES lemmas(id)
        )
    """
    )

    # Relations
    cursor.execute(
        """
        CREATE TABLE relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_lemma_id INTEGER NOT NULL,
            parent_lemma_text TEXT NOT NULL,
            relation_type TEXT,
            FOREIGN KEY(child_lemma_id) REFERENCES lemmas(id)
        )
    """
    )

    cursor.execute("CREATE INDEX idx_lemma_text ON lemmas(lemma_text)")
    cursor.execute("CREATE INDEX idx_forms_lemma ON forms(lemma_id)")
    cursor.execute("CREATE INDEX idx_forms_text ON forms(form_text)")
    cursor.execute("CREATE INDEX idx_lemmas_lsj_id ON lemmas(lsj_id)")


class MasterIngestionLinker:
    def __init__(self):
        self.converter = BetaCodeConverter()
        self.lsj_map = {} # canonical_key -> id

    def load_lsj_map(self, cursor):
        logger.info("Loading LSJ Headword Map...")
        # Verify lsj_entries exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lsj_entries'")
        if not cursor.fetchone():
            logger.warning("lsj_entries table does not exist! Linking will fail.")
            return

        cursor.execute("SELECT id, canonical_key FROM lsj_entries")
        rows = cursor.fetchall()
        for row_id, key in rows:
            if key:
                self.lsj_map[key] = row_id
        logger.info(f"Loaded {len(self.lsj_map)} LSJ entries.")

    def normalize_for_match(self, text):
        if not text:
            return None
        # Convert to Beta Code (handles accents/breathing stripping conceptually via canonicalize later? No, to_beta_code preserves them)
        beta = self.converter.to_beta_code(text)
        # Canonicalize (strips accents/breathings, converts to lowercase latin-ish beta code)
        canon = self.converter.canonicalize(beta)
        return canon

    def parse_etymology(self, text):
        if not text:
            return None
        # Regex for "from ancient greek [WORD]"
        # Matches: αρχαία ελληνική, αρχ. ελλ., grc
        match = re.search(r"(?:αρχαία ελληνική|αρχ\. ελλ\.|grc)\s+([^\s,.]+)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def ingest_stage_1(self, cursor):
        logger.info("--- STAGE 1: INGESTION & LINKING ---")
        if not KAIKKI_EL_FILE.exists():
            logger.error(f"Kaikki file not found: {KAIKKI_EL_FILE}")
            return

        total_lines = sum(1 for _ in open(KAIKKI_EL_FILE, "r", encoding="utf-8"))

        count = 0
        with open(KAIKKI_EL_FILE, "r", encoding="utf-8") as f:
            for line in tqdm(f, total=total_lines, desc="Ingesting"):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                word = entry.get("word")
                if not word:
                    continue

                pos = entry.get("pos")

                # IPA
                ipa = ""
                if "sounds" in entry:
                    for s in entry["sounds"]:
                        if "ipa" in s:
                            ipa = s["ipa"]
                            break

                # Etymology
                etym_templates = entry.get("etymology_templates", [])
                etym_json = json.dumps(etym_templates, ensure_ascii=False)
                etym_text = entry.get("etymology_text", "")

                # Definitions
                greek_defs = []
                form_of_parents = set()

                if "senses" in entry:
                    for sense in entry["senses"]:
                        if "glosses" in sense:
                            greek_defs.extend(sense["glosses"])

                        for tag in ["form_of", "alt_of", "inflection_of"]:
                            if tag in sense:
                                for ref in sense[tag]:
                                    if "word" in ref:
                                        form_of_parents.add(ref["word"])

                greek_def_str = " | ".join(greek_defs) if greek_defs else ""

                # --- LINKING LOGIC ---
                lsj_id = None

                # 1. The Deep Etymological Hunt
                ancient_word = self.parse_etymology(etym_text)
                if ancient_word:
                    canon = self.normalize_for_match(ancient_word)
                    if canon in self.lsj_map:
                        lsj_id = self.lsj_map[canon]

                # 2. The Fuzzy Fallback
                if not lsj_id:
                    canon_lemma = self.normalize_for_match(word)
                    if canon_lemma in self.lsj_map:
                        lsj_id = self.lsj_map[canon_lemma]

                # INSERT
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO lemmas
                    (lemma_text, pos, ipa, etymology_json, greek_def, lsj_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (word, pos, ipa, etym_json, greek_def_str, lsj_id)
                )

                # Get inserted ID
                cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (word,))
                res = cursor.fetchone()
                if not res:
                    continue
                lemma_id = res[0]

                # Relations
                for parent in form_of_parents:
                    cursor.execute(
                        """
                        INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type)
                        VALUES (?, ?, 'form_of')
                        """,
                        (lemma_id, parent)
                    )

                # Forms
                if "forms" in entry:
                    for form in entry["forms"]:
                        f_text = form.get("form")
                        f_tags = form.get("tags", [])
                        if f_text:
                            cursor.execute(
                                """
                                INSERT INTO forms (lemma_id, form_text, tags_json)
                                VALUES (?, ?, ?)
                                """,
                                (lemma_id, f_text, json.dumps(f_tags, ensure_ascii=False))
                            )

                count += 1
                if count % BATCH_SIZE == 0:
                    cursor.connection.commit()

        cursor.connection.commit()
        logger.info("Stage 1 Complete.")

    def ingest_stage_2(self, cursor):
        logger.info("--- STAGE 2: ENRICHMENT (THE SUBLIME PASS) ---")

        # Select all lemmas that have an LSJ link
        cursor.execute("SELECT l.id, l.lsj_id, e.entry_json FROM lemmas l JOIN lsj_entries e ON l.lsj_id = e.id")
        rows = cursor.fetchall()

        logger.info(f"Enriching {len(rows)} linked lemmas...")

        updates = []
        for lemma_id, lsj_id, entry_json_str in tqdm(rows, desc="Enriching"):
            if not entry_json_str:
                continue

            try:
                entry_data = json.loads(entry_json_str)
            except json.JSONDecodeError:
                continue

            # Gather all citations from all senses
            candidates = []
            senses = entry_data.get("senses", [])

            # Also extract a fallback definition from the first sense
            fallback_def = ""
            if senses:
                fallback_def = senses[0].get("definition", "")

            for sense in senses:
                citations = sense.get("citations", [])
                for cit in citations:
                    # Check if 'greek' exists, if not skip?
                    quote = cit.get("greek", "")
                    trans = cit.get("translation", "")
                    author = cit.get("author", "")
                    work = cit.get("work", "")

                    full_bibl = f"{author} {work}".strip()
                    tier = get_author_tier(author)

                    # Length in words
                    length = len(quote.split()) if quote else 0

                    candidates.append({
                        "quote": quote,
                        "trans": trans,
                        "author": full_bibl,
                        "tier": tier,
                        "length": length,
                        "has_trans": bool(trans)
                    })

            # THE WATERFALL SORT
            # Sort by: Tier ASC (1 is best), Has Trans DESC (True is better -> False comes first in bool sort? No, False < True. We want True first. So `not has_trans` ASC), Length DESC (-length ASC)
            candidates.sort(key=lambda x: (
                x["tier"],
                not x["has_trans"],
                -x["length"]
            ))

            # Filter Garbage
            final_candidates = [c for c in candidates if c["tier"] < 5 and c["length"] > 0]

            if not final_candidates:
                # If no citations, we might just keep the definition?
                # The prompt says "update the etymology_text ... with this 'Sublime' data".
                # If no citation, maybe just the definition?
                if fallback_def:
                    updates.append((fallback_def, "[]", lemma_id))
                continue

            # Build Gallery (Top 3)
            gallery = []
            seen_authors = set()

            for cand in final_candidates:
                if len(gallery) >= 3:
                    break

                main_author = cand["author"].split()[0] if cand["author"] else "Unknown"
                if main_author in seen_authors and len(final_candidates) > 3:
                    continue # Diversity check

                formatted = f"{cand['quote']}"
                if cand["trans"]:
                    formatted += f" '{cand['trans']}'"
                formatted += f" ({cand['author']})"

                gallery.append(formatted)
                seen_authors.add(main_author)

            # Combine Definition + Gallery
            final_text = fallback_def
            if gallery:
                final_text += " | " + " | ".join(gallery)

            # Prepare JSON (Sublime Data)
            sublime_json = json.dumps(final_candidates[:3], ensure_ascii=False)

            updates.append((final_text, sublime_json, lemma_id))

        # Batch Update
        logger.info(f"Updating {len(updates)} lemmas...")
        cursor.executemany("UPDATE lemmas SET etymology_text = ?, etymology_json = ? WHERE id = ?", updates)
        cursor.connection.commit()
        logger.info("Stage 2 Complete.")

def main():
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    linker = MasterIngestionLinker()

    # Setup
    create_schema(cursor)
    linker.load_lsj_map(cursor)

    # Execute
    linker.ingest_stage_1(cursor)
    linker.ingest_stage_2(cursor)

    # Optimize
    cursor.execute("VACUUM")
    conn.close()
    logger.info("Master Ingestion Complete.")

if __name__ == "__main__":
    main()
