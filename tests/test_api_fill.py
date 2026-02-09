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

class TestApiFill(unittest.TestCase):
    def test_fill_curriculum_tokenization(self):
        client = TestClient(app)

        # Mock engine instance
        mock_engine_instance = MagicMock()

        # Setup tokenize_text to return something specific
        def side_effect(text, lang):
            return [{"text": text, "lang": lang, "is_alpha": True}]
        mock_engine_instance.tokenize_text.side_effect = side_effect
        mock_engine_instance.transliterate_sentence.return_value = "transliterated"

        # Patch the global engine in src.api
        with patch("src.api.engine", mock_engine_instance):
            # Patch call_gemini to return filled rows
            with patch("src.api.call_gemini") as mock_gemini:
                mock_gemini.return_value = [
                    {
                        "id": "rule_1",
                        "source_sentence": "Hello",
                        "target_sentence": "Γειά",
                        "knot_context": "Context"
                    }
                ]

                # Create request with proper node structure
                request_data = {
                    "worksheet_data": [
                        {
                            "id": "rule_1",
                            "type": "rule",
                            "label": "Rule 1",
                            "data": {
                                "knot_definition": "Def"
                            }
                        }
                    ],
                    "instruction_text": "dummy"
                }

                response = client.post("/fill_curriculum", json=request_data)

                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()
                rows = data["worksheet_data"]
                self.assertEqual(len(rows), 1)

                # Retrieve the node
                node = rows[0]
                self.assertEqual(node["id"], "rule_1")

                # Check data dictionary
                node_data = node.get("data", {})

                # Check tokens were added to data
                self.assertIn("source_tokens", node_data)
                self.assertIn("target_tokens", node_data)

                # Check content of tokens based on our side_effect
                self.assertEqual(node_data["source_tokens"], [{"text": "Hello", "lang": "en", "is_alpha": True}])
                self.assertEqual(node_data["target_tokens"], [{"text": "Γειά", "lang": "el", "is_alpha": True}])

                # Verify engine.tokenize_text was called
                # Note: tokenize_text might be called more times if we had more fields, but here just source and target
                self.assertEqual(mock_engine_instance.tokenize_text.call_count, 2)
                mock_engine_instance.tokenize_text.assert_any_call("Hello", "en")
                mock_engine_instance.tokenize_text.assert_any_call("Γειά", "el")

if __name__ == '__main__':
    unittest.main()
