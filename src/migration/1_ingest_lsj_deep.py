import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.beta_code import BetaCodeConverter

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

DB_PATH = Path("data/processed/kombyphantike_v2.db")
XML_DIR = Path("data/dictionaries/lsj_xml")
POET_AUTHORS = ["Sophocles", "Homer"]
BATCH_SIZE = 1000  # Commit every 1000 entries


def strip_ns(tag):
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def clean_definition_text(text, converter):
    if not text:
        return ""

    # 1. Regex Cleanup (Fast)
    # Remove "c. gen.", "c. acc.", "folld. by", "cf." (case insensitive)
    text = re.sub(r"\bc\. gen\.\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bc\. acc\.\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfolld\. by\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcf\.\s*", "", text, flags=re.IGNORECASE)

    # Clean multiple semicolons/spaces
    text = re.sub(r";+", ";", text)
    text = re.sub(r"\s+", " ", text)

    # 2. Beta Code Detection (Optimized)
    # Only split and token-process if the string actually contains beta code markers
    # This skips the expensive loop for pure English text.
    if re.search(r"[\\/=\\|]", text):
        tokens = re.split(r"(\s+)", text)
        processed_tokens = []
        for token in tokens:
            # Only convert if it looks like beta code AND isn't just whitespace
            if token.strip() and re.search(r"[\\/=\\|]", token):
                processed_tokens.append(converter.to_greek(token))
            else:
                processed_tokens.append(token)
        text = "".join(processed_tokens)

    return text.strip()


def process_citation(cit_node, converter):
    cit_obj = {}

    # Extract fields
    for child in cit_node:
        tag = strip_ns(child.tag)
        text_val = child.text.strip() if child.text else ""
        if not text_val:
            continue

        if tag == "author":
            cit_obj["author"] = text_val
        elif tag in ("work", "title"):
            cit_obj["work"] = text_val
        elif tag in ("quote", "q", "text"):
            cit_obj["greek"] = clean_definition_text(text_val, converter)
        elif tag in ("translation", "tr"):
            cit_obj["translation"] = text_val
        elif tag == "bibl":
            # Handle nested bibl
            for bibl_child in child:
                bibl_tag = strip_ns(bibl_child.tag)
                bibl_text = bibl_child.text.strip() if bibl_child.text else ""
                if not bibl_text:
                    continue
                if bibl_tag == "author":
                    cit_obj["author"] = bibl_text
                elif bibl_tag == "title":
                    cit_obj["work"] = bibl_text

    # Jewel Selection Logic
    has_translation = "translation" in cit_obj and cit_obj["translation"]
    author = cit_obj.get("author")
    is_poet = author in POET_AUTHORS

    if has_translation:
        return cit_obj
    elif is_poet:
        return cit_obj
    else:
        return None


def get_definition_text(elem, converter):
    text_content = []
    if elem.text:
        text_content.append(elem.text.strip())

    for child in elem:
        tag_name = strip_ns(child.tag)
        if tag_name == "cit":
            if child.tail:
                text_content.append(child.tail.strip())
            continue

        sub_text = get_definition_text(child, converter)
        if sub_text:
            text_content.append(sub_text)

        if child.tail:
            text_content.append(child.tail.strip())

    combined_text = " ".join(filter(None, text_content))
    return clean_definition_text(combined_text, converter)


def ingest_lsj():
    if not XML_DIR.exists():
        print(f"Directory {XML_DIR} does not exist.")
        return

    converter = BetaCodeConverter()

    # Create DB directory if it doesn't exist
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Optimization: synchronous off makes writes faster (riskier, but fine for migration)
    cursor.execute("PRAGMA synchronous = OFF")
    cursor.execute("PRAGMA journal_mode = MEMORY")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS lsj_entries (
        id INTEGER PRIMARY KEY,
        canonical_key TEXT UNIQUE,
        headword TEXT,
        entry_json TEXT
    );
    """
    )
    conn.commit()

    files = sorted(list(XML_DIR.glob("*.xml")))  # Sort to ensure alpha order
    print(f"Found {len(files)} XML files.")

    total_inserted = 0

    # Outer loop: Files
    for file_path in tqdm(files, desc="Processing Files", unit="file"):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Find all entryFree.
            entries = []
            for elem in root.iter():
                if strip_ns(elem.tag) == "entryFree":
                    entries.append(elem)

            if not entries:
                continue

            # Inner loop: Entries (Visual Feedback)
            file_updates = 0
            for entry in tqdm(entries, desc=f"  Parsing {file_path.name}", leave=False):
                # headword
                headword = entry.get("headword")
                if not headword:
                    for child in entry:
                        if strip_ns(child.tag) == "orth":
                            headword = child.text
                            break

                # key
                key_attr = entry.get("key")
                canonical_key = ""

                if key_attr:
                    canonical_key = converter.canonicalize(key_attr)
                elif headword:
                    beta = converter.to_beta_code(headword)
                    canonical_key = converter.canonicalize(beta)

                if not canonical_key:
                    continue

                senses_list = []
                sense_nodes = []
                for child in entry.iter():
                    if strip_ns(child.tag) == "sense":
                        sense_nodes.append(child)

                for sense in sense_nodes:
                    sense_id = sense.get("id") or sense.get("n")
                    definition = get_definition_text(sense, converter)
                    citations = []
                    cit_nodes = []
                    for child in sense.iter():
                        if strip_ns(child.tag) == "cit":
                            cit_nodes.append(child)

                    for cit in cit_nodes:
                        cit_obj = process_citation(cit, converter)
                        if cit_obj:
                            citations.append(cit_obj)

                    senses_list.append(
                        {
                            "id": sense_id,
                            "definition": definition,
                            "citations": citations,
                        }
                    )

                entry_data = {"headword": headword, "senses": senses_list}

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO lsj_entries (canonical_key, headword, entry_json)
                    VALUES (?, ?, ?)
                """,
                    (
                        canonical_key,
                        headword,
                        json.dumps(entry_data, ensure_ascii=False),
                    ),
                )

                file_updates += 1
                total_inserted += 1

                # BATCH COMMIT
                if total_inserted % BATCH_SIZE == 0:
                    conn.commit()

            # Commit end of file
            conn.commit()

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    conn.commit()
    conn.close()
    print(f"Ingestion Complete. Total entries: {total_inserted}")


if __name__ == "__main__":
    ingest_lsj()
