import sqlite3
import pytest
from pathlib import Path
import sys
import importlib.util

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

def load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_7", "src/migration/7_propagate_metadata.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["migration_7"] = module
    spec.loader.exec_module(module)
    return module

migration_7 = load_migration_module()

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_kombyphantike.db"
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
            lsj_id INTEGER,
            etymology_text TEXT,
            shift_type TEXT
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

    conn.commit()
    conn.close()
    return db_path

def test_propagate_metadata(test_db):
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # 1. Insert Parent with full metadata
    cursor.execute("""
        INSERT INTO lemmas (lemma_text, greek_def, english_def, etymology_text, lsj_id, shift_type)
        VALUES ('parent', 'Parent Greek', 'Parent English', 'Parent Etym', 12345, 'metaphor')
    """)

    # 2. Insert Child with MISSING metadata
    # Note: english_def is empty string to test that case, others are NULL
    cursor.execute("""
        INSERT INTO lemmas (lemma_text, greek_def, english_def, etymology_text, lsj_id, shift_type)
        VALUES ('child', NULL, '', NULL, NULL, NULL)
    """)

    # Get IDs
    cursor.execute("SELECT id FROM lemmas WHERE lemma_text = 'child'")
    child_id = cursor.fetchone()[0]

    # 3. Insert Relation
    cursor.execute("""
        INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type)
        VALUES (?, 'parent', 'form_of')
    """, (child_id,))

    conn.commit()
    conn.close()

    # 4. Run Migration
    migration_7.propagate_metadata(test_db)

    # 5. Verify
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT greek_def, english_def, etymology_text, lsj_id, shift_type FROM lemmas WHERE id = ?", (child_id,))
    row = cursor.fetchone()
    conn.close()

    assert row[0] == 'Parent Greek'
    assert row[1] == 'Parent English'
    assert row[2] == 'Parent Etym'
    assert row[3] == 12345
    assert row[4] == 'metaphor'

def test_no_overwrite_existing(test_db):
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Parent
    cursor.execute("""
        INSERT INTO lemmas (lemma_text, greek_def, english_def)
        VALUES ('parent2', 'Parent Greek', 'Parent English')
    """)

    # Child with EXISTING metadata
    cursor.execute("""
        INSERT INTO lemmas (lemma_text, greek_def, english_def)
        VALUES ('child2', 'Child Greek', 'Child English')
    """)

    cursor.execute("SELECT id FROM lemmas WHERE lemma_text = 'child2'")
    child_id = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type)
        VALUES (?, 'parent2', 'form_of')
    """, (child_id,))

    conn.commit()
    conn.close()

    migration_7.propagate_metadata(test_db)

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT greek_def, english_def FROM lemmas WHERE id = ?", (child_id,))
    row = cursor.fetchone()
    conn.close()

    assert row[0] == 'Child Greek'  # Should NOT change
    assert row[1] == 'Child English' # Should NOT change
