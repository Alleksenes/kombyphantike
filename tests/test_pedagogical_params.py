import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock heavy dependencies
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["transliterate"] = MagicMock()
sys.modules["src.database"] = MagicMock()
sys.modules["elevenlabs"] = MagicMock()
sys.modules["elevenlabs.client"] = MagicMock()

# Mock google
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()

# Mock src.kombyphantike dependencies before importing it
# sys.modules["src.config"] = MagicMock() # Use real config
sys.modules["src.knot_loader"] = MagicMock()
# DO NOT MOCK src.models so FastAPI works

from src.api import app
from fastapi.testclient import TestClient
from src.kombyphantike import KombyphantikeEngine

class TestPedagogicalParams(unittest.TestCase):

    def setUp(self):
        # Create a mock engine instance
        self.mock_engine = MagicMock()
        # Ensure it returns a dummy graph structure expected by response_model
        # ConstellationGraph expects 'nodes' and 'links'
        self.mock_engine.compile_curriculum.return_value = {
            "nodes": [],
            "links": []
        }

    def test_draft_curriculum_passes_params(self):
        client = TestClient(app)

        # Patch the engine in src.api
        with patch("src.api.engine", self.mock_engine):
            payload = {
                "theme": "Philosophy",
                "sentence_count": 5,
                "target_level": "C2",
                "complexity": "complex"
            }
            response = client.post("/draft_curriculum", json=payload)

            # Check response
            self.assertEqual(response.status_code, 200, response.text)

            # Check call arguments
            self.mock_engine.compile_curriculum.assert_called_once()
            call_args = self.mock_engine.compile_curriculum.call_args
            # Args: theme, count
            self.assertEqual(call_args[0][0], "Philosophy")
            self.assertEqual(call_args[0][1], 5)
            # Kwargs: target_level, complexity
            self.assertEqual(call_args[1]["target_level"], "C2")
            self.assertEqual(call_args[1]["complexity"], "complex")

    def test_engine_generate_instruction_includes_params(self):
        # Mock dependencies for Engine initialization
        mock_db = MagicMock()
        mock_db.get_metadata.return_value = {}
        mock_db.get_relations.return_value = {}
        mock_db.get_paradigm.return_value = []

        mock_knot_loader = MagicMock()
        mock_knot_loader.knots = pd.DataFrame()
        mock_knot_loader.construct_regex.return_value = ".*"

        # We use real src.models now

        def read_csv_side_effect(*args, **kwargs):
            path = str(args[0]) if args else ""
            if "noun_declensions.csv" in path:
                return pd.DataFrame({"Lemma": [], "Gender": []})
            # Kelly default
            return pd.DataFrame({
                "Part of speech": [],
                "Lemma": [],
                "ID": [],
                "Similarity_Score": [],
                "Modern_Examples": []
            })

        with patch("src.kombyphantike.DatabaseManager", return_value=mock_db), \
             patch("src.kombyphantike.KnotLoader", return_value=mock_knot_loader), \
             patch("src.kombyphantike.pd.read_csv", side_effect=read_csv_side_effect), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", new_callable=MagicMock) as mock_open:

            mock_open.return_value.__enter__.return_value.read.return_value = "{}"

            engine = KombyphantikeEngine()
            # Fix pos_col
            engine.pos_col = "Part of speech"

            # Mock select_words to return empty DF so we don't crash on processing
            engine.select_words = MagicMock(return_value=pd.DataFrame({"Part of speech": [], "Lemma": []}))
            engine._expand_word_pool = MagicMock(return_value=pd.DataFrame({"Part of speech": [], "Lemma": []}))
            engine.select_strategic_knots = MagicMock(return_value=[])

            # Call compile_curriculum
            graph = engine.compile_curriculum("test", 1, target_level="B1", complexity="simple")

            # Extract instruction text from center node
            center_node = next(n for n in graph.nodes if n.type == "theme")
            text = center_node.data["instruction_text"]

            # Verify params in text
            self.assertIn("**TARGET LEVEL:** B1", text)
            self.assertIn("**COMPLEXITY:** simple", text)

if __name__ == '__main__':
    unittest.main()
