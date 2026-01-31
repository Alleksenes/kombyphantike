import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.kombyphantike import KombyphantikeEngine

class TestParadigmLinking(unittest.TestCase):
    def setUp(self):
        self.engine = KombyphantikeEngine()
        # Inject mock paradigms
        self.engine.paradigms = {
            "σπίτι": [{"form": "σπίτι", "tags": ["noun", "sg", "nom"]}],
            "μεγάλος": [{"form": "μεγάλο", "tags": ["adj", "sg", "nom", "neut"]}]
        }

    def test_paradigm_linking_found(self):
        text = "Το σπίτι είναι μεγάλο."
        tokens = self.engine.tokenize_text(text, "el")

        # Check "σπίτι"
        token_found = False
        for t in tokens:
            if t['text'] == "σπίτι":
                token_found = True
                self.assertTrue(t.get('has_paradigm'))
                self.assertIsNotNone(t.get('paradigm'))
                self.assertEqual(t['paradigm'], self.engine.paradigms["σπίτι"])

        self.assertTrue(token_found, "Token 'σπίτι' not found in tokens")

    def test_paradigm_linking_not_found(self):
        text = "Το σπίτι."
        tokens = self.engine.tokenize_text(text, "el")

        # Check "Το" - assuming "Το" lemma is not in our mock paradigms
        token_found = False
        for t in tokens:
            if t['text'] == "Το":
                token_found = True
                self.assertFalse(t.get('has_paradigm'))
                self.assertIsNone(t.get('paradigm'))

        self.assertTrue(token_found, "Token 'Το' not found in tokens")

if __name__ == '__main__':
    unittest.main()
