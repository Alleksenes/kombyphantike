import sqlite3
import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from src.beta_code import BetaCodeConverter

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
DICT_DIR = DATA_DIR / "dictionaries"
LSJ_DIR = DICT_DIR / "lsj_xml"
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- TIER DEFINITIONS (Reused from lsj_fuzzy_indexer.py) ---
TIER_GOD = [
    "Soph.", "S.", "Aesch.", "A.", "Eur.", "E.", "Hom.", "Il.", "Od.",
    "Pind.", "Pi.", "Hes.",
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

def clean_rich_trans(text):
    if not text:
        return ""
    text = text.strip(" [](),;.")
    if len(text) < 2:
        return ""
    if text.lower() in ["ib", "id", "ibid", "op. cit.", "loc. cit."]:
        return ""
    return text

def get_text_between_siblings(start_node, end_node, parent):
    text_parts = []
    if start_node.tail:
        text_parts.append(start_node.tail.strip())
    started = False
    for child in parent:
        if child == start_node:
            started = True
            continue
        if child == end_node:
            break
        if started:
            if child.text:
                text_parts.append(child.text.strip())
            if child.tail:
                text_parts.append(child.tail.strip())
    return " ".join(text_parts).replace(" ,", ",").replace(" .", ".")

def extract_definition_flow(entry, converter):
    def_parts = []
    for sense in entry.findall(".//sense"):
        for child in sense:
            if child.tag == "tr" and child.text:
                def_parts.append(child.text.strip().strip(",;"))
            elif child.tag == "foreign" and child.text:
                beta = child.text
                greek = converter.to_greek(beta)
                if len(greek.split()) < 4:
                    def_parts.append(greek)
            if child.tag == "bibl" or child.tag == "cit":
                break
        if def_parts:
            break
    return "; ".join(def_parts)

def clean_definition(text: str) -> str:
    if not text:
        return ""
    parts = text.split(";")
    clean_parts = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part[0].isupper() and part.endswith(".") and len(part) < 20:
            continue
        if "Études" in part or "Rev." in part:
            continue
        if "[" in part and "]" in part:
            continue
        clean_parts.append(part)
    cleaned = "; ".join(clean_parts)
    if cleaned.endswith(" the"):
        cleaned = cleaned[:-4]
    elif cleaned.endswith(" a"):
        cleaned = cleaned[:-2]
    return cleaned

def extract_citation_candidates(entry, converter, fallback_def=""):
    candidates = []

    # STRATEGY 1: CIT (Explicit Citation Blocks)
    for cit in entry.findall(".//cit"):
        quote_tag = cit.find(".//quote")
        bibl_tag = cit.find(".//bibl")

        # Check for Translation inside CIT
        tr_tag = cit.find(".//tr")
        trans_text = ""
        if tr_tag is not None and tr_tag.text:
            trans_text = tr_tag.text.strip()

        if quote_tag is not None and quote_tag.text:
            beta = quote_tag.text
            greek = converter.to_greek(beta).replace("[", "").replace("]", "")
            raw_bibl = (
                "".join(bibl_tag.itertext()).strip() if bibl_tag is not None else ""
            )

            tier = get_author_tier(raw_bibl)
            word_count = len(greek.split())
            has_trans = len(trans_text) > 0

            candidates.append(
                {
                    "quote": greek,
                    "trans": trans_text,
                    "author": raw_bibl,
                    "tier": tier,
                    "length": word_count,
                    "has_trans": has_trans,
                }
            )

    # STRATEGY 2 & 3: SIBLING SCAN & IMPLICIT
    last_trans = fallback_def

    for sense in entry.findall(".//sense"):
        children = list(sense)
        for i, child in enumerate(children):

            # Update Translation Context
            if child.tag == "tr" and child.text:
                last_trans = child.text.strip()

            # STRATEGY 2: Explicit Greek (<foreign>)
            if child.tag == "foreign" and child.text:
                bibl_node = None
                for offset in range(1, 6):
                    if i + offset >= len(children):
                        break
                    sibling = children[i + offset]
                    if sibling.tag == "bibl":
                        bibl_node = sibling
                        break
                    elif sibling.tag == "foreign":
                        break

                if bibl_node is not None:
                    beta = child.text
                    greek = converter.to_greek(beta).replace("[", "").replace("]", "")
                    raw_bibl = "".join(bibl_node.itertext()).strip()
                    rich_trans = get_text_between_siblings(child, bibl_node, sense)
                    rich_trans = clean_rich_trans(re.sub(r"\s+", " ", rich_trans))

                    tier = get_author_tier(raw_bibl)
                    word_count = len(greek.split())
                    has_trans = len(rich_trans) > 0

                    candidates.append(
                        {
                            "quote": greek,
                            "trans": rich_trans,
                            "author": raw_bibl,
                            "tier": tier,
                            "length": word_count,
                            "has_trans": has_trans,
                        }
                    )

            # STRATEGY 3: IMPLICIT CITATIONS (Bibl without Foreign)
            if child.tag == "bibl":
                prev = children[i - 1] if i > 0 else None
                if prev is not None and prev.tag == "foreign":
                    continue  # Handled by Strategy 2

                raw_bibl = "".join(child.itertext()).strip()
                tier = get_author_tier(raw_bibl)

                if tier <= 2 and last_trans:
                    lemma_beta = entry.get("key")
                    if lemma_beta:
                        lemma_greek = (
                            converter.to_greek(lemma_beta)
                            .replace("^", "")
                            .replace("1", "")
                            .replace("2", "")
                        )
                        lemma_greek = re.sub(r"\d+", "", lemma_greek)

                        candidates.append(
                            {
                                "quote": lemma_greek,
                                "trans": last_trans,
                                "author": raw_bibl,
                                "tier": tier,
                                "length": 1,
                                "has_trans": True,
                            }
                        )

    # THE WATERFALL SORT
    candidates.sort(
        key=lambda x: (
            x["tier"],  # 1 is best
            not x["has_trans"],  # False (Has) is best
            -x["length"],  # Longest is best
        )
    )

    # Filter Garbage
    final = [c for c in candidates if c["tier"] < 5 and c["length"] > 0]
    return final

def create_lsj_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lsj_entries (
            id INTEGER PRIMARY KEY,
            canonical_key TEXT UNIQUE,
            definition TEXT,
            citations_json TEXT
        );
    """)

def ingest_lsj():
    if not LSJ_DIR.exists():
        logger.warning(f"LSJ directory not found: {LSJ_DIR}")
        return

    # Initialize Database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    create_lsj_table(cursor)

    # Initialize Converter
    try:
        converter = BetaCodeConverter()
    except Exception as e:
        logger.error(f"Failed to initialize BetaCodeConverter: {e}")
        return

    xml_files = list(LSJ_DIR.glob("*.xml"))
    logger.info(f"Found {len(xml_files)} XML files.")

    count = 0
    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Use iter() to find all entryFree elements regardless of depth
            for entry in root.findall(".//entryFree"):
                key = entry.get("key")
                if not key:
                    continue

                canon_key = converter.canonicalize(key)
                if not canon_key:
                    continue

                raw_def = extract_definition_flow(entry, converter)
                final_def = clean_definition(raw_def)

                cit_candidates = extract_citation_candidates(entry, converter, final_def)

                # Take top 3 "Jewel" citations
                jewels = cit_candidates[:3]
                citations_json = json.dumps(jewels, ensure_ascii=False)

                # Insert into DB
                try:
                    cursor.execute("""
                        INSERT INTO lsj_entries (canonical_key, definition, citations_json)
                        VALUES (?, ?, ?)
                        ON CONFLICT(canonical_key) DO UPDATE SET
                            definition = excluded.definition,
                            citations_json = excluded.citations_json
                    """, (canon_key, final_def, citations_json))
                    count += 1
                except sqlite3.Error as e:
                    logger.error(f"Database error for key {canon_key}: {e}")

        except Exception as e:
            logger.error(f"Error parsing {xml_file.name}: {e}")

    conn.commit()
    conn.close()
    logger.info(f"Ingestion complete. Processed {count} entries.")

if __name__ == "__main__":
    ingest_lsj()
