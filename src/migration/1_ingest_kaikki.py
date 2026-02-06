import json
import sqlite3
from pathlib import Path
import sys
from tqdm import tqdm

# Constants
INPUT_FILE = Path("data/dictionaries/kaikki-en.jsonl")
DB_FILE = Path("data/processed/kombyphantike_v2.db")
BATCH_SIZE = 1000

def init_db(conn):
    """Initialize the database with the required schema."""
    cursor = conn.cursor()

    # Create lemmas table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lemmas (
        id INTEGER PRIMARY KEY,
        lemma_text TEXT UNIQUE,
        pos TEXT,
        ipa TEXT,
        etymology_json TEXT
    )
    """)

    # Create forms table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS forms (
        id INTEGER PRIMARY KEY,
        lemma_id INTEGER,
        form_text TEXT,
        tags_json TEXT,
        FOREIGN KEY (lemma_id) REFERENCES lemmas (id)
    )
    """)

    # Create relations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relations (
        id INTEGER PRIMARY KEY,
        child_lemma_id INTEGER,
        parent_lemma_text TEXT,
        relation_type TEXT,
        FOREIGN KEY (child_lemma_id) REFERENCES lemmas (id)
    )
    """)

    conn.commit()

def extract_ipa(entry):
    """Extract IPA from the entry."""
    sounds = entry.get("sounds", [])
    for sound in sounds:
        if "ipa" in sound:
            return sound["ipa"]
    return None

def process_line(cursor, line):
    """Process a single line from the JSONL file."""
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return

    if entry.get("lang_code") != "el":
        return

    lemma_text = entry.get("word")
    if not lemma_text:
        return

    pos = entry.get("pos")
    ipa = extract_ipa(entry)

    # Extract etymology
    etymology_text = entry.get("etymology_text")
    etymology_json = json.dumps({"etymology_text": etymology_text}) if etymology_text else None

    try:
        # Insert or Ignore to handle unique constraint on lemma_text
        cursor.execute(
            "INSERT OR IGNORE INTO lemmas (lemma_text, pos, ipa, etymology_json) VALUES (?, ?, ?, ?)",
            (lemma_text, pos, ipa, etymology_json)
        )

        # Get lemma_id
        if cursor.rowcount > 0:
            lemma_id = cursor.lastrowid
        else:
            # If it already existed, fetch the ID
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma_text,))
            result = cursor.fetchone()
            if result:
                lemma_id = result[0]
            else:
                # This should logically not happen if the insert failed due to uniqueness
                return

        # Forms
        forms = entry.get("forms", [])
        for form in forms:
            form_text = form.get("form")
            if form_text:
                tags = form.get("tags", [])
                tags_json = json.dumps(tags)
                cursor.execute(
                    "INSERT INTO forms (lemma_id, form_text, tags_json) VALUES (?, ?, ?)",
                    (lemma_id, form_text, tags_json)
                )

        # Relations
        related = entry.get("related", [])
        for rel in related:
            parent_text = rel.get("word")
            if parent_text:
                tags = rel.get("tags", [])
                relation_type = json.dumps(tags) if tags else None
                cursor.execute(
                    "INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type) VALUES (?, ?, ?)",
                    (lemma_id, parent_text, relation_type)
                )

    except sqlite3.IntegrityError as e:
        print(f"Error inserting {lemma_text}: {e}", file=sys.stderr)

def main():
    if not INPUT_FILE.exists():
        print(f"Error: Input file {INPUT_FILE} not found.", file=sys.stderr)
        return

    # Ensure output directory exists
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_FILE)
    init_db(conn)
    cursor = conn.cursor()

    print(f"Ingesting from {INPUT_FILE} to {DB_FILE}...")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        # Iterate over lines with progress bar
        for i, line in tqdm(enumerate(f)):
            process_line(cursor, line)

            if i % BATCH_SIZE == 0:
                conn.commit()

    conn.commit()
    conn.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    main()
