import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api import app

class TestApiFillPreservation(unittest.TestCase):
    def test_fill_curriculum_preserves_static_fields(self):
        client = TestClient(app)

        # Mock engine
        mock_engine = MagicMock()
        # Setup tokenize_text to return something dummy
        mock_engine.tokenize_text.return_value = []
        mock_engine.transliterate_sentence.return_value = ""

        # Patch the global engine in src.api
        with patch("src.api.engine", mock_engine):
            # Patch call_gemini to return filled rows but MISSING the static field
            with patch("src.api.call_gemini") as mock_gemini:
                # The AI returns ONLY what it thinks is relevant or updated
                mock_gemini.return_value = [
                    {
                        "source_sentence": "Hello",
                        "target_sentence": "Γειά",
                        "knot_context": "Explanation"
                    }
                ]

                # The request contains the static field 'knot_definition'
                request_data = {
                    "worksheet_data": [
                        {
                            "source_sentence": "",
                            "target_sentence": "",
                            "knot_definition": "Static Definition Here",
                            "knot_id": "K1"
                        }
                    ],
                    "instruction_text": "dummy"
                }

                response = client.post("/fill_curriculum", json=request_data)

                self.assertEqual(response.status_code, 200)
                data = response.json()
                rows = data["worksheet_data"]
                self.assertEqual(len(rows), 1)
                row = rows[0]

                # Verify static field preservation
                # This assertion will fail until src/api.py is fixed to merge data
                self.assertIn("knot_definition", row, "knot_definition should be preserved")
                self.assertEqual(row["knot_definition"], "Static Definition Here")

                # Verify AI fields are present
                self.assertEqual(row["knot_context"], "Explanation")

if __name__ == '__main__':
    unittest.main()
