import sqlite3
import json
import logging
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import KAIKKI_EL_FILE, PROCESSED_DIR

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
BATCH_SIZE = 5000

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def create_schema(cursor):
    """Destroys and Rebuilds the World."""
    cursor.execute("DROP TABLE IF EXISTS relations")
    cursor.execute("DROP TABLE IF EXISTS forms")
    cursor.execute("DROP TABLE IF EXISTS lemmas")

    # Lemmas: Now with Greek Definition (Crucial)
    cursor.execute(
        """
        CREATE TABLE lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT NOT NULL UNIQUE,
            pos TEXT,
            ipa TEXT,
            etymology_json TEXT,
            greek_def TEXT, 
            english_def TEXT,
            lsj_id INTEGER -- Placeholder for the Weaver
        )
    """
    )

    # Forms: The Paradigm
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

    # Relations: The Soft Links
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
    cursor.execute(
        "CREATE INDEX idx_forms_text ON forms(form_text)"
    )  # Crucial for Reverse Lookup


def ingest_kaikki_el():
    if not KAIKKI_EL_FILE.exists():
        logging.error(f"File not found: {KAIKKI_EL_FILE}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    logging.info("Resetting Schema...")
    create_schema(cursor)

    logging.info("Counting lines...")
    total_lines = sum(1 for _ in open(KAIKKI_EL_FILE, "r", encoding="utf-8"))

    logging.info("Ingesting...")
    count = 0

    with open(KAIKKI_EL_FILE, "r", encoding="utf-8") as f:
        for line in tqdm(f, total=total_lines):
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

            # Etymology (Raw)
            etym = json.dumps(entry.get("etymology_templates", []), ensure_ascii=False)

            # Definitions
            # Kaikki-EL usually puts definitions in 'senses' -> 'glosses'
            greek_defs = []
            form_of_parents = set()

            for sense in entry.get("senses", []):
                # 1. Grab Greek Definition
                if "glosses" in sense:
                    greek_defs.extend(sense["glosses"])

                # 2. Grab Redirects (The Soft Link)
                # Look for "form_of", "alt_of", "inflection_of"
                for tag in ["form_of", "alt_of", "inflection_of"]:
                    if tag in sense:
                        for ref in sense[tag]:
                            if "word" in ref:
                                form_of_parents.add(ref["word"])

            greek_def_str = " | ".join(greek_defs) if greek_defs else ""

            # Insert Lemma
            cursor.execute(
                """
                INSERT OR IGNORE INTO lemmas (lemma_text, pos, ipa, etymology_json, greek_def)
                VALUES (?, ?, ?, ?, ?)
            """,
                (word, pos, ipa, etym, greek_def_str),
            )

            # Get the ID we just inserted (or retrieved)
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (word,))
            res = cursor.fetchone()
            if not res:
                continue
            lemma_id = res[0]

            # Insert Relations (The Fix for ισχύει)
            for parent in form_of_parents:
                cursor.execute(
                    """
                    INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type)
                    VALUES (?, ?, 'form_of')
                """,
                    (lemma_id, parent),
                )

            # Insert Forms (The Paradigm)
            # Kaikki-EL flattens forms nicely
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
                            (lemma_id, f_text, json.dumps(f_tags, ensure_ascii=False)),
                        )

            count += 1
            if count % BATCH_SIZE == 0:
                conn.commit()

    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    logging.info("Ingestion Complete.")


if __name__ == "__main__":
    ingest_kaikki_el()
