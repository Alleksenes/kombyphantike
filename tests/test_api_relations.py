import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Adjust sys.path to include src
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.api import app

class TestApiRelations(unittest.TestCase):

    @patch("src.api.KombyphantikeEngine")
    def test_get_relations_success(self, MockEngine):
        # Configure the mock engine instance that startup_event will create
        mock_instance = MockEngine.return_value
        mock_db = MagicMock()
        mock_db.get_relations.return_value = {
            "synonyms": ["happy", "joyful"],
            "antonyms": ["sad"]
        }
        mock_instance.db = mock_db

        # Use TestClient as context manager to trigger startup/shutdown
        with TestClient(app) as client:
            response = client.get("/relations/test_word")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "synonyms": ["happy", "joyful"],
                "antonyms": ["sad"]
            })

            # Verify call
            mock_db.get_relations.assert_called_once_with("test_word")

    @patch("src.api.KombyphantikeEngine")
    def test_get_relations_empty(self, MockEngine):
        mock_instance = MockEngine.return_value
        mock_instance.db.get_relations.return_value = {}

        with TestClient(app) as client:
            response = client.get("/relations/unknown")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {})

    def test_get_relations_engine_failure(self):
        # Test case where engine raises an error
        with patch("src.api.KombyphantikeEngine") as MockEngine:
            mock_instance = MockEngine.return_value
            mock_instance.db.get_relations.side_effect = Exception("DB Connection Failed")

            with TestClient(app) as client:
                response = client.get("/relations/error_word")

                self.assertEqual(response.status_code, 500)
                # The generic exception handler in api.py returns the string representation of error
                self.assertIn("DB Connection Failed", response.text)

if __name__ == "__main__":
    unittest.main()
