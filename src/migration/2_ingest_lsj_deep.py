import sqlite3
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.beta_code import BetaCodeConverter

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x: x

DB_PATH = Path("data/processed/kombyphantike_v2.db")
XML_DIR = Path("data/dictionaries/lsj_xml")

def strip_ns(tag):
    if '}' in tag:
        return tag.split('}', 1)[1]
    return tag

def get_definition_text(elem):
    text_content = []
    if elem.text:
        text_content.append(elem.text.strip())

    for child in elem:
        tag_name = strip_ns(child.tag)
        if tag_name == 'cit':
            # Skip citation content in definition, but keep tail text
            if child.tail:
                text_content.append(child.tail.strip())
            continue

        # Recurse for other tags to get their text
        sub_text = get_definition_text(child)
        if sub_text:
            text_content.append(sub_text)

        if child.tail:
            text_content.append(child.tail.strip())

    return " ".join(filter(None, text_content))

def ingest_lsj():
    if not XML_DIR.exists():
        print(f"Directory {XML_DIR} does not exist.")
        return

    converter = BetaCodeConverter()

    # Create DB directory if it doesn't exist
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lsj_entries (
        id INTEGER PRIMARY KEY,
        canonical_key TEXT UNIQUE, -- Stripped beta code (e.g. 'prostatew')
        headword TEXT, -- Original Greek form
        entry_json TEXT -- The structured tree
    );
    """)
    conn.commit()

    files = list(XML_DIR.glob("*.xml"))
    print(f"Found {len(files)} XML files.")

    for file_path in tqdm(files):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Find all entryFree.
            entries = []
            for elem in root.iter():
                if strip_ns(elem.tag) == 'entryFree':
                    entries.append(elem)

            for entry in entries:
                # headword
                headword = entry.get('headword')
                if not headword:
                    # try <orth> child
                    for child in entry:
                         if strip_ns(child.tag) == 'orth':
                             headword = child.text
                             break

                # key
                key_attr = entry.get('key')
                canonical_key = ""

                if key_attr:
                    canonical_key = converter.canonicalize(key_attr)
                elif headword:
                    # fallback: convert headword to beta code then canonicalize
                    beta = converter.to_beta_code(headword)
                    canonical_key = converter.canonicalize(beta)

                if not canonical_key:
                    continue

                senses_list = []

                # Find all sense tags within this entry
                sense_nodes = []
                for child in entry.iter():
                    if strip_ns(child.tag) == 'sense':
                        sense_nodes.append(child)

                for sense in sense_nodes:
                    sense_id = sense.get('id') or sense.get('n')

                    definition = get_definition_text(sense)

                    citations = []
                    cit_nodes = []
                    for child in sense.iter():
                        if strip_ns(child.tag) == 'cit':
                            cit_nodes.append(child)

                    for cit in cit_nodes:
                        cit_obj = {}
                        for child in cit:
                            tag = strip_ns(child.tag)
                            text_val = child.text.strip() if child.text else ""
                            if not text_val:
                                continue

                            if tag == 'author':
                                cit_obj['author'] = text_val
                            elif tag in ('work', 'title'):
                                cit_obj['work'] = text_val
                            elif tag in ('quote', 'q', 'text'):
                                cit_obj['text'] = text_val
                            elif tag in ('translation', 'tr'):
                                cit_obj['translation'] = text_val
                            elif tag == 'bibl':
                                # bibl might contain author/work
                                for bibl_child in child:
                                    bibl_tag = strip_ns(bibl_child.tag)
                                    bibl_text = bibl_child.text.strip() if bibl_child.text else ""
                                    if not bibl_text: continue
                                    if bibl_tag == 'author':
                                        cit_obj['author'] = bibl_text
                                    elif bibl_tag == 'title':
                                        cit_obj['work'] = bibl_text

                        if cit_obj:
                            citations.append(cit_obj)

                    senses_list.append({
                        "id": sense_id,
                        "definition": definition,
                        "citations": citations
                    })

                entry_data = {
                    "headword": headword,
                    "senses": senses_list
                }

                cursor.execute("""
                    INSERT OR REPLACE INTO lsj_entries (canonical_key, headword, entry_json)
                    VALUES (?, ?, ?)
                """, (canonical_key, headword, json.dumps(entry_data, ensure_ascii=False)))

        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    ingest_lsj()
