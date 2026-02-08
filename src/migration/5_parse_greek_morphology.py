import sqlite3
import json
import re
import logging
import sys
from pathlib import Path
from tqdm import tqdm

# Ensure src is in path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

# Database Path
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
LOG_DIR = PROCESSED_DIR.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
MISSING_PARENTS_LOG = LOG_DIR / "missing_parents.log"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 2. The Rosetta Stone (Mapping Dictionary)
MORPH_MAP = {
    # Cases
    "ονομαστική": "nominative",
    "γενική": "genitive",
    "αιτιατική": "accusative",
    "κλητική": "vocative",
    # Numbers
    "ενικού": "singular",
    "πληθυντικού": "plural",
    # Genders
    "αρσενικό": "masculine",
    "αρσενικού": "masculine",
    "θηλυκό": "feminine",
    "θηλυκού": "feminine",
    "ουδέτερο": "neuter",
    "ουδέτερου": "neuter",
    # Verbs
    "ενεστώτα": "present",
    "αόριστου": "past",
    "παρατατικού": "imperfect",
    "μέλλοντα": "future",
    "υποτακτικής": "subjunctive",
    "οριστικής": "indicative",
    "ενεργητική": "active",
    "παθητική": "passive",
}

def ensure_schema(cursor):
    """Creates forms and relations tables if they don't exist."""
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_id INTEGER NOT NULL,
            form_text TEXT NOT NULL,
            tags_json TEXT,
            FOREIGN KEY(lemma_id) REFERENCES lemmas(id)
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_lemma_id INTEGER NOT NULL,
            parent_lemma_text TEXT NOT NULL,
            relation_type TEXT,
            FOREIGN KEY(child_lemma_id) REFERENCES lemmas(id)
        )
    """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_forms_lemma ON forms(lemma_id)")

def extract_person(text):
    """Extracts person (1st, 2nd, 3rd) from text."""
    persons = []
    # Match α', β', γ' followed by πρόσωπο, handling both standard apostrophe and greek tonos
    if re.search(r"[α1][\'΄ο]\s*πρόσωπο", text):
        persons.append("1st person")
    if re.search(r"[β2][\'΄ο]\s*πρόσωπο", text):
        persons.append("2nd person")
    if re.search(r"[γ3][\'΄ο]\s*πρόσωπο", text):
        persons.append("3rd person")
    return persons

def parse_greek_morphology():
    if not DB_PATH.exists():
        logging.error(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    ensure_schema(cursor)
    conn.commit()

    logging.info("Fetching lemmas with greek_def...")
    cursor.execute("SELECT id, lemma_text, greek_def FROM lemmas WHERE greek_def IS NOT NULL")
    rows = cursor.fetchall()

    logging.info(f"Found {len(rows)} lemmas to process.")

    missing_parents = []
    processed_count = 0
    relations_added = 0
    forms_added = 0

    # Cache for parent lemma IDs to reduce DB hits
    logging.info("Pre-loading lemma map...")
    cursor.execute("SELECT lemma_text, id FROM lemmas")
    lemma_map = {text: pid for text, pid in cursor.fetchall()}

    for lemma_id, lemma_text, greek_def in tqdm(rows, desc="Parsing Morphology"):
        # Phase A: Normalization
        normalized_def = greek_def.lower().strip().rstrip(".;")

        # Phase B: The Anchor Catch
        # Regex to find parent lemma
        # Patterns: "του <word>", "της <word>", "των <word>", "του ρήματος <word>"
        match = re.search(r"(?:^|\s)(?:του\s+ρήματος|του|της|των)\s+([^\s,;]+)", normalized_def)

        if not match:
            continue

        parent_lemma_text = match.group(1)
        parent_lemma_text = parent_lemma_text.rstrip(".")

        # Phase C: Multi-Tag Extraction
        tags = []
        for greek_term, english_tag in MORPH_MAP.items():
            if greek_term in normalized_def:
                tags.append(english_tag)

        # Add persons
        tags.extend(extract_person(normalized_def))

        # Phase D: Relational Integrity
        # Only proceed if we found tags, otherwise it's likely a false positive anchor match in a normal definition
        if not tags:
            continue

        parent_id = lemma_map.get(parent_lemma_text)

        if parent_id:
            # Insert into relations
            cursor.execute(
                """
                INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type)
                VALUES (?, ?, ?)
                """,
                (lemma_id, parent_lemma_text, 'form_of')
            )
            relations_added += 1

            # Insert into forms
            cursor.execute(
                """
                INSERT INTO forms (lemma_id, form_text, tags_json)
                VALUES (?, ?, ?)
                """,
                (parent_id, lemma_text, json.dumps(tags, ensure_ascii=False))
            )
            forms_added += 1

        else:
            missing_parents.append((lemma_text, parent_lemma_text))

        processed_count += 1

        if processed_count % 1000 == 0:
            conn.commit()

    conn.commit()
    conn.close()

    # Log missing parents
    if missing_parents:
        with open(MISSING_PARENTS_LOG, "w", encoding="utf-8") as f:
            for child, parent in missing_parents:
                f.write(f"Child: {child}, Missing Parent: {parent}\n")
        logging.warning(f"Logged {len(missing_parents)} missing parents to {MISSING_PARENTS_LOG}")

    logging.info(f"Processing complete. Added {relations_added} relations and {forms_added} forms.")

if __name__ == "__main__":
    parse_greek_morphology()
