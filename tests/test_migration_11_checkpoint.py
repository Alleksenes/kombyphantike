import sys
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock

# Mock google.cloud and google.cloud.translate_v2
mock_translate = MagicMock()
mock_client = MagicMock()
mock_translate.Client.return_value = mock_client

# Ensure from google.cloud import translate_v2 works
mock_cloud = MagicMock()
mock_cloud.translate_v2 = mock_translate
sys.modules['google.cloud'] = mock_cloud
# Also set direct module entry just in case
sys.modules['google.cloud.translate_v2'] = mock_translate

# Mock dotenv
sys.modules['dotenv'] = MagicMock()

# Import the migration script dynamically
import importlib.util
script_path = Path(__file__).resolve().parent.parent / "src/migration/11_translate_missing_defs.py"
spec = importlib.util.spec_from_file_location("migration_script", script_path)
migration_script = importlib.util.module_from_spec(spec)
sys.modules["src.migration.11_translate_missing_defs"] = migration_script
spec.loader.exec_module(migration_script)

class TestMigration11:
    def test_checkpoint_and_cache(self):
        # Set small batch size to test batching and caching across batches
        migration_script.BATCH_SIZE = 2

        # Verify the script is using our mock
        # print(f"DEBUG: Script translate object: {migration_script.translate}")
        # print(f"DEBUG: Mock translate object: {mock_translate}")
        # assert migration_script.translate == mock_translate

        with tempfile.NamedTemporaryFile(suffix=".db") as tmp_db, \
             tempfile.NamedTemporaryFile(suffix=".txt") as tmp_ckpt:

            db_path = Path(tmp_db.name)
            ckpt_path = Path(tmp_ckpt.name)

            # Initialize DB Schema and Data
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE lemmas (
                    id INTEGER PRIMARY KEY,
                    greek_def TEXT,
                    english_def TEXT,
                    modern_def TEXT
                )
            """)

            # Insert Test Data
            cursor.execute("INSERT INTO lemmas (id, greek_def, english_def, modern_def) VALUES (1, 'g1', 'e1', 'm1')")
            cursor.execute("INSERT INTO lemmas (id, greek_def, english_def, modern_def) VALUES (2, 'g2', NULL, NULL)")
            cursor.execute("INSERT INTO lemmas (id, greek_def, english_def, modern_def) VALUES (3, 'g3', NULL, '')")
            cursor.execute("INSERT INTO lemmas (id, greek_def, english_def, modern_def) VALUES (4, 'g2', NULL, NULL)")
            cursor.execute("INSERT INTO lemmas (id, greek_def, english_def, modern_def) VALUES (5, 'g4', NULL, NULL)")

            conn.commit()
            conn.close()

            with open(ckpt_path, 'w') as f:
                f.write("1")

            # Setup API Mock Side Effect
            def translate_side_effect(values, target_language=None, format_=None):
                res = []
                for v in values:
                    res.append({'translatedText': f"EN_{v}"})
                return res

            mock_client.translate.side_effect = translate_side_effect

            # Run Migration
            migration_script.run_migration(db_path, ckpt_path)

            # --- VERIFICATION ---

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            rows = cursor.execute("SELECT id, english_def FROM lemmas ORDER BY id").fetchall()
            conn.close()

            # Row 1: Skipped/Unchanged
            assert rows[0] == (1, 'e1')

            # Row 2: Translated
            assert rows[1] == (2, 'EN_g2')

            # Row 3: Translated
            assert rows[2] == (3, 'EN_g3')

            # Row 4: Translated (Should be EN_g2)
            assert rows[3] == (4, 'EN_g2')

            # Row 5: Translated
            assert rows[4] == (5, 'EN_g4')

            with open(ckpt_path, 'r') as f:
                content = f.read().strip()
                assert content == "5"

            assert mock_client.translate.call_count == 2
