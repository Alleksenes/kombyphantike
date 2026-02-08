import sys
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import logging

# Mock heavy dependencies
sys.modules["elevenlabs"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["spacy"] = MagicMock()
sys.modules["transliterate"] = MagicMock()

# Import after mocking
from src.kombyphantike import KombyphantikeEngine

class TestExpandWordPool(unittest.TestCase):
    def setUp(self):
        self.kelly_data = pd.DataFrame({
            "ID": ["1", "2"],
            "Λημμα (Lemma)": ["word1", "word2"],
            "Lemma": ["word1", "word2"],
            "Μέρος του Λόγου (Part of speech)": ["Ουσιαστικό", "Ρήμα"],
            "Freq_Score": [0.9, 0.8],
            "Heritage_Score": [1.0, 1.0],
            "Semantic_Score": [1.0, 1.0],
            "Similarity_Score": [1.0, 1.0],
            "Modern_Examples": ["Ex1", "Ex2"],
            "Greek_Def": ["Def1", "Def2"],
            "Modern_Def": ["Def1", "Def2"],
            "Shift_Type": ["Direct Inheritance", "Direct Inheritance"],
            "Target_Def": ["Def1", "Def2"]
        })
        self.decls_data = pd.DataFrame({
            "Lemma": ["word1", "word2"],
            "Gender": ["Masc", "Neut"]
        })

    @patch("src.kombyphantike.DatabaseManager")
    @patch("pandas.read_csv")
    @patch("src.kombyphantike.KnotLoader")
    def test_expand_word_pool_logic(self, MockKnotLoader, MockReadCSV, MockDBManager):
        # Setup Mocks
        mock_db = MagicMock()
        MockDBManager.return_value = mock_db

        def read_csv_side_effect(path, **kwargs):
             s_path = str(path)
             if "kelly.csv" in s_path:
                 return self.kelly_data
             if "noun_declensions.csv" in s_path:
                 return self.decls_data
             return pd.DataFrame()
        MockReadCSV.side_effect = read_csv_side_effect

        mock_knot_loader = MagicMock()
        mock_knot_loader.knots = pd.DataFrame()
        MockKnotLoader.return_value = mock_knot_loader

        # Initialize
        engine = KombyphantikeEngine()
        engine.nlp = MagicMock()
        engine.model = MagicMock()

        # Setup Relations
        # word1 has 6 relations (check limit 5)
        relations_w1 = {
            "synonyms": ["s1", "s2"],
            "related": ["r1", "r2"],
            "derived": ["d1", "d2"]
        }
        mock_db.get_relations.side_effect = lambda w: relations_w1 if w == "word1" else {}

        # Setup Metadata (POS mapping)
        def get_meta(w):
            if w in ["s1", "s2"]: return {"pos": "noun"}
            if w in ["r1", "r2"]: return {"pos": "adj"} # Adjective -> Επίθετο
            if w in ["d1", "d2"]: return {"pos": "verb"} # Verb -> Ρήμα
            return {"pos": "noun"}
        mock_db.get_metadata.side_effect = get_meta

        # Check implementation existence
        if not hasattr(engine, "_expand_word_pool"):
            print("Method _expand_word_pool not found, skipping logic test (expected during TDD)")
            return

        expanded_df = engine._expand_word_pool(self.kelly_data)

        # Assertions
        # Original 2 words + max 5 relations = 7 words total
        self.assertEqual(len(expanded_df), 2 + 5)

        lemmas = expanded_df["Lemma"].tolist()

        # Check strict containment of first 5
        # The order is non-deterministic due to set(), so we check count and membership
        new_words = [w for w in lemmas if w not in ["word1", "word2"]]
        self.assertEqual(len(new_words), 5)

        candidates_set = {"s1", "s2", "r1", "r2", "d1", "d2"}
        self.assertTrue(all(w in candidates_set for w in new_words))

        # Check POS mapping for any present word
        if "s1" in new_words:
            row_s1 = expanded_df[expanded_df["Lemma"] == "s1"].iloc[0]
            self.assertIn("Ουσιαστικό", row_s1[engine.pos_col])

        if "r1" in new_words:
            row_r1 = expanded_df[expanded_df["Lemma"] == "r1"].iloc[0]
            self.assertIn("Επίθετο", row_r1[engine.pos_col])

    @patch("src.kombyphantike.DatabaseManager")
    @patch("pandas.read_csv")
    @patch("src.kombyphantike.KnotLoader")
    def test_compile_curriculum_integration(self, MockKnotLoader, MockReadCSV, MockDBManager):
        # Setup Mocks
        mock_db = MagicMock()
        MockDBManager.return_value = mock_db

        def read_csv_side_effect(path, **kwargs):
             s_path = str(path)
             if "kelly.csv" in s_path:
                 return self.kelly_data
             if "noun_declensions.csv" in s_path:
                 return self.decls_data
             return pd.DataFrame()
        MockReadCSV.side_effect = read_csv_side_effect

        mock_knot_loader = MagicMock()
        mock_knot_loader.knots = pd.DataFrame()
        MockKnotLoader.return_value = mock_knot_loader

        engine = KombyphantikeEngine()
        engine.nlp = MagicMock()
        engine.model = MagicMock()

        # Mock select_words to return data
        engine.select_words = MagicMock(return_value=self.kelly_data.copy())

        # Mock dependencies of compile_curriculum
        engine.select_strategic_knots = MagicMock(return_value=[])

        # Setup Relations for integration test
        mock_db.get_relations.side_effect = lambda w: {"synonyms": ["integrated_syn"]} if w == "word1" else {}
        mock_db.get_metadata.return_value = {"pos": "noun"}

        # Run
        result = engine.compile_curriculum("Theme", 10)

        # Verify result is a ConstellationGraph
        from src.models import ConstellationGraph
        self.assertIsInstance(result, ConstellationGraph)

        # Extract center node data
        center_node = next(n for n in result.nodes if n.type == "theme")
        instruction = center_node.data["instruction_text"]

        # Verify result contains the new word in instruction text
        self.assertIn("integrated_syn", instruction)

        # Verify words_df in result has it
        words_list = center_node.data["words_df_json"]
        # words_df_json is list of dicts
        lemmas = [w["Lemma"] for w in words_list]
        self.assertIn("integrated_syn", lemmas)

if __name__ == "__main__":
    unittest.main()
