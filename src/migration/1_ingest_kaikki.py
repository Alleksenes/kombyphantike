import sqlite3
import json
import logging
import sys
from pathlib import Path
from tqdm import tqdm

# --- CONFIGURATION ---
# Ensure src is in path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import KAIKKI_EN_FILE, PROCESSED_DIR

# Database Path
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
BATCH_SIZE = 5000

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


# --- DATABASE SCHEMA ---
def create_schema(cursor):
    """Defines the Bedrock Schema."""
    # Lemmas: The Atoms
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT NOT NULL UNIQUE,
            pos TEXT,
            ipa TEXT,
            etymology_json TEXT
        )
    """
    )
    # Forms: The Shape Shifters (Paradigm)
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
    # Relations: The Constellation (Synonyms, Roots)
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
    # Indexing for Speed
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lemma_text ON lemmas(lemma_text)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_forms_lemma ON forms(lemma_id)")


# --- INGESTION LOGIC ---
def ingest_kaikki():
    if not KAIKKI_EN_FILE.exists():
        logging.error(f"Kaikki dictionary not found at {KAIKKI_EN_FILE}. Aborting.")
        return

    # Pre-calculate size for the Progress Bar (The Architect's foresight)
    logging.info("Measuring the scroll length...")
    total_lines = sum(1 for _ in open(KAIKKI_EN_FILE, "r", encoding="utf-8"))
    logging.info(f"Found {total_lines:,} entries.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    create_schema(cursor)

    count = 0

    with open(KAIKKI_EN_FILE, "r", encoding="utf-8") as f:
        for line in tqdm(f, total=total_lines, desc="Ingesting Kaikki"):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 1. Filter: Greek Only
            if entry.get("lang_code") != "el":
                continue

            lemma_text = entry.get("word")
            if not lemma_text:
                continue

            # 2. Extract Data
            pos = entry.get("pos")

            # IPA (Find first valid IPA)
            ipa = None
            for s in entry.get("sounds", []):
                if "ipa" in s:
                    ipa = s["ipa"]
                    break

            # Structured Etymology
            etymology_json = json.dumps(
                entry.get("etymology_templates", []), ensure_ascii=False
            )

            # 3. Insert Lemma
            cursor.execute(
                """
                INSERT OR IGNORE INTO lemmas (lemma_text, pos, ipa, etymology_json)
                VALUES (?, ?, ?, ?)
            """,
                (lemma_text, pos, ipa, etymology_json),
            )

            # Get ID (whether new or existing)
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma_text,))
            res = cursor.fetchone()
            if not res:
                continue
            lemma_id = res[0]

            # 4. Insert Forms (The Infinite Gym)
            for form in entry.get("forms", []):
                form_text = form.get("form")
                tags = form.get("tags", [])
                if form_text:
                    cursor.execute(
                        """
                        INSERT INTO forms (lemma_id, form_text, tags_json)
                        VALUES (?, ?, ?)
                    """,
                        (lemma_id, form_text, json.dumps(tags, ensure_ascii=False)),
                    )

            # 5. Insert Relations (The Cartographer)
            # We capture ALL semantic links, not just 'related'
            relation_keys = [
                "derived",
                "related",
                "synonyms",
                "antonyms",
                "compounds",
                "descendants",
            ]
            for key in relation_keys:
                for item in entry.get(key, []):
                    parent_text = item.get("word")
                    if parent_text:
                        cursor.execute(
                            """
                            INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type)
                            VALUES (?, ?, ?)
                        """,
                            (lemma_id, parent_text, key),
                        )

            count += 1
            if count % BATCH_SIZE == 0:
                conn.commit()

    conn.commit()
    # Vacuum to reclaim space and optimize pages
    logging.info("Optimizing database structure...")
    conn.execute("VACUUM")
    conn.close()

    logging.info(
        f"Great Migration (Scribe) complete. {count:,} Greek entries saved to {DB_PATH}."
    )


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ingest_kaikki()
