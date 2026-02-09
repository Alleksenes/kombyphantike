import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock heavy dependencies
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["transliterate"] = MagicMock()
# sys.modules["src.database"] = MagicMock() # We want to patch it inside the test

from src.kombyphantike import KombyphantikeEngine
from src.models import ConstellationGraph, ConstellationNode

class TestComplexityLogic(unittest.TestCase):

    def setUp(self):
        # Mock dependencies for Engine initialization
        self.mock_db_cls = patch("src.kombyphantike.DatabaseManager").start()
        self.mock_db = self.mock_db_cls.return_value

        self.mock_knot_loader_cls = patch("src.kombyphantike.KnotLoader").start()
        self.mock_knot_loader = self.mock_knot_loader_cls.return_value
        self.mock_knot_loader.knots = pd.DataFrame() # Empty knots
        self.mock_knot_loader.construct_regex.return_value = ".*"

        # Mock pd.read_csv to avoid file I/O
        self.mock_read_csv = patch("src.kombyphantike.pd.read_csv").start()

        def read_csv_side_effect(*args, **kwargs):
            path = str(args[0]) if args else ""
            if "noun_declensions.csv" in path:
                return pd.DataFrame({"Lemma": [], "Gender": []})
            # Kelly default
            return pd.DataFrame({
                "Part of speech": ["Noun"],
                "Lemma": ["test_lemma"],
                "ID": [1],
                "Similarity_Score": [0.5],
                "Modern_Examples": ["Ex1"],
                "Greek_Def": ["Def1"],
                "Modern_Def": ["Def2"],
                "Shift_Type": ["Direct Inheritance"]
            })
        self.mock_read_csv.side_effect = read_csv_side_effect

        # Mock file existence
        patch("pathlib.Path.exists", return_value=True).start()
        mock_open = patch("builtins.open", new_callable=MagicMock).start()
        # Ensure read returns valid JSON string
        mock_open.return_value.__enter__.return_value.read.return_value = "{}"

        self.engine = KombyphantikeEngine()
        # Fix pos_col
        self.engine.pos_col = "Part of speech"

    def tearDown(self):
        patch.stopall()

    def test_select_words_complexity_lucid(self):
        # Setup db.select_words to return something
        self.mock_db.select_words.return_value = []

        # We need to monkey-patch select_words if we want to test it in isolation,
        # but here we test the engine's method directly.

        # Test Lucid: Expect max_kds=30 if target_level="Any"
        self.engine.select_words("theme", 10, target_level="Any", complexity="lucid")

        # Verify db.select_words called with range 0-30
        self.mock_db.select_words.assert_called_with("theme", 0, 30, limit=40)

    def test_select_words_complexity_complex(self):
        self.mock_db.select_words.return_value = []

        # Test Complex: Expect min_kds=50 if target_level="Any"
        self.engine.select_words("theme", 10, target_level="Any", complexity="complex")

        # Verify db.select_words called with range 50-100
        self.mock_db.select_words.assert_called_with("theme", 50, 100, limit=40)

    def test_expand_word_pool_complexity_lucid(self):
        # Lucid limit = 2
        words_df = pd.DataFrame({"Lemma": ["root"], "Part of speech": ["Noun"]})

        # Mock get_relations to return many
        self.mock_db.get_relations.return_value = {
            "synonyms": ["s1", "s2", "s3", "s4", "s5"]
        }
        self.mock_db.get_metadata.return_value = {"pos": "noun", "definition": "def", "etymology_text": "etym"}

        result_df = self.engine._expand_word_pool(words_df, complexity="lucid")

        # We expect 2 new rows added
        self.assertEqual(len(result_df), 3) # 1 original + 2 new

    def test_expand_word_pool_complexity_complex_etymology(self):
        # Complex limit = 6 (or 5+), and Etymology
        words_df = pd.DataFrame({"Lemma": ["root"], "Part of speech": ["Noun"]})

        self.mock_db.get_relations.return_value = {
            "synonyms": ["s1", "s2", "s3", "s4", "s5", "s6"]
        }
        # Mock metadata to include etymology
        self.mock_db.get_metadata.return_value = {
            "pos": "noun",
            "definition": "def",
            "etymology_text": "Ancient Origin"
        }

        result_df = self.engine._expand_word_pool(words_df, complexity="complex")

        # We expect 6 new rows (limit is 6)
        # Note: The plan said "Limit to 6".
        self.assertEqual(len(result_df), 7) # 1 original + 6 new

        # Check Etymology column exists and is populated
        self.assertIn("Etymology", result_df.columns)
        self.assertEqual(result_df.iloc[1]["Etymology"], "Ancient Origin")

    def test_generate_ai_instruction_includes_etymology(self):
        words_df = pd.DataFrame({
            "Lemma": ["alpha", "beta", "gamma"],
            "Part of speech": ["Noun", "Noun", "Noun"],
            "Etymology": ["From A", "From B", ""]
        })

        text = self.engine.generate_ai_instruction("theme", 10, words_df, complexity="complex")

        self.assertIn("alpha (Etym: From A)", text)
        self.assertIn("beta (Etym: From B)", text)
        self.assertIn("gamma", text)
        self.assertNotIn("gamma (Etym: )", text)
        self.assertNotIn("gamma (Etym:)", text)

    def test_generate_ai_instruction_includes_complexity_guidance(self):
        empty_df = pd.DataFrame(columns=["Part of speech", "Lemma"])

        # Lucid
        text = self.engine.generate_ai_instruction("theme", 10, empty_df, complexity="lucid")
        self.assertIn("Write clear, simple sentences", text)

        # Complex
        text = self.engine.generate_ai_instruction("theme", 10, empty_df, complexity="complex")
        self.assertIn("Write sophisticated, philologically rich sentences", text)

    def test_compile_curriculum_passes_complexity(self):
        # Mock internal methods to verify calls
        # Since we are testing integration, we can't mock methods on self.engine easily without replacing them
        # but we can rely on side effects or use `with patch.object`.

        with patch.object(self.engine, 'select_words', return_value=pd.DataFrame({"Lemma": ["a"], "Part of speech": ["Noun"]})) as mock_select, \
             patch.object(self.engine, '_expand_word_pool', return_value=pd.DataFrame({"Lemma": ["a"], "Part of speech": ["Noun"]})) as mock_expand:

             self.engine.select_strategic_knots = MagicMock(return_value=[])

             self.engine.compile_curriculum("theme", 10, complexity="complex")

             mock_select.assert_called_with("theme", 15, "Any", "complex")
             mock_expand.assert_called_with(mock_select.return_value, "complex")

if __name__ == '__main__':
    unittest.main()
