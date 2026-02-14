import sys
import os
import sqlite3
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# --- MOCKING ---
# We must mock before importing the script because it does 'from google.cloud import ...' at top level
mock_translate = MagicMock()
mock_client_instance = MagicMock()
mock_translate.Client.return_value = mock_client_instance

# Setup sys.modules
mock_cloud = MagicMock()
mock_cloud.translate_v2 = mock_translate
sys.modules['google.cloud'] = mock_cloud
sys.modules['google.cloud.translate_v2'] = mock_translate

# Mock dotenv
mock_dotenv = MagicMock()
sys.modules['dotenv'] = mock_dotenv

# Import script dynamically
import importlib.util
script_path = Path(__file__).resolve().parent.parent / "src/migration/11_translate_missing_defs.py"
spec = importlib.util.spec_from_file_location("migration_script_apikey", script_path)
migration_script = importlib.util.module_from_spec(spec)
sys.modules["src.migration.11_translate_missing_defs"] = migration_script
spec.loader.exec_module(migration_script)

def test_api_key_initialization():
    # Setup temporary DB and checkpoint
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp_db, \
         tempfile.NamedTemporaryFile(suffix=".txt") as tmp_ckpt:

        db_path = Path(tmp_db.name)
        ckpt_path = Path(tmp_ckpt.name)

        # Create dummy DB structure
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE lemmas (id INTEGER PRIMARY KEY, greek_def TEXT, english_def TEXT, modern_def TEXT)")
        conn.execute("INSERT INTO lemmas VALUES (1, 'g1', '', '')")
        conn.commit()
        conn.close()

        # Set Environment Variable
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test_api_key_123"}, clear=True):
            # Reset mock
            mock_translate.Client.reset_mock()

            # Run
            migration_script.run_migration(db_path, ckpt_path)

            # Check call args
            args, kwargs = mock_translate.Client.call_args

            # Verify client_options is present and correct
            # We expect Client(client_options={"api_key": "test_api_key_123"})
            assert kwargs is not None, "Client called with no keyword arguments"
            assert "client_options" in kwargs, "client_options not found in call args"
            assert kwargs["client_options"] == {"api_key": "test_api_key_123"}, "api_key mismatch in client_options"

def test_fallback_initialization():
    # Setup temporary DB
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp_db, \
         tempfile.NamedTemporaryFile(suffix=".txt") as tmp_ckpt:

        db_path = Path(tmp_db.name)
        ckpt_path = Path(tmp_ckpt.name)

        # Create dummy DB
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE lemmas (id INTEGER PRIMARY KEY, greek_def TEXT, english_def TEXT, modern_def TEXT)")
        conn.commit()
        conn.close()

        # Ensure NO Environment Variable
        with patch.dict(os.environ, {}, clear=True):
             if "GOOGLE_API_KEY" in os.environ:
                 del os.environ["GOOGLE_API_KEY"]

             mock_translate.Client.reset_mock()

             migration_script.run_migration(db_path, ckpt_path)

             # Check call args
             args, kwargs = mock_translate.Client.call_args
             # If kwargs are present, ensure api_key is not in client_options
             if kwargs and "client_options" in kwargs:
                 assert "api_key" not in kwargs["client_options"], "Unexpected api_key found"
