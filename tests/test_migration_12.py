import sqlite3
import pytest
import importlib.util
import sys
from pathlib import Path
import json

# Define paths
MIGRATION_FILE = Path(__file__).resolve().parent.parent / "src" / "migration" / "12_link_via_etymology.py"

def load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_12", MIGRATION_FILE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["migration_12"] = module
    spec.loader.exec_module(module)
    return module

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_kombyphantike.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE lsj_entries (
            id INTEGER PRIMARY KEY,
            headword TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE lemmas (
            id INTEGER PRIMARY KEY,
            lemma_text TEXT,
            etymology_text TEXT,
            etymology_json TEXT,
            lsj_id INTEGER
        )
    """)

    # Insert LSJ Data
    # Normalization of 'λέξις' -> 'λεξις'
    cursor.execute("INSERT INTO lsj_entries (id, headword) VALUES (1, 'λέξις')")
    cursor.execute("INSERT INTO lsj_entries (id, headword) VALUES (2, 'ἄνθρωπος')") # Normalized: ανθρωπος

    # Insert Lemmas
    # 1. Text match: 'αρχαία ελληνική λέξις'
    cursor.execute("""
        INSERT INTO lemmas (id, lemma_text, etymology_text, etymology_json, lsj_id)
        VALUES (1, 'word1', 'From αρχαία ελληνική λέξις.', NULL, NULL)
    """)

    # 2. JSON match: 'grc' and 'λέξις'
    # Note: verify extract_from_json expects a list
    json_data = json.dumps([
        {"name": "inh", "args": {"1": "el", "2": "grc", "3": "λέξις"}}
    ])
    cursor.execute("""
        INSERT INTO lemmas (id, lemma_text, etymology_text, etymology_json, lsj_id)
        VALUES (2, 'word2', NULL, ?, NULL)
    """, (json_data,))

    # 3. No match
    cursor.execute("""
        INSERT INTO lemmas (id, lemma_text, etymology_text, etymology_json, lsj_id)
        VALUES (3, 'word3', 'Just some text', NULL, NULL)
    """)

    # 4. Text match with 'grc' prefix: 'grc ἄνθρωπος'
    cursor.execute("""
        INSERT INTO lemmas (id, lemma_text, etymology_text, etymology_json, lsj_id)
        VALUES (4, 'word4', 'Derived from grc ἄνθρωπος', NULL, NULL)
    """)

    # 5. Already linked (should be ignored by query, but function logic iterates candidates)
    # The script query filters WHERE lsj_id IS NULL, so this row won't be touched.
    cursor.execute("""
        INSERT INTO lemmas (id, lemma_text, etymology_text, etymology_json, lsj_id)
        VALUES (5, 'word5', 'From αρχαία ελληνική λέξις', NULL, 999)
    """)

    conn.commit()
    conn.close()

    return db_path

def test_migration_logic(temp_db):
    module = load_migration_module()

    # Run migration on temp db
    module.run_migration(temp_db)

    # Verify
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Check word1 -> 1
    cursor.execute("SELECT lsj_id FROM lemmas WHERE id = 1")
    assert cursor.fetchone()[0] == 1, "Failed to link word1 via text regex"

    # Check word2 -> 1
    cursor.execute("SELECT lsj_id FROM lemmas WHERE id = 2")
    assert cursor.fetchone()[0] == 1, "Failed to link word2 via JSON parsing"

    # Check word3 -> NULL
    cursor.execute("SELECT lsj_id FROM lemmas WHERE id = 3")
    assert cursor.fetchone()[0] is None, "Incorrectly linked word3"

    # Check word4 -> 2
    cursor.execute("SELECT lsj_id FROM lemmas WHERE id = 4")
    assert cursor.fetchone()[0] == 2, "Failed to link word4 via 'grc' regex"

    # Check word5 -> 999 (Unchanged)
    cursor.execute("SELECT lsj_id FROM lemmas WHERE id = 5")
    assert cursor.fetchone()[0] == 999, "Incorrectly modified existing link for word5"

    conn.close()
