import json
import logging
import re
import sqlite3
import sys
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.beta_code import BetaCodeConverter
from src.config import PROCESSED_DIR

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"

# --- TIER DEFINITIONS (The Waterfall) ---
TIER_GOD = [
    "Soph.",
    "S.",
    "Aesch.",
    "A.",
    "Eur.",
    "E.",
    "Hom.",
    "Il.",
    "Od.",
    "Pind.",
    "Pi.",
    "Hes.",
]
TIER_PHIL = ["Pl.", "Arist.", "X.", "Epicur.", "Stoic."]
TIER_HIST = ["Hdt.", "Th.", "D.H.", "Plb.", "Xen."]


def get_author_tier(author_str):
    if not author_str:
        return 4
    for a in TIER_GOD:
        if a in author_str:
            return 1
    for a in TIER_PHIL:
        if a in author_str:
            return 2
    for a in TIER_HIST:
        if a in author_str:
            return 3
    return 4


def clean_lsj_text(text):
    if not text:
        return ""
    # Strip common LSJ technical noise
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ;.,")


def create_schema(cursor):
    """Refined Schema with Separated Ancient Data"""
    logger.info("Rebuilding Schema with Two-Column Ancient Data...")
    cursor.execute("DROP TABLE IF EXISTS relations")
    cursor.execute("DROP TABLE IF EXISTS forms")
    cursor.execute("DROP TABLE IF EXISTS lemmas")

    cursor.execute("""
        CREATE TABLE lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT NOT NULL UNIQUE,
            pos TEXT,
            ipa TEXT,
            greek_def TEXT,
            modern_def TEXT,
            ancient_definitions TEXT, -- The "Ground" (Semantics)
            ancient_citations TEXT,   -- The "Sky" (Golden Jewels)
            etymology_json TEXT,      -- Raw data for future-proofing
            lsj_id INTEGER,
            kds_score INTEGER,
            FOREIGN KEY(lsj_id) REFERENCES lsj_entries(id)
        )
    """)
    # (Relations and Forms tables remain the same...)
    cursor.execute(
        "CREATE TABLE forms (id INTEGER PRIMARY KEY AUTOINCREMENT, lemma_id INTEGER NOT NULL, form_text TEXT NOT NULL, tags_json TEXT, FOREIGN KEY(lemma_id) REFERENCES lemmas(id))"
    )
    cursor.execute(
        "CREATE TABLE relations (id INTEGER PRIMARY KEY AUTOINCREMENT, child_lemma_id INTEGER NOT NULL, parent_lemma_text TEXT NOT NULL, relation_type TEXT, FOREIGN KEY(child_lemma_id) REFERENCES lemmas(id))"
    )


class MasterIngestionLinker:
    def __init__(self):
        self.converter = BetaCodeConverter()
        self.lsj_map = {}

    def load_lsj_map(self, cursor):
        cursor.execute("SELECT id, canonical_key FROM lsj_entries")
        for row_id, key in cursor.fetchall():
            if key:
                self.lsj_map[key] = row_id

    def ingest_stage_2(self, cursor):
        """THE ENRICHMENT PASS: Separating Semantics from Jewels"""
        logger.info("--- STAGE 2: THE WATERFALL ENRICHMENT ---")
        cursor.execute(
            "SELECT l.id, l.lsj_id, e.entry_json FROM lemmas l JOIN lsj_entries e ON l.lsj_id = e.id"
        )
        rows = cursor.fetchall()

        updates = []
        for lemma_id, lsj_id, entry_json_str in tqdm(rows, desc="Enriching"):
            entry_data = json.loads(entry_json_str)
            senses = entry_data.get("senses", [])

            # 1. THE GROUND: Extract Clean Definitions
            semantics = []
            for sense in senses:
                d = clean_lsj_text(sense.get("definition", ""))
                if d and d not in semantics:
                    semantics.append(d)

            ancient_def_str = " | ".join(semantics[:4])  # Top 4 semantic meanings

            # 2. THE SKY: Extract and Sort Citations (Waterfall)
            candidates = []
            for sense in senses:
                for cit in sense.get("citations", []):
                    quote = cit.get("greek", "")
                    trans = cit.get("translation", "")
                    author = cit.get("author", "")
                    work = cit.get("work", "")

                    if not quote:
                        continue

                    tier = get_author_tier(author)
                    candidates.append(
                        {
                            "quote": quote,
                            "trans": trans,
                            "author": f"{author} {work}".strip(),
                            "tier": tier,
                            "has_trans": bool(trans),
                            "len": len(quote.split()),
                        }
                    )

            # Waterfall Sort: Tier -> Has Translation -> Length
            candidates.sort(key=lambda x: (x["tier"], not x["has_trans"], -x["len"]))

            # Build Citation Gallery
            gallery = []
            seen_authors = set()
            for c in candidates:
                if len(gallery) >= 3:
                    break
                main_author = c["author"].split()[0] if c["author"] else "Unknown"
                if main_author in seen_authors and len(candidates) > 5:
                    continue

                fmt = f"{c['quote']}"
                if c["trans"]:
                    fmt += f" '{c['trans']}'"
                fmt += f" ({c['author']})"
                gallery.append(fmt)
                seen_authors.add(main_author)

            ancient_cit_str = " | ".join(gallery)

            updates.append((ancient_def_str, ancient_cit_str, lemma_id))

        cursor.executemany(
            "UPDATE lemmas SET ancient_definitions = ?, ancient_citations = ? WHERE id = ?",
            updates,
        )
        cursor.connection.commit()
        logger.info("Stage 1 Complete.")

    def ingest_stage_2(self, cursor):
        logger.info("--- STAGE 2: ENRICHMENT (THE SUBLIME PASS) ---")

        # Select all lemmas that have an LSJ link
        cursor.execute(
            "SELECT l.id, l.lsj_id, e.entry_json FROM lemmas l JOIN lsj_entries e ON l.lsj_id = e.id"
        )
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

                    candidates.append(
                        {
                            "quote": quote,
                            "trans": trans,
                            "author": full_bibl,
                            "tier": tier,
                            "length": length,
                            "has_trans": bool(trans),
                        }
                    )

            # THE WATERFALL SORT
            # Sort by: Tier ASC (1 is best), Has Trans DESC (True is better -> False comes first in bool sort? No, False < True. We want True first. So `not has_trans` ASC), Length DESC (-length ASC)
            candidates.sort(key=lambda x: (x["tier"], not x["has_trans"], -x["length"]))

            # Filter Garbage
            final_candidates = [
                c for c in candidates if c["tier"] < 5 and c["length"] > 0
            ]

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
                    continue  # Diversity check

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
        cursor.executemany(
            "UPDATE lemmas SET etymology_text = ?, etymology_json = ? WHERE id = ?",
            updates,
        )
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
