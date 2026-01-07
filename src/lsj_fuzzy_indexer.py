import xml.etree.ElementTree as ET
import json, logging, re
from src.config import DICT_DIR
from src.beta_code import BetaCodeConverter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

LSJ_DIR = DICT_DIR / "lsj_xml"
OUTPUT_INDEX = DICT_DIR / "lsj_index.json"
ABBREV_FILE = DICT_DIR / "abbreviations.json"

# --- SCORING WEIGHTS ---
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
]
TIER_PHIL = ["Pl.", "Arist."]
TIER_HIST = ["Hdt.", "Th.", "X."]

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
    """Cleans up captured translation text."""
    if not text:
        return ""
    # Remove leading/trailing junk
    text = text.strip(" [](),;.")
    if len(text) < 2:
        return ""
    # Filter bibliographic placeholders
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


def get_author_score(author_str):
    if not author_str:
        return 0
    for a in TIER_GOD:
        if a in author_str:
            return 60
    for a in TIER_PHIL:
        if a in author_str:
            return 30
    for a in TIER_HIST:
        if a in author_str:
            return 10
    if "IG" in author_str or "Schol." in author_str:
        return -50
    return 0


def get_quality_score(greek_text, has_translation, author_score):
    score = 0
    word_count = len(greek_text.split())

    # 1. TRANSLATION IS KING
    if has_translation:
        score += 50

    # 2. Penalize Noise
    if "[" in greek_text or "]" in greek_text:
        score -= 20
    if "π." in greek_text or "κ." in greek_text:
        if word_count < 5:
            score -= 10

    # 3. Penalize Fragments
    if word_count < 2:
        score -= 40

    # 4. Length Sweet Spot
    if 3 <= word_count <= 15:
        score += 20
    if word_count > 5:
        score += 10

    # 5. Penalize No-Translation UNLESS it's a God Tier Poet
    if not has_translation and author_score < 50:
        score -= 20

    return score


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


def is_golden_author(author_text):
    for giant in [
        "Sophocles",
        "Homer",
        "Euripides",
        "Aeschylus",
        "Plato",
        "Aristophanes",
        "Thucydides",
        "Herodotus",
        "Pindar",
        "Hesiod",
        "Sappho",
    ]:
        if giant in author_text:
            return True
    return False


def extract_citation_candidates(entry, converter):
    candidates = []

    # STRATEGY 1: CIT
    for cit in entry.findall(".//cit"):
        quote_tag = cit.find(".//quote")
        bibl_tag = cit.find(".//bibl")
        if quote_tag is not None and quote_tag.text:
            beta = quote_tag.text
            # Clean brackets immediately
            greek = converter.to_greek(beta).replace("[", "").replace("]", "")

            raw_bibl = (
                "".join(bibl_tag.itertext()).strip() if bibl_tag is not None else ""
            )

            auth_score = get_author_score(raw_bibl)
            # CIT usually lacks translation inside tag
            qual_score = get_quality_score(greek, False, auth_score)

            total = auth_score + qual_score
            if total > 0:
                candidates.append(
                    {"quote": greek, "trans": "", "author": raw_bibl, "score": total}
                )

    # STRATEGY 2: SIBLING SCAN
    for sense in entry.findall(".//sense"):
        children = list(sense)
        for i, child in enumerate(children):
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
                    # Clean brackets immediately
                    greek = converter.to_greek(beta).replace("[", "").replace("]", "")

                    raw_bibl = "".join(bibl_node.itertext()).strip()

                    rich_trans = get_text_between_siblings(child, bibl_node, sense)
                    rich_trans = clean_rich_trans(re.sub(r"\s+", " ", rich_trans))

                    has_trans = len(rich_trans) > 0

                    auth_score = get_author_score(raw_bibl)
                    qual_score = get_quality_score(greek, has_trans, auth_score)

                    total = auth_score + qual_score

                    if total > 0:
                        candidates.append(
                            {
                                "quote": greek,
                                "trans": rich_trans,
                                "author": raw_bibl,
                                "score": total,
                            }
                        )

    # STRATEGY 3: IMPLICIT CITATIONS (Bibl without Foreign)

    last_trans = ""

    for sense in entry.findall(".//sense"):
        children = list(sense)
        for i, child in enumerate(children):

            if child.tag == "tr" and child.text:
                last_trans = child.text.strip()

            if child.tag == "bibl":
                prev = children[i - 1] if i > 0 else None
                if prev is not None and prev.tag == "foreign":
                    continue

                raw_bibl = "".join(child.itertext()).strip()
                full_bibl = expand_author(raw_bibl)

                # Only grab if Golden Author (otherwise too much noise)
                if is_golden_author(full_bibl):
                    lemma_beta = entry.get("key")
                    lemma_greek = converter.to_greek(lemma_beta).split("^")[0]

                    # Consttruct
                    formatted = f"{lemma_greek} '{last_trans}' ({full_bibl})"

                    score = 40

                    candidates.append(
                        {
                            "quote": lemma_greek,
                            "trans": last_trans,
                            "author": raw_bibl,
                            "score": score,
                        }
                    )

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def build_index():
    print(f"--- STARTING JEWEL HUNTER INDEXING ---")
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
                cit_candidates = extract_citation_candidates(entry, converter)

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
                    unique_cits = {
                        c["quote"]: c for c in existing["cits_list"]
                    }.values()
                    existing["cits_list"] = sorted(
                        list(unique_cits), key=lambda x: x["score"], reverse=True
                    )

                    if key not in existing["original_key"]:
                        existing["original_key"] += "; " + key

            logger.info(f"Processed {xml_file.name}...")

        except Exception as e:
            logger.error(f"Error parsing {xml_file.name}: {e}")

    # FORMAT FOR OUTPUT
    print("Curating Gallery...")
    for k, v in lsj_index.items():
        candidates = v.pop("cits_list", [])
        if not candidates:
            v["cit"] = ""
            continue

        gallery = []
        for cand in candidates[:3]:
            full_bibl = expand_author(cand["author"])
            formatted = f"{cand['quote']}"
            if cand["trans"]:
                formatted += f" '{cand['trans']}'"
            formatted += f" ({full_bibl})"
            gallery.append(formatted)

        v["cit"] = " | ".join(gallery)

    with open(OUTPUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(lsj_index, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved to {OUTPUT_INDEX}")


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


if __name__ == "__main__":
    build_index()
