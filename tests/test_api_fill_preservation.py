import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock heavy dependencies BEFORE importing src.api
sys.modules["transliterate"] = MagicMock()
sys.modules["pandas"] = MagicMock()
sys.modules["spacy"] = MagicMock()
sys.modules["elevenlabs"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["src.kombyphantike"] = MagicMock()
sys.modules["src.audio"] = MagicMock()

# Now import app
from src.api import app
from fastapi.testclient import TestClient

class TestApiFillPreservation(unittest.TestCase):
    def test_fill_curriculum_preserves_static_fields(self):
        client = TestClient(app)

        # Mock engine instance
        mock_engine_instance = MagicMock()
        mock_engine_instance.tokenize_text.return_value = []
        mock_engine_instance.transliterate_sentence.return_value = ""

        # Patch the global engine in src.api
        with patch("src.api.engine", mock_engine_instance):
            # Patch call_gemini to return filled rows but MISSING the static field
            with patch("src.api.call_gemini") as mock_gemini:
                # The AI returns ONLY what it thinks is relevant or updated
                mock_gemini.return_value = [
                    {
                        "id": "rule_1",
                        "source_sentence": "Hello",
                        "target_sentence": "Γειά",
                        "knot_context": "Explanation"
                    }
                ]

                # The request contains the static field 'knot_definition' in 'data'
                request_data = {
                    "worksheet_data": [
                        {
                            "id": "rule_1",
                            "type": "rule",
                            "label": "Rule",
                            "data": {
                                "source_sentence": "",
                                "target_sentence": "",
                                "knot_definition": "Static Definition Here",
                                "knot_id": "K1"
                            }
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

                # Verify static field preservation in 'data'
                self.assertIn("data", row)
                row_data = row["data"]

                self.assertIn("knot_definition", row_data, "knot_definition should be preserved")
                self.assertEqual(row_data["knot_definition"], "Static Definition Here")

                # Verify AI fields are present in 'data'
                self.assertEqual(row_data["knot_context"], "Explanation")

if __name__ == '__main__':
    unittest.main()
