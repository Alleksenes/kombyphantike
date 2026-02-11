import sqlite3
import json
import pytest
from pathlib import Path
import sys
import importlib.util

# Load the migration module dynamically because it starts with a number
migration_file = Path(__file__).resolve().parent.parent / "src" / "migration" / "10_master_hydration.py"
spec = importlib.util.spec_from_file_location("master_hydration", migration_file)
master_hydration = importlib.util.module_from_spec(spec)
sys.modules["master_hydration"] = master_hydration
spec.loader.exec_module(master_hydration)


@pytest.fixture
def temp_db(tmp_path):
    # Setup temporary database
    db_path = tmp_path / "test_kombyphantike.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
    CREATE TABLE lemmas (
        id INTEGER PRIMARY KEY,
        lemma_text TEXT,
        lsj_id INTEGER,
        kds_score INTEGER,
        etymology_text TEXT,
        transliteration TEXT,
        entry_json TEXT
    )
    """)
    # Note: added entry_json to lemmas just in case, though lsj_entries has it.
    # But wait, the script queries lsj_entries.entry_json.

    cursor.execute("""
    CREATE TABLE lsj_entries (
        id INTEGER PRIMARY KEY,
        headword TEXT,
        entry_json TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE relations (
        id INTEGER PRIMARY KEY,
        child_lemma_id INTEGER,
        parent_lemma_text TEXT,
        relation_type TEXT
    )
    """)

    # Insert Data

    # 1. KDS Inheritance Case
    # Parent: KDS 20
    cursor.execute("INSERT INTO lemmas (id, lemma_text, kds_score) VALUES (1, 'μήτηρ', 20)")
    # Child: KDS 80 (should inherit 20)
    cursor.execute("INSERT INTO lemmas (id, lemma_text, kds_score) VALUES (2, 'μητέρος', 80)")
    # Relation
    cursor.execute("INSERT INTO relations (child_lemma_id, parent_lemma_text, relation_type) VALUES (2, 'μήτηρ', 'form_of')")

    # 2. Fuzzy Linking Case
    # LSJ Entry: 'ἄγγελος' (ID 100)
    cursor.execute("INSERT INTO lsj_entries (id, headword, entry_json) VALUES (100, 'ἄγγελος', '{}')")
    # Lemma: 'άγγελος' (Modern, no ID) -> Should match
    cursor.execute("INSERT INTO lemmas (id, lemma_text, lsj_id) VALUES (3, 'άγγελος', NULL)")

    # 3. LSJ Excavation Case
    # Lemma Linked to ID 200
    cursor.execute("INSERT INTO lemmas (id, lemma_text, lsj_id) VALUES (4, 'φιλοσοφία', 200)")
    # LSJ Entry 200 with messy definitions
    # JSON structure: {"senses": [{"definition": "..."}]}
    entry_data = {
        "senses": [
            {"definition": "love of knowledge, wisdom, freq. in Pi. P. 4.102; cultivated pursuit."},
            {"definition": "scientific inquiry, method, system, opp. mere empiricism."},
            {"definition": "tragic irony in S. OT 1430; bad definition that should not appear due to limit."}
        ]
    }
    cursor.execute("INSERT INTO lsj_entries (id, headword, entry_json) VALUES (200, 'φιλοσοφία', ?)", (json.dumps(entry_data),))

    # 4. Transliteration Case
    # Lemma needing transliteration
    cursor.execute("INSERT INTO lemmas (id, lemma_text) VALUES (5, 'Καλημέρα')")

    conn.commit()
    conn.close()
    return db_path


def test_master_hydration_logic(temp_db):
    # Run Migration on temp_db
    # Pass db_path=temp_db to run_migration
    master_hydration.run_migration(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # --- Verify KDS Inheritance ---
    cursor.execute("SELECT kds_score FROM lemmas WHERE id = 2")
    child_score = cursor.fetchone()[0]
    # Should inherit 20 from parent
    assert child_score == 20, f"Child KDS should be 20, got {child_score}"

    # --- Verify Fuzzy Linking ---
    cursor.execute("SELECT lsj_id FROM lemmas WHERE id = 3")
    row = cursor.fetchone()
    assert row is not None
    linked_id = row[0]
    # Should link to LSJ ID 100 ('ἄγγελος' normalized matches 'άγγελος')
    assert linked_id == 100, f"Lemma 3 should be linked to LSJ 100, got {linked_id}"

    # --- Verify LSJ Excavation & Cleaning ---
    cursor.execute("SELECT etymology_text FROM lemmas WHERE id = 4")
    row = cursor.fetchone()
    assert row is not None
    etym_text = row[0]
    print(f"DEBUG: etymology_text='{etym_text}'")

    # Expected cleanup:
    # "love of knowledge, wisdom, freq. in Pi. P. 4.102; cultivated pursuit." -> "love of knowledge, wisdom; cultivated pursuit"
    # "scientific inquiry, method, system, opp. mere empiricism." -> "scientific inquiry, method, system, mere empiricism" (opp. stripped)

    assert "love of knowledge, wisdom" in etym_text
    # "cultivated pursuit" might be part of the first definition string after semicolon if the source had it?
    # Wait, the source string is "love of knowledge...; cultivated pursuit."
    # My cleaner cleans the whole string.
    # ABBREV_PATTERN removes "freq." and "opp.".
    # CITATION_PATTERN removes "Pi. P. 4.102".

    # Check for absence of stripped patterns
    assert "Pi." not in etym_text
    assert "freq." not in etym_text
    assert "opp." not in etym_text
    assert "S. OT" not in etym_text

    # Check for content presence
    assert "scientific inquiry" in etym_text
    assert "tragic irony" in etym_text

    # --- Verify Transliteration ---
    cursor.execute("SELECT transliteration FROM lemmas WHERE id = 5")
    row = cursor.fetchone()
    assert row is not None
    translit_text = row[0]
    assert translit_text == "Kalimera", f"Transliteration failed for 'Καλημέρα', got {translit_text}"

    # Check inheritance of transliteration for 'μήτηρ' (ID 1)
    cursor.execute("SELECT transliteration FROM lemmas WHERE id = 1")
    t1 = cursor.fetchone()[0]
    # 'μήτηρ' -> 'mitir' usually
    assert t1 is not None
    assert len(t1) > 0

    conn.close()
