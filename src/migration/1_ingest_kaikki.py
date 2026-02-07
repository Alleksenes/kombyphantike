import sqlite3
import json
from pathlib import Path
from tqdm import tqdm
import sys

# Ensure src is in path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.config import KAIKKI_EN_FILE, PROCESSED_DIR

DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"

def init_db(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT UNIQUE,
            pos TEXT,
            ipa TEXT,
            etymology_json TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_id INTEGER,
            form_text TEXT,
            tags_json TEXT,
            FOREIGN KEY(lemma_id) REFERENCES lemmas(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_lemma_id INTEGER,
            parent_lemma_text TEXT,
            relation_type TEXT,
            FOREIGN KEY(child_lemma_id) REFERENCES lemmas(id)
        )
    """)
    conn.commit()

def process_file():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    cursor = conn.cursor()

    count = 0

    # Check if file exists
    if not KAIKKI_EN_FILE.exists():
        print(f"File {KAIKKI_EN_FILE} not found! Please ensure data/dictionaries/kaikki-en.jsonl exists.")
        conn.close()
        return

    print(f"Ingesting from {KAIKKI_EN_FILE} into {DB_PATH}...")

    with open(KAIKKI_EN_FILE, "r", encoding="utf-8") as f:
        # Use tqdm for progress bar
        # We don't know total lines unless we wc -l first, but we can stream
        for line in tqdm(f, desc="Processing lines"):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Filter for Greek (el)
            if entry.get("lang_code") != "el":
                continue

            lemma_text = entry.get("word")
            if not lemma_text:
                continue

            pos = entry.get("pos")

            # Extract IPA (first one found)
            ipa = None
            sounds = entry.get("sounds", [])
            for s in sounds:
                if "ipa" in s:
                    ipa = s["ipa"]
                    break

            # Store etymology templates as JSON string
            etymology_json = json.dumps(entry.get("etymology_templates", []), ensure_ascii=False)

            # Insert Lemma
            # Use INSERT OR IGNORE to handle uniqueness constraint on lemma_text
            cursor.execute("""
                INSERT OR IGNORE INTO lemmas (lemma_text, pos, ipa, etymology_json)
                VALUES (?, ?, ?, ?)
            """, (lemma_text, pos, ipa, etymology_json))

            # Retrieve the ID (whether inserted or existing)
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma_text,))
            row = cursor.fetchone()
            if not row:
                continue
            lemma_id = row[0]

            # Insert Forms
            forms = entry.get("forms", [])
            for form in forms:
                form_text = form.get("form")
                tags = form.get("tags", [])
                if form_text:
                    cursor.execute("""
                        INSERT INTO forms (lemma_id, form_text, tags_json)
                        VALUES (?, ?, ?)
                    """, (lemma_id, form_text, json.dumps(tags, ensure_ascii=False)))

            # Insert Relations
            # Check keys: derived, related, synonyms, antonyms, compounds, descendants
            relation_keys = ["derived", "related", "synonyms", "antonyms", "compounds", "descendants"]
            for key in relation_keys:
                items = entry.get(key, [])
                for item in items:
                    parent_text = item.get("word")
                    if parent_text:
                        cursor.execute("""
                            INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type)
                            VALUES (?, ?, ?)
                        """, (lemma_id, parent_text, key))

            count += 1
            # Batch Commit
            if count % 5000 == 0:
                conn.commit()

    conn.commit()
    conn.close()
    print(f"Ingestion complete. Processed {count} Greek entries.")

if __name__ == "__main__":
    process_file()
