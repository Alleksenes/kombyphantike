import sqlite3
import json
import os
import shutil
from pathlib import Path
import sys

# Ensure src is in path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.database import DatabaseManager
from src.config import PROCESSED_DIR

# Temporary DB Path
TEST_DB_PATH = PROCESSED_DIR / "test_kombyphantike_v2.db"
ORIG_DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"

def setup_test_db():
    if TEST_DB_PATH.exists():
        os.remove(TEST_DB_PATH)

    conn = sqlite3.connect(TEST_DB_PATH)
    cursor = conn.cursor()

    # Create Schema (Simplified for test)
    cursor.execute("""
        CREATE TABLE lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT NOT NULL UNIQUE,
            pos TEXT,
            ipa TEXT,
            etymology_json TEXT,
            lsj_id INTEGER,
            english_def TEXT,
            greek_def TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_id INTEGER NOT NULL,
            form_text TEXT NOT NULL,
            tags_json TEXT,
            FOREIGN KEY(lemma_id) REFERENCES lemmas(id)
        )
    """)

    # Insert Mock Data
    cursor.execute("INSERT INTO lemmas (lemma_text, pos) VALUES (?, ?)", ("γράφω", "verb"))
    lemma_id = cursor.lastrowid

    # 1. Present Active Indicative 1st Person Singular
    # Kaikki tags: ["present", "imperfective", "active", "indicative", "first-person", "singular"]
    tags_present = ["present", "imperfective", "active", "indicative", "first-person", "singular"]
    cursor.execute("INSERT INTO forms (lemma_id, form_text, tags_json) VALUES (?, ?, ?)",
                   (lemma_id, "γράφω", json.dumps(tags_present)))

    # 2. Aorist Active Indicative 1st Person Singular
    # Kaikki tags: ["past", "perfective", "active", "indicative", "first-person", "singular"]
    tags_aorist = ["past", "perfective", "active", "indicative", "first-person", "singular"]
    cursor.execute("INSERT INTO forms (lemma_id, form_text, tags_json) VALUES (?, ?, ?)",
                   (lemma_id, "έγραψα", json.dumps(tags_aorist)))

    conn.commit()
    conn.close()

def test_paradigm_synthesis():
    # Swap DB temporarily
    if ORIG_DB_PATH.exists():
        shutil.move(ORIG_DB_PATH, str(ORIG_DB_PATH) + ".bak")

    shutil.copy(TEST_DB_PATH, ORIG_DB_PATH)

    try:
        db = DatabaseManager()
        paradigm = db.get_paradigm("γράφω")

        print("\n--- Paradigm Check ---")

        found_aorist = False
        found_present = False

        for form in paradigm:
            tags = form.get("tags", [])
            form_text = form.get("form")
            print(f"Form: {form_text}, Tags: {tags}")

            # Check for Synthesized Tags
            has_Aorist = "Aorist" in tags
            has_Present = "Present" in tags
            has_1 = "1" in tags

            if form_text == "έγραψα":
                if has_Aorist and has_1:
                    print("✅ Aorist form has 'Aorist' and '1' tags.")
                    found_aorist = True
                else:
                    print("❌ Aorist form MISSING 'Aorist' or '1' tags.")

            if form_text == "γράφω":
                if has_Present and has_1:
                    print("✅ Present form has 'Present' and '1' tags.")
                    found_present = True
                else:
                    print("❌ Present form MISSING 'Present' or '1' tags.")

        if found_aorist and found_present:
            print("\n🎉 SUCCESS: Tags are correctly synthesized!")
        else:
            print("\n⚠️ FAILURE: Tags are NOT synthesized yet.")

    finally:
        # Restore DB
        if os.path.exists(str(ORIG_DB_PATH) + ".bak"):
            if ORIG_DB_PATH.exists():
                os.remove(ORIG_DB_PATH)
            shutil.move(str(ORIG_DB_PATH) + ".bak", ORIG_DB_PATH)
        elif ORIG_DB_PATH.exists(): # Cleanup if it was just copied
             os.remove(ORIG_DB_PATH)

        if TEST_DB_PATH.exists():
            os.remove(TEST_DB_PATH)

if __name__ == "__main__":
    setup_test_db()
    test_paradigm_synthesis()
