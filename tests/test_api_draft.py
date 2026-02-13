import sys
import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# 1. Mock heavy dependencies BEFORE imports
sys.modules["transliterate"] = MagicMock()
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["src.database"] = MagicMock()
sys.modules["src.audio"] = MagicMock()

# Mock src.kombyphantike module and engine class
mock_komby_module = MagicMock()
sys.modules["src.kombyphantike"] = mock_komby_module
mock_engine_class = MagicMock()
mock_komby_module.KombyphantikeEngine = mock_engine_class

# 2. Import API and Models
from src.api import app
import src.api
from src.models import ConstellationGraph, ConstellationNode, ConstellationLink, NodeData

class TestDraftCurriculum(unittest.TestCase):
    def setUp(self):
        # We need to access the mock engine instance that will be created
        self.mock_engine_instance = mock_engine_class.return_value

    def test_draft_curriculum_binding(self):
        """Verify that draft_curriculum returns a valid ConstellationGraph."""

        # Setup the mock return value
        node_data = NodeData(
            knot_id="test_knot",
            hero="test_hero",
            instruction_text="Test instruction"
        )
        node = ConstellationNode(
            id="node1",
            label="Test Node",
            type="theme",
            status="active",
            data=node_data
        )
        graph = ConstellationGraph(
            nodes=[node],
            links=[],
            golden_path=["node1"]
        )

        # Configure the mock to return this graph
        self.mock_engine_instance.compile_curriculum.return_value = graph

        # Use context manager to ensure startup events run (which initializes engine)
        with TestClient(app) as client:
            # Make the request
            payload = {
                "theme": "Love",
                "sentence_count": 5,
                "target_level": "A1",
                "complexity": "lucid"
            }

            response = client.post("/draft_curriculum", json=payload)

            # Assertions
            self.assertEqual(response.status_code, 200, f"Response: {response.text}")

            data = response.json()

            # Verify structure matches ConstellationGraph
            self.assertIn("nodes", data)
            self.assertIn("links", data)
            self.assertIn("golden_path", data)
            self.assertEqual(data["nodes"][0]["id"], "node1")
            self.assertEqual(data["golden_path"], ["node1"])

if __name__ == "__main__":
    unittest.main()
