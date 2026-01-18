import xml.etree.ElementTree as ET
import json
import logging
import re
from src.config import DICT_DIR
from src.beta_code import BetaCodeConverter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

LSJ_DIR = DICT_DIR / "lsj_xml"
OUTPUT_INDEX = DICT_DIR / "lsj_index.json"
ABBREV_FILE = DICT_DIR / "abbreviations.json"

# --- TIER DEFINITIONS ---
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
TIER_PHIL = ["Pl.", "Arist.", "X."]
TIER_HIST = ["Hdt.", "Th.", "D.H.", "Plb."]

# LOAD ABBREVIATIONS
ABBREV_MAP = {}
if ABBREV_FILE.exists():
    try:
        with open(ABBREV_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            for k, v in raw_data.items():
                if isinstance(v, dict):
                    val = v.get("author") or v.get("work") or v.get("expanded")
                    if val:
                        ABBREV_MAP[k] = val
                elif isinstance(v, str):
                    ABBREV_MAP[k] = v
    except:
        pass


def expand_author(text):
    if not text:
        return ""
    tokens = text.split()
    expanded = []
    for t in tokens:
        clean = t.strip(".,;") + "."
        expanded.append(ABBREV_MAP.get(clean, ABBREV_MAP.get(t, t)))
    return " ".join(expanded)


def is_greek(text):
    for char in text:
        if "\u0370" <= char <= "\u03ff" or "\u1f00" <= char <= "\u1fff":
            return True
    return False


def clean_rich_trans(text):
    if not text:
        return ""
    text = text.strip(" [](),;.")
    if len(text) < 2:
        return ""
    if text.lower() in ["ib", "id", "ibid", "op. cit.", "loc. cit."]:
        return ""
    return text


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


def extract_aorist(entry, converter):
    found_aorist_tag = False
    for elem in entry.iter():
        if elem.tag.endswith("tns"):
            if elem.text and "aor" in elem.text:
                found_aorist_tag = True
                continue
        if found_aorist_tag:
            if elem.tag.endswith("quote"):
                beta_form = elem.text
                if beta_form:
                    greek_form = converter.to_greek(beta_form)
                    if is_greek(greek_form):
                        return greek_form
            if elem.tag.endswith("bibl") or elem.tag.endswith("sense"):
                found_aorist_tag = False
    return ""


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
    # We scan senses to find flow

    # Initialize with the main definition as a fallback translation
    # This fixes cases where the definition is global but citation is local
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

                # Accept Poets (1) and Philosophers (2)
                # If we have a translation (even fallback), we take it.
                if tier <= 2 and last_trans:
                    lemma_beta = entry.get("key")
                    lemma_greek = (
                        converter.to_greek(lemma_beta)
                        .replace("^", "")
                        .replace("1", "")
                        .replace("2", "")
                    )

                    # Remove numbers from lemma (e.g. θεολόγος1)
                    lemma_greek = re.sub(r"\d+", "", lemma_greek)

                    candidates.append(
                        {
                            "quote": lemma_greek,
                            "trans": last_trans,
                            "author": raw_bibl,
                            "tier": tier,
                            "length": 1,
                            "has_trans": True,  # We treat the def as trans
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


def build_index():
    print(f"--- STARTING WATERFALL LSJ INDEXING ---")
    if not LSJ_DIR.exists():
        return

    converter = BetaCodeConverter()
    lsj_index = {}
    xml_files = list(LSJ_DIR.glob("*.xml"))
    logger.info(f"Found {len(xml_files)} XML files.")

    for xml_file in xml_files:
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for entry in root.findall(".//entryFree"):
                key = entry.get("key")
                if not key:
                    continue

                canon_key = converter.canonicalize(key)
                if not canon_key:
                    continue

                raw_def = extract_definition_flow(entry, converter)
                final_def = clean_definition(raw_def)
                aorist_form = extract_aorist(entry, converter)

                # PASS THE DEFINITION AS FALLBACK
                cit_candidates = extract_citation_candidates(
                    entry, converter, final_def
                )

                if not final_def and not aorist_form and not cit_candidates:
                    continue

                if canon_key not in lsj_index:
                    lsj_index[canon_key] = {
                        "def": final_def,
                        "aor": aorist_form,
                        "cits_list": cit_candidates,
                        "original_key": key,
                    }
                else:
                    existing = lsj_index[canon_key]
                    if final_def:
                        if not existing["def"]:
                            existing["def"] = final_def
                        elif final_def not in existing["def"]:
                            existing["def"] += " | " + final_def

                    if aorist_form and aorist_form != existing["aor"]:
                        if existing["aor"]:
                            existing["aor"] += " / " + aorist_form
                        else:
                            existing["aor"] = aorist_form

                    existing["cits_list"].extend(cit_candidates)
                    existing["cits_list"].sort(
                        key=lambda x: (x["tier"], not x["has_trans"], -x["length"])
                    )

                    if key not in existing["original_key"]:
                        existing["original_key"] += "; " + key

            logger.info(f"Processed {xml_file.name}...")

        except Exception as e:
            logger.error(f"Error parsing {xml_file.name}: {e}")

    print("Curating Gallery...")
    for k, v in lsj_index.items():
        candidates = v.pop("cits_list", [])
        if not candidates:
            v["cit"] = ""
            continue

        gallery = []
        seen_authors = set()

        for cand in candidates:
            if len(gallery) >= 3:
                break

            full_bibl = expand_author(cand["author"])
            main_author = full_bibl.split()[0] if full_bibl else "Unknown"

            if main_author in seen_authors and len(candidates) > 3:
                continue

            formatted = f"{cand['quote']}"
            if cand["trans"]:
                formatted += f" '{cand['trans']}'"
            formatted += f" ({full_bibl})"
            gallery.append(formatted)
            seen_authors.add(main_author)

        v["cit"] = " | ".join(gallery)

    with open(OUTPUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(lsj_index, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved to {OUTPUT_INDEX}")


if __name__ == "__main__":
    build_index()
