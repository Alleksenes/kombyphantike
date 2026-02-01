import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os
import json
from pathlib import Path
import pandas as pd

# Mock spacy before importing kombyphantike
sys.modules['spacy'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

import src.kombyphantike
from src.kombyphantike import KombyphantikeEngine

class TestKombyphantikeParadigms(unittest.TestCase):
    def setUp(self):
        self.mock_paradigms = {
            "test_lemma": [
                {"form": "test_lemma", "tags": ["nom"]},
                {"form": "test_lemma_gen", "tags": ["gen"]}
            ]
        }
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
    @patch('src.kombyphantike.open') # Needed for json.load
    def test_tokenize_with_paradigms(self, mock_open_func, mock_read_csv):
        # Mock file handling
        mock_read_csv.return_value = self.mock_df

        # We need to mock PARADIGMS_PATH object
        mock_path = MagicMock()
        mock_path.exists.return_value = True

        # Patch the module-level variable
        with patch('src.kombyphantike.PARADIGMS_PATH', new=mock_path):
            # Also patch json.load to return our data
            with patch('json.load', return_value=self.mock_paradigms):

                mock_nlp = MagicMock()
                mock_token = MagicMock()
                mock_token.text = "test_word"
                mock_token.lemma_ = "test_lemma"
                mock_token.pos_ = "NOUN"
                mock_token.tag_ = "tag"
                mock_token.dep_ = "dep"
                mock_token.is_alpha = True

                # Make nlp object callable (it processes text and returns doc)
                # doc is iterable of tokens
                mock_doc = [mock_token]
                mock_nlp.return_value = mock_doc

                with patch('src.kombyphantike.spacy.load', return_value=mock_nlp):
                    engine = KombyphantikeEngine()
                    # Ensure engine loaded paradigms
                    self.assertEqual(engine.paradigms, self.mock_paradigms)

                    engine.nlp_el = mock_nlp
                    tokens = engine.tokenize_text("test_word", "el")

                    self.assertEqual(len(tokens), 1)
                    t = tokens[0]
                    self.assertEqual(t['lemma'], "test_lemma")
                    self.assertTrue(t['has_paradigm'])
                    self.assertEqual(t['paradigm'], self.mock_paradigms["test_lemma"])

    @patch('src.kombyphantike.pd.read_csv')
    def test_tokenize_without_paradigm(self, mock_read_csv):
        mock_read_csv.return_value = self.mock_df

        # Case where file doesn't exist
        mock_path = MagicMock()
        mock_path.exists.return_value = False

        with patch('src.kombyphantike.PARADIGMS_PATH', new=mock_path):
            mock_nlp = MagicMock()
            mock_token = MagicMock()
            mock_token.lemma_ = "unknown_lemma"
            mock_doc = [mock_token]
            mock_nlp.return_value = mock_doc

            with patch('src.kombyphantike.spacy.load', return_value=mock_nlp):
                engine = KombyphantikeEngine()
                self.assertEqual(engine.paradigms, {})

                engine.nlp_el = mock_nlp
                tokens = engine.tokenize_text("word", "el")

                self.assertFalse(tokens[0]['has_paradigm'])
                self.assertIsNone(tokens[0]['paradigm'])

    @patch('src.kombyphantike.pd.read_csv')
    @patch('src.kombyphantike.open')
    def test_tokenize_irregular_and_fallback(self, mock_open_func, mock_read_csv):
        mock_read_csv.return_value = self.mock_df

        # Mock paradigms with irregular target and a fallback case
        extended_paradigms = {
            "είμαι": [{"form": "είμαι", "tags": ["pres"]}],
            "fallback_word": [{"form": "fallback_word", "tags": ["noun"]}]
        }

        mock_path = MagicMock()
        mock_path.exists.return_value = True

        with patch('src.kombyphantike.PARADIGMS_PATH', new=mock_path):
            with patch('json.load', return_value=extended_paradigms):
                mock_nlp = MagicMock()

                # Token 1: "είναι" -> Should map to "είμαι"
                t1 = MagicMock()
                t1.text = "είναι"
                t1.lemma_ = "wrong_lemma" # Simulate bad spacy lemma
                t1.pos_ = "VERB"
                t1.tag_ = "tag"
                t1.dep_ = "root"
                t1.is_alpha = True

                # Token 2: "fallback_word" -> Lemma missing in paradigms, but text is there
                t2 = MagicMock()
                t2.text = "fallback_word" # Lowercase matches key
                t2.lemma_ = "unknown_lemma"
                t2.pos_ = "NOUN"
                t2.tag_ = "tag"
                t2.dep_ = "obj"
                t2.is_alpha = True

                mock_doc = [t1, t2]
                mock_nlp.return_value = mock_doc

                with patch('src.kombyphantike.spacy.load', return_value=mock_nlp):
                    engine = KombyphantikeEngine()
                    engine.nlp_el = mock_nlp

                    tokens = engine.tokenize_text("είναι fallback_word", "el")

                    self.assertEqual(len(tokens), 2)

                    # Check irregular mapping
                    # "είναι" text -> "είμαι" lemma lookup
                    self.assertTrue(tokens[0]['has_paradigm'])
                    self.assertEqual(tokens[0]['paradigm'], extended_paradigms["είμαι"])

                    # Check fallback
                    # "fallback_word" lemma "unknown_lemma" fails -> fallback to text "fallback_word"
                    self.assertTrue(tokens[1]['has_paradigm'])
                    self.assertEqual(tokens[1]['paradigm'], extended_paradigms["fallback_word"])

if __name__ == '__main__':
    unittest.main()
