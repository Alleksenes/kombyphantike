import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock spacy before importing kombyphantike
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()

from src.kombyphantike import KombyphantikeEngine

class TestTokenizer(unittest.TestCase):
    def setUp(self):
        # Setup Spacy Mock
        self.mock_nlp = MagicMock()

        # When nlp("text") is called, return a doc
        def nlp_side_effect(text):
            doc = MagicMock()
            doc.__iter__.return_value = self._create_tokens(text)
            return doc

        self.mock_nlp.side_effect = nlp_side_effect

        # Patch spacy.load to return our mock
        sys.modules["spacy"].load.return_value = self.mock_nlp

        # Initialize engine
        # It will try to load spacy, which we mocked
        self.engine = KombyphantikeEngine()

        # Manually set nlp_el and nlp_en just in case
        self.engine.nlp_el = self.mock_nlp
        self.engine.nlp_en = self.mock_nlp

    def _create_tokens(self, text):
        # Simple whitespace tokenizer for mocking
        raw_tokens = text.split()
        if text.endswith("."):
             # Handle simple period at end
             if len(raw_tokens) > 0 and raw_tokens[-1].endswith("."):
                 last = raw_tokens[-1]
                 raw_tokens[-1] = last[:-1]
                 if raw_tokens[-1] == "":
                     raw_tokens.pop()
                 raw_tokens.append(".")

        mock_tokens = []
        for t in raw_tokens:
            token = MagicMock()
            token.text = t
            token.lemma_ = t.lower()
            token.pos_ = "NOUN" # Dummy
            token.tag_ = "NN"
            token.dep_ = "ROOT"
            token.is_alpha = t.isalpha()
            token.morph = "Case=Nom|Gender=Neut"
            mock_tokens.append(token)
        return mock_tokens

    def test_tokenize_greek(self):
        text = "Το σπίτι είναι μεγάλο."
        # The engine uses translit, which we didn't mock.
        # But we need to make sure 'transliterate' is installed.
        # Ideally we should mock 'transliterate.translit' if we don't want to depend on it.
        # But let's assume it works or mock it if needed.

        tokens = self.engine.tokenize_text(text, "el")

        self.assertTrue(len(tokens) > 0)
        # Check first token "Το"
        t0 = tokens[0]
        self.assertEqual(t0['text'], "Το")
        self.assertIn('lemma', t0)
        self.assertIn('pos', t0)
        self.assertIn('tag', t0)
        self.assertIn('dep', t0)
        self.assertIn('is_alpha', t0)
        self.assertIn('morphology', t0)
        self.assertIn('transliteration', t0)

        # Since we mocked morph to return a string "Case=Nom...", verify it
        self.assertEqual(t0['morphology'], "Case=Nom|Gender=Neut")

        # Check punctuation "."
        t_last = tokens[-1]
        self.assertEqual(t_last['text'], ".")
        self.assertFalse(t_last['is_alpha'])

    def test_tokenize_english(self):
        text = "The house is big."
        tokens = self.engine.tokenize_text(text, "en")

        self.assertTrue(len(tokens) > 0)
        t0 = tokens[0]
        self.assertEqual(t0['text'], "The")
        self.assertTrue(t0['is_alpha'])

        t_last = tokens[-1]
        self.assertEqual(t_last['text'], ".")
        self.assertFalse(t_last['is_alpha'])

if __name__ == '__main__':
    unittest.main()
