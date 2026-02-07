import sqlite3
import json
import tempfile
import pytest
import sys
import importlib.util
from pathlib import Path

# Dynamic import for the migration script because its name starts with a digit
def import_migration_module():
    file_path = Path("src/migration/1c_augment_kaikki_en.py").resolve()
    spec = importlib.util.spec_from_file_location("migration_1c", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["migration_1c"] = module
    spec.loader.exec_module(module)
    return module

migration_module = import_migration_module()

@pytest.fixture
def temp_db():
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create schema WITHOUT the new columns to test schema migration
    cursor.execute("""
        CREATE TABLE lemmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lemma_text TEXT NOT NULL UNIQUE
        )
    """)

    # Insert test data
    cursor.execute("INSERT INTO lemmas (lemma_text) VALUES ('νερό')")
    cursor.execute("INSERT INTO lemmas (lemma_text) VALUES ('γάτα')")

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if db_path.exists():
        db_path.unlink()

@pytest.fixture
def temp_jsonl():
    # Create a temporary JSONL file
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode='w', encoding='utf-8') as tmp:
        # 1. Matching entry for 'νερό' (Water)
        entry1 = {
            "word": "νερό",
            "lang_code": "el",
            "senses": [{"glosses": ["water"]}],
            "etymology_text": "From ancient Greek generic."
        }
        tmp.write(json.dumps(entry1) + "\n")

        # 2. Matching entry for 'γάτα' (Cat)
        entry2 = {
            "word": "γάτα",
            "lang_code": "el",
            "senses": [{"glosses": ["cat", "feline"]}],
            "etymology_text": "From ancient times."
        }
        tmp.write(json.dumps(entry2) + "\n")

        # 3. Non-Greek entry (should be ignored)
        entry3 = {
            "word": "water",
            "lang_code": "en",
            "senses": [{"glosses": ["liquid"]}],
            "etymology_text": "Germanic."
        }
        tmp.write(json.dumps(entry3) + "\n")

    yield Path(tmp.name)

    # Cleanup
    if Path(tmp.name).exists():
        Path(tmp.name).unlink()

def test_migration_1c(temp_db, temp_jsonl):
    # Run the migration logic
    migration_module.run_migration(db_path=temp_db, jsonl_path=temp_jsonl)

    # Verify results
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Check if columns were added (if not, this query will fail)
    try:
        cursor.execute("SELECT english_def, etymology_text FROM lemmas WHERE lemma_text = 'νερό'")
        res_nero = cursor.fetchone()
    except sqlite3.OperationalError as e:
        pytest.fail(f"Columns missing: {e}")

    assert res_nero[0] == "water"
    assert res_nero[1] == "From ancient Greek generic."

    # Check 'γάτα'
    cursor.execute("SELECT english_def, etymology_text FROM lemmas WHERE lemma_text = 'γάτα'")
    res_gata = cursor.fetchone()
    assert res_gata[0] == "cat | feline"
    assert res_gata[1] == "From ancient times."

    conn.close()
