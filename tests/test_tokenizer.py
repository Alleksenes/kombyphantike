import sys
import os
import unittest
import spacy

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.kombyphantike import KombyphantikeEngine

class TestTokenizer(unittest.TestCase):
    def setUp(self):
        # Initialize engine
        # We assume data files are present as per exploration
        self.engine = KombyphantikeEngine()

    def test_tokenize_greek(self):
        text = "Το σπίτι είναι μεγάλο."
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
        self.assertTrue(t0['is_alpha']) # "Το" is alpha

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
