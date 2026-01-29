import sys
import os
import json
import unittest
from unittest.mock import MagicMock
from pathlib import Path
import pandas as pd
import shutil

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Mock sentence_transformers BEFORE importing src.kombyphantike
sys.modules["sentence_transformers"] = MagicMock()

from src.kombyphantike import KombyphantikeEngine
from src.config import PROCESSED_DIR, DATA_DIR

PARADIGMS_PATH = PROCESSED_DIR / "paradigms.json"
DICT_DIR = DATA_DIR / "dictionaries"
KNOTS_PATH = DICT_DIR / "knots.csv"

class TestTokenization(unittest.TestCase):
    def setUp(self):
        # Create dummy paradigms.json
        self.dummy_paradigms = {
            "τρέχω": [{"form": "τρέχω", "tags": ["present", "active"]}],
            "άνθρωπος": [{"form": "άνθρωπος", "tags": ["noun", "masculine"]}]
        }
        # Backup existing if any
        self.backup_paradigms = None
        if PARADIGMS_PATH.exists():
            with open(PARADIGMS_PATH, "r", encoding="utf-8") as f:
                self.backup_paradigms = f.read()

        with open(PARADIGMS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.dummy_paradigms, f, ensure_ascii=False)

        # Create dummy knots.csv
        self.created_knots = False
        self.backup_knots = None
        if not DICT_DIR.exists():
            DICT_DIR.mkdir(parents=True)

        if KNOTS_PATH.exists():
            self.backup_knots = pd.read_csv(KNOTS_PATH, dtype=str)

        dummy_knots = pd.DataFrame([
            {
                "Knot_ID": "K1",
                "POS_Tag": "Noun",
                "Regex_Ending": "ος",
                "Parent_Concept": "Case",
                "Nuance": "",
                "Description": "Nominative Singular",
                "Morpho_Constraint": ""
            },
            {
                "Knot_ID": "K2",
                "POS_Tag": "Syntax",
                "Regex_Ending": "",
                "Parent_Concept": "Syntax",
                "Nuance": "",
                "Description": "Simple Sentence",
                "Morpho_Constraint": ""
            }
        ])
        dummy_knots.to_csv(KNOTS_PATH, index=False)
        self.created_knots = True

        # Initialize engine
        self.engine = KombyphantikeEngine()

    def tearDown(self):
        # Restore paradigms
        if self.backup_paradigms:
            with open(PARADIGMS_PATH, "w", encoding="utf-8") as f:
                f.write(self.backup_paradigms)
        else:
            if PARADIGMS_PATH.exists():
                PARADIGMS_PATH.unlink()

        # Restore knots
        if self.backup_knots is not None:
            self.backup_knots.to_csv(KNOTS_PATH, index=False)
        elif self.created_knots and KNOTS_PATH.exists():
            KNOTS_PATH.unlink()

    def test_tokenize_sentence(self):
        # "Ο άνθρωπος τρέχει γρήγορα."
        text = "Ο άνθρωπος τρέχει γρήγορα."
        tokens = self.engine._tokenize_sentence(text)

        print("\nTokens:", tokens)

        # Basic Checks
        self.assertTrue(len(tokens) > 0)

        # Check 'άνθρωπος'
        token_anthropos = next((t for t in tokens if t["text"] == "άνθρωπος"), None)
        self.assertIsNotNone(token_anthropos)
        self.assertEqual(token_anthropos["lemma"], "άνθρωπος")
        self.assertTrue(token_anthropos.get("has_paradigm"))

        # Check 'τρέχει' -> 'τρέχω'
        token_trexei = next((t for t in tokens if t["text"] == "τρέχει"), None)
        self.assertIsNotNone(token_trexei)
        self.assertEqual(token_trexei["lemma"], "τρέχω")
        self.assertTrue(token_trexei.get("has_paradigm"))

        # Check 'γρήγορα' (adverb, likely no paradigm in dummy data)
        token_grigora = next((t for t in tokens if t["text"] == "γρήγορα"), None)
        self.assertIsNotNone(token_grigora)
        self.assertFalse(token_grigora.get("has_paradigm", False))

    def test_empty_input(self):
        self.assertEqual(self.engine._tokenize_sentence(""), [])
        self.assertEqual(self.engine._tokenize_sentence(None), [])

    def test_compile_curriculum_structure(self):
        # Mock select_words to return a known DataFrame
        dummy_df = pd.DataFrame([
            {
                "Lemma": "άνθρωπος",
                "Part of speech": "Ουσιαστικό",
                "Greek_Def": "Human",
                "Modern_Def": "Human",
                "Ancient_Context": "",
                "Modern_Examples": "",
                "Synonyms": "",
                "ID": "1",
                "Freq_Score": 0.9,
                "Heritage_Score": 1.0,
                "Semantic_Score": 1.0
            }
        ])
        # Ensure column name matches engine.pos_col
        # Engine detects pos_col from kelly.csv.
        # If kelly.csv loaded in __init__, it sets self.pos_col.
        # We need to use that.
        if hasattr(self.engine, 'pos_col') and self.engine.pos_col:
            dummy_df.rename(columns={"Part of speech": self.engine.pos_col}, inplace=True)

        self.engine.select_words = MagicMock(return_value=dummy_df)

        # Mock select_strategic_knots
        dummy_knot = {
             "Knot_ID": "K1", "POS_Tag": "Noun", "Regex_Ending": "ος",
             "Parent_Concept": "Case", "Nuance": "", "Description": "Nom",
             "Morpho_Constraint": ""
        }
        self.engine.select_strategic_knots = MagicMock(return_value=[dummy_knot])

        # Run compile_curriculum
        result = self.engine.compile_curriculum("Test Theme", 4)
        rows = result["worksheet_data"]

        self.assertTrue(len(rows) > 0)
        first_row = rows[0]
        self.assertIn("Target Tokens", first_row)
        self.assertEqual(first_row["Target Tokens"], [])

if __name__ == "__main__":
    unittest.main()
