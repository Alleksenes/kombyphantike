import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.kombyphantike import KombyphantikeEngine

class TestTokenizerMetadata(unittest.TestCase):
    @patch('src.kombyphantike.pd.read_csv')
    @patch('src.kombyphantike.spacy.load')
    @patch('src.kombyphantike.KnotLoader')
    @patch('src.kombyphantike.KombyphantikeEngine._load_paradigms')
    def test_metadata_injection(self, mock_load_paradigms, mock_knot_loader, mock_spacy, mock_read_csv):
        # Setup Mock Kelly Data
        data = {
            "Lemma": ["δοκιμή", "άλογο"],
            "Modern_Def": ["test", "horse"],
            "Greek_Def": ["δοκιμασία", "ίππος"],
            "Ancient_Context": ["ancient test", "ancient horse"],
            "Shift_Type": ["Semantic Shift", "Direct Inheritance"],
            "Part of speech": ["Ουσιαστικό", "Ουσιαστικό"],
            "ID": ["1", "2"],
            "Similarity_Score": ["0.5", "0.6"]
        }
        df = pd.DataFrame(data)

        # Configure read_csv to return df when called for KELLY_PATH
        def read_csv_side_effect(path, **kwargs):
            path_str = str(path)
            if "kelly.csv" in path_str:
                return df
            return pd.DataFrame({"Lemma": [], "Gender": []})

        mock_read_csv.side_effect = read_csv_side_effect

        # Mock Paradigms to return empty dict (or minimal if needed)
        mock_load_paradigms.return_value = {}

        # Mock Spacy
        mock_nlp = MagicMock()
        mock_spacy.return_value = mock_nlp

        # Mock Token
        def make_token(text, lemma):
            t = MagicMock()
            t.text = text
            t.lemma_ = lemma
            t.pos_ = "NOUN"
            t.tag_ = "NOUN"
            t.dep_ = "ROOT"
            t.is_alpha = True
            return t

        # Scenario 1: Exact Lemma Match
        token1 = make_token("δοκιμή", "δοκιμή")
        # Scenario 2: Text Lower Match (Lemma mismatch)
        token2 = make_token("Άλογο", "unknown_lemma")

        mock_doc = [token1, token2]
        mock_nlp.return_value = mock_doc

        # Initialize Engine
        engine = KombyphantikeEngine()

        # Run Tokenizer
        tokens = engine.tokenize_text("δοκιμή Άλογο", "el")

        # Assertions
        self.assertEqual(len(tokens), 2)

        # Token 1: Lemma Match
        t1 = tokens[0]
        self.assertEqual(t1['text'], "δοκιμή")
        # These should fail before the fix
        self.assertIn('definition', t1, "Missing definition in token 1")
        self.assertEqual(t1['definition'], "test")
        self.assertEqual(t1['ancient_context'], "ancient test")
        self.assertEqual(t1['semantic_shift'], "Semantic Shift")

        # Token 2: Text Lower Match (Fallback)
        t2 = tokens[1]
        self.assertEqual(t2['text'], "Άλογο")
        # These should fail before the fix
        self.assertIn('definition', t2, "Missing definition in token 2")
        self.assertEqual(t2['definition'], "horse")
        self.assertEqual(t2['ancient_context'], "ancient horse")
        self.assertEqual(t2['semantic_shift'], "Direct Inheritance")

if __name__ == '__main__':
    unittest.main()
