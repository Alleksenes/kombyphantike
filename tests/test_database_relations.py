import unittest
import sqlite3
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Adjust sys.path to include src
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir.parent))

from src.database import DatabaseManager

class TestDatabaseRelations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path("temp_test_data")
        self.temp_dir.mkdir(exist_ok=True)
        self.db_path = self.temp_dir / "kombyphantike_v2.db"
        self.create_test_db(self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()
        if self.temp_dir.exists():
            self.temp_dir.rmdir()

    def create_test_db(self, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create Schema
        cursor.execute("""
            CREATE TABLE lemmas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lemma_text TEXT NOT NULL UNIQUE,
                pos TEXT,
                ipa TEXT,
                etymology_json TEXT,
                greek_def TEXT,
                english_def TEXT,
                lsj_id INTEGER
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
        cursor.execute("""
            CREATE TABLE relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_lemma_id INTEGER NOT NULL,
                parent_lemma_text TEXT NOT NULL,
                relation_type TEXT,
                FOREIGN KEY(child_lemma_id) REFERENCES lemmas(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE lsj_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_json TEXT
            )
        """)

        # Populate Data
        # 1. Parent Lemma: 'ισχύω'
        cursor.execute("INSERT INTO lemmas (lemma_text, pos) VALUES (?, ?)", ("ισχύω", "verb"))
        parent_id = cursor.lastrowid

        # 2. Forms for 'ισχύω'
        forms = [
            ("ισχύω", ["pres", "ind", "1s"]),
            ("ισχύεις", ["pres", "ind", "2s"]),
            ("ισχύει", ["pres", "ind", "3s"]),
        ]
        for form, tags in forms:
            cursor.execute("INSERT INTO forms (lemma_id, form_text, tags_json) VALUES (?, ?, ?)",
                           (parent_id, form, json.dumps(tags)))

        # 3. Child Lemma: 'ισχύει' (as a headword entry that has no forms attached directly)
        cursor.execute("INSERT INTO lemmas (lemma_text, pos) VALUES (?, ?)", ("ισχύει", "verb"))
        child_id = cursor.lastrowid

        # 4. Relation: 'ισχύει' is form_of 'ισχύω'
        cursor.execute("INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type) VALUES (?, ?, ?)",
                       (child_id, "ισχύω", "form_of"))

        conn.commit()
        conn.close()

    def test_get_paradigm_direct(self):
        with patch("src.database.PROCESSED_DIR", self.temp_dir):
            db = DatabaseManager()
            paradigm = db.get_paradigm("ισχύω")
            self.assertIsNotNone(paradigm)
            forms = [p['form'] for p in paradigm]
            self.assertIn("ισχύω", forms)
            db.close()

    def test_get_paradigm_via_relation(self):
        with patch("src.database.PROCESSED_DIR", self.temp_dir):
            db = DatabaseManager()
            paradigm = db.get_paradigm("ισχύει")
            self.assertIsNotNone(paradigm)

            forms = [p['form'] for p in paradigm]
            self.assertIn("ισχύω", forms)
            self.assertIn("ισχύει", forms)

            # Check for is_current_form flag
            current_form_entry = next((p for p in paradigm if p.get('is_current_form')), None)
            self.assertIsNotNone(current_form_entry)
            self.assertEqual(current_form_entry['form'], "ισχύει")

            db.close()

if __name__ == "__main__":
    unittest.main()
