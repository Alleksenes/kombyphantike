
import unittest
from unittest.mock import MagicMock, patch
import sys
import pandas as pd

# Mock spacy before importing kombyphantike
sys.modules['spacy'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

from src.kombyphantike import KombyphantikeEngine

class TestListParadigms(unittest.TestCase):
    def setUp(self):
        # Mock DataFrame for init
        self.mock_df = pd.DataFrame({
            "Part of speech": ["Noun"],
            "ID": ["1"],
            "Similarity_Score": [0],
            "Shift_Type": ["None"],
            "Modern_Def": ["Def"],
            "Lemma": ["test_lemma"],
            "Gender": ["M"]
        })

    @patch('src.kombyphantike.pd.read_csv')
    @patch('src.kombyphantike.open')
    def test_tokenize_with_list_paradigm(self, mock_open_func, mock_read_csv):
        mock_read_csv.return_value = self.mock_df

        # Paradigm is a LIST (new format)
        mock_paradigms = {
            "είμαι": [
                {"form": "είμαι", "tags": ["pres"]},
                {"form": "είναι", "tags": ["pres", "3sg"]}
            ]
        }

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        with patch('src.kombyphantike.PARADIGMS_PATH', new=mock_path):
            with patch('json.load', return_value=mock_paradigms):
                mock_nlp = MagicMock()

                # Test Auxiliary Check with List
                t1 = MagicMock()
                t1.text = "είναι"
                t1.lemma_ = "είναι"
                t1.pos_ = "VERB"
                t1.is_alpha = True

                mock_nlp.return_value = [t1]

                with patch('src.kombyphantike.spacy.load', return_value=mock_nlp):
                    engine = KombyphantikeEngine()
                    engine.nlp_el = mock_nlp

                    tokens = engine.tokenize_text("είναι", "el")

                    self.assertTrue(tokens[0]['has_paradigm'])
                    self.assertIsInstance(tokens[0]['paradigm'], list)
                    self.assertEqual(tokens[0]['paradigm'], mock_paradigms["είμαι"])

    @patch('src.kombyphantike.pd.read_csv')
    @patch('src.kombyphantike.open')
    def test_plural_check_with_list(self, mock_open_func, mock_read_csv):
        mock_read_csv.return_value = self.mock_df

        mock_paradigms = {
            "test_plural": [
                {"form": "test_plural", "tags": ["plural"]}
            ]
        }

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        with patch('src.kombyphantike.PARADIGMS_PATH', new=mock_path):
            with patch('json.load', return_value=mock_paradigms):
                with patch('src.kombyphantike.spacy.load', return_value=MagicMock()):
                    engine = KombyphantikeEngine()

                    # Should NOT crash and return True
                    is_plural = engine._check_paradigm_for_plural("test_plural")
                    self.assertTrue(is_plural)

    @patch('src.kombyphantike.pd.read_csv')
    @patch('src.kombyphantike.open')
    def test_context_with_list(self, mock_open_func, mock_read_csv):
        mock_read_csv.return_value = self.mock_df

        mock_paradigms = {
            "hero": [
                {"form": "hero_form"}
            ]
        }

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        with patch('src.kombyphantike.PARADIGMS_PATH', new=mock_path):
            with patch('json.load', return_value=mock_paradigms):
                with patch('src.kombyphantike.spacy.load', return_value=MagicMock()):
                    engine = KombyphantikeEngine()

                    row = {"Modern_Examples": "This is a hero_form sentence."}
                    corpus = []

                    # Should NOT crash
                    ctx = engine._get_modern_context("hero", row, corpus)
                    self.assertIn("hero_form", ctx)

if __name__ == '__main__':
    unittest.main()
