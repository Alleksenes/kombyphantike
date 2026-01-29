import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api import app

class TestApiFill(unittest.TestCase):
    def test_fill_curriculum_tokenization(self):
        client = TestClient(app)

        # Mock engine
        mock_engine = MagicMock()
        # Setup tokenize_text to return something specific
        def side_effect(text, lang):
            return [{"text": text, "lang": lang, "is_alpha": True}]
        mock_engine.tokenize_text.side_effect = side_effect

        # Patch the global engine in src.api
        with patch("src.api.engine", mock_engine):
            # Patch call_gemini to return filled rows
            with patch("src.api.call_gemini") as mock_gemini:
                mock_gemini.return_value = [
                    {
                        "source_sentence": "Hello",
                        "target_sentence": "Γειά"
                    }
                ]

                request_data = {
                    "worksheet_data": [],
                    "instruction_text": "dummy"
                }

                response = client.post("/fill_curriculum", json=request_data)

                self.assertEqual(response.status_code, 200)
                data = response.json()
                rows = data["worksheet_data"]
                self.assertEqual(len(rows), 1)
                row = rows[0]

                # Check tokens were added
                self.assertIn("source_tokens", row)
                self.assertIn("target_tokens", row)

                # Check content of tokens based on our side_effect
                self.assertEqual(row["source_tokens"], [{"text": "Hello", "lang": "en", "is_alpha": True}])
                self.assertEqual(row["target_tokens"], [{"text": "Γειά", "lang": "el", "is_alpha": True}])

                # Verify engine.tokenize_text was called
                self.assertEqual(mock_engine.tokenize_text.call_count, 2)
                mock_engine.tokenize_text.assert_any_call("Hello", "en")
                mock_engine.tokenize_text.assert_any_call("Γειά", "el")

if __name__ == '__main__':
    unittest.main()
