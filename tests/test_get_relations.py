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

class TestGetRelations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path("temp_test_data_relations")
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
            CREATE TABLE relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                child_lemma_id INTEGER NOT NULL,
                parent_lemma_text TEXT NOT NULL,
                relation_type TEXT,
                FOREIGN KEY(child_lemma_id) REFERENCES lemmas(id)
            )
        """)

        # Populate Data
        # 1. Lemma: 'χαρά' (joy)
        cursor.execute("INSERT INTO lemmas (lemma_text, pos) VALUES (?, ?)", ("χαρά", "noun"))
        lemma_id = cursor.lastrowid

        # 2. Relations for 'χαρά'
        cursor.execute("INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type) VALUES (?, ?, ?)",
                       (lemma_id, "ευτυχία", "synonyms"))
        cursor.execute("INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type) VALUES (?, ?, ?)",
                       (lemma_id, "λύπη", "antonyms"))
        cursor.execute("INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type) VALUES (?, ?, ?)",
                       (lemma_id, "χαίρομαι", "derived"))

        conn.commit()
        conn.close()

    def test_get_relations_success(self):
        with patch("src.database.PROCESSED_DIR", self.temp_dir):
            db = DatabaseManager()
            # We assume get_relations is implemented. It's not yet, so this test will fail if run now.
            # However, we are writing the test first (TDD).
            try:
                relations = db.get_relations("χαρά")
            except AttributeError:
                self.fail("DatabaseManager has no attribute 'get_relations'")

            expected = {
                "synonyms": ["ευτυχία"],
                "antonyms": ["λύπη"],
                "derived": ["χαίρομαι"]
            }

            # Since order in list might not be guaranteed if multiple entries exist,
            # we should check content. Here only one entry per type.
            self.assertEqual(relations.get("synonyms"), ["ευτυχία"])
            self.assertEqual(relations.get("antonyms"), ["λύπη"])
            self.assertEqual(relations.get("derived"), ["χαίρομαι"])

            db.close()

    def test_get_relations_not_found(self):
        with patch("src.database.PROCESSED_DIR", self.temp_dir):
            db = DatabaseManager()
            try:
                relations = db.get_relations("unknown_word")
            except AttributeError:
                self.fail("DatabaseManager has no attribute 'get_relations'")

            self.assertEqual(relations, {})
            db.close()

if __name__ == "__main__":
    unittest.main()
