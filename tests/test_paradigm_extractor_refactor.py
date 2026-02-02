import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import pandas as pd
import sys
from pathlib import Path

# Adjust path to find src
sys.path.append(str(Path(__file__).parent.parent))

from src.noun_declension_extractor import ParadigmExtractor

class TestParadigmExtractorRefactor(unittest.TestCase):
    def setUp(self):
        self.mock_targets_df = pd.DataFrame({
            "Lemma": ["lemma1", "lemma2", "lemma3"]
        })

        self.kaikki_data = [
            # Lemma 1: Noun
            {
                "word": "lemma1",
                "pos": "noun",
                "forms": [
                    {"form": "lemma1", "tags": ["nom", "sg"], "raw_tags": ["nom_raw"]},
                    {"form": "lemma1s", "tags": ["gen", "sg"]},
                    {"form": "lemma1-romanized", "tags": ["romanization"]}
                ]
            },
            # Lemma 2: Verb with Junk
            {
                "word": "lemma2",
                "pos": "verb",
                "forms": [
                    {"form": "lemma2", "tags": ["pres", "1sg"]},
                    {"form": "el-conjug-1st-act", "tags": ["junk"]},
                    {"form": "Formed using suffix...", "tags": ["junk"]},
                    {"form": "valid_form", "tags": ["past"]}
                ]
            },
            # Lemma 3: Adjective
            {
                "word": "lemma3",
                "pos": "adj",
                "forms": [
                    {"form": "lemma3", "tags": ["nom", "sg", "masc"]}
                ]
            }
        ]

        self.kaikki_content = "\n".join([json.dumps(entry) for entry in self.kaikki_data])

    @patch('src.noun_declension_extractor.pd.read_csv')
    @patch('src.noun_declension_extractor.pd.read_excel')
    # We patch KAIKKI_EL_FILE at the module level where it is imported/used
    # Wait, it's imported as a constant. So patching src.noun_declension_extractor.KAIKKI_EL_FILE is correct.
    @patch('src.noun_declension_extractor.KAIKKI_EL_FILE', new="mock_kaikki.json")
    @patch('src.noun_declension_extractor.KELLY_CSV')
    @patch('builtins.open')
    def test_extract_all_refactored(self, mock_file_open, mock_kelly_path, mock_read_excel, mock_read_csv):
        # Mock Kelly Loading
        mock_read_csv.return_value = self.mock_targets_df
        # Mock file existence
        mock_kelly_path.exists.return_value = True

        # Mock Kaikki File Reading
        # We need to handle multiple open calls? extract_all opens KAIKKI_EL_FILE.
        # init does not open. load_targets reads csv (mocked).

        # mock_open works best when read directly.
        m = mock_open(read_data=self.kaikki_content)
        mock_file_open.side_effect = [m.return_value] # Only one open call expected for kaikki file

        extractor = ParadigmExtractor()
        paradigms = extractor.extract_all()

        # Verify Lemma 1 (Noun)
        self.assertIn("lemma1", paradigms)
        # Check structure is list
        self.assertIsInstance(paradigms["lemma1"], list, "Output should be a list, not a dict")
        forms1 = paradigms["lemma1"]
        self.assertEqual(len(forms1), 2) # Should exclude romanization
        self.assertEqual(forms1[0]["form"], "lemma1")
        self.assertEqual(forms1[0].get("raw_tags"), ["nom_raw"], "Should capture raw_tags if present")
        self.assertEqual(forms1[1]["form"], "lemma1s")

        # Verify Lemma 2 (Verb with Junk)
        self.assertIn("lemma2", paradigms)
        forms2 = paradigms["lemma2"]
        # Should filter "el-conjug..." and "Formed using..."
        valid_forms = [f["form"] for f in forms2]
        self.assertIn("lemma2", valid_forms)
        self.assertIn("valid_form", valid_forms)
        self.assertNotIn("el-conjug-1st-act", valid_forms)
        self.assertNotIn("Formed using suffix...", valid_forms)

        # Verify Lemma 3 (Adjective)
        self.assertIn("lemma3", paradigms)
        forms3 = paradigms["lemma3"]
        self.assertEqual(forms3[0]["form"], "lemma3")

if __name__ == '__main__':
    unittest.main()
