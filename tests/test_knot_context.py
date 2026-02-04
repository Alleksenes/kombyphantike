import sys
import os
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock spacy and sentence_transformers
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()

from src.kombyphantike import KombyphantikeEngine

class TestKnotContext(unittest.TestCase):
    def setUp(self):
        # Setup Spacy Mock
        self.mock_nlp = MagicMock()

        # Simple doc mock for similarity
        def nlp_side_effect(text):
            doc = MagicMock()
            doc.similarity.return_value = 0.5
            doc.__iter__.return_value = []
            return doc
        self.mock_nlp.side_effect = nlp_side_effect
        sys.modules["spacy"].load.return_value = self.mock_nlp

        # Mock KnotLoader
        self.mock_knot_loader_patcher = patch('src.kombyphantike.KnotLoader')
        self.mock_knot_loader_cls = self.mock_knot_loader_patcher.start()
        self.mock_knot_loader = self.mock_knot_loader_cls.return_value

        # Setup dummy knots
        # Knot structure: Knot_ID, POS_Tag, Regex_Ending, Morpho_Constraint, Parent_Concept, Nuance, Description
        knots_data = {
            "Knot_ID": ["1", "2"],
            "POS_Tag": ["Noun", "Verb"],
            "Regex_Ending": [None, None],
            "Morpho_Constraint": [None, None],
            "Parent_Concept": ["Case", "Tense"],
            "Nuance": ["Use Genitive", "Use Past"],
            "Description": ["Genitive Case", "Past Tense"],
            "Example_Word": ["", ""]
        }
        self.mock_knot_loader.knots = pd.DataFrame(knots_data)

        # Helper for regex construction
        def construct_regex(ending):
            return ".*"
        self.mock_knot_loader.construct_regex.side_effect = construct_regex

        # Initialize engine
        self.engine = KombyphantikeEngine()
        self.engine.nlp = self.mock_nlp # Ensure nlp is set for similarity fallback

        # Mock kelly data if it's empty (though we saw it on disk, it might be safer to ensure it has rows)
        if self.engine.kelly.empty:
            self.engine.kelly = pd.DataFrame({
                "Lemma": ["word1", "word2"],
                "Modern_Def": ["def1", "def2"],
                "Greek_Def": ["def1", "def2"],
                "Part of speech": ["Ουσιαστικό", "Ρήμα"],
                "ID": [1, 2],
                "Similarity_Score": [0.5, 0.5],
                "Shift_Type": ["Direct Inheritance", "Direct Inheritance"],
                "Modern_Examples": ["ex1", "ex2"]
            })
            # Re-detect pos col
            self.engine.pos_col = "Part of speech"
            self.engine.kelly["Freq_Score"] = 0.5
            self.engine.kelly["Heritage_Score"] = 1.0
            self.engine.kelly["Semantic_Score"] = 0.5
            self.engine.kelly["Final_Score"] = 1.0

    def tearDown(self):
        self.mock_knot_loader_patcher.stop()

    def test_knot_context_presence(self):
        # Run compile_curriculum
        theme = "Life"
        target_sentences = 4

        result = self.engine.compile_curriculum(theme, target_sentences)

        worksheet_data = result["worksheet_data"]
        self.assertTrue(len(worksheet_data) > 0)

        for row in worksheet_data:
            # Check if knot_context key exists
            self.assertIn("knot_context", row)

            # It should be empty initially, as the LLM fills it
            # But the presence of the key is what we need to verify for the frontend
            self.assertEqual(row["knot_context"], "")

            # Also verify other required fields
            self.assertIn("target_sentence", row)
            self.assertIn("source_sentence", row)
            self.assertIn("knot_id", row)

if __name__ == '__main__':
    unittest.main()
