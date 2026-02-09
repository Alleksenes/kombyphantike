import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import pandas as pd

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock heavy dependencies
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["transliterate"] = MagicMock()
# sys.modules["src.database"] = MagicMock() # We want to test DatabaseManager logic partially or at least mock its connection
sys.modules["elevenlabs"] = MagicMock()
sys.modules["elevenlabs.client"] = MagicMock()

from src.database import DatabaseManager
from src.kombyphantike import KombyphantikeEngine

class TestSelectWordsDB(unittest.TestCase):

    def setUp(self):
        # Mock sqlite3 connection for DatabaseManager
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor

        # Patch sqlite3.connect to return our mock connection
        self.connect_patcher = patch('sqlite3.connect', return_value=self.mock_conn)
        self.mock_connect = self.connect_patcher.start()

        # Mock pd.read_csv to avoid loading large files
        self.read_csv_patcher = patch('pandas.read_csv')
        self.mock_read_csv = self.read_csv_patcher.start()

        def read_csv_side_effect(*args, **kwargs):
            # Check the first argument (path)
            path = str(args[0]) if args else ""
            if "noun_declensions.csv" in path:
                return pd.DataFrame({"Lemma": ["example"], "Gender": ["Masculine"]})
            # Default to Kelly structure
            return pd.DataFrame({
                "Part of speech": ["Ουσιαστικό"],
                "Lemma": ["example"],
                "ID": [1],
                "Similarity_Score": [0.5],
                "Modern_Examples": ["Ex 1"],
                "Greek_Def": ["Def 1"],
                "Modern_Def": ["Def 1"],
                "Shift_Type": ["Direct Inheritance"],
                "Semantic_Warning": [""],
                "Συχνότητα (Frequency)": [0.5]
            })

        self.mock_read_csv.side_effect = read_csv_side_effect

    def tearDown(self):
        self.connect_patcher.stop()
        self.read_csv_patcher.stop()

    def test_database_select_words_query(self):
        db = DatabaseManager()
        db.select_words("theme", 0, 100, 10)

        query_args = self.mock_cursor.execute.call_args
        self.assertIsNotNone(query_args)
        query = query_args[0][0]
        params = query_args[0][1]

        self.assertIn("lemma_text LIKE '%' || ? || '%'", query)
        self.assertIn("modern_def LIKE '%' || ? || '%'", query)
        self.assertIn("kds_score BETWEEN ? AND ?", query)
        self.assertIn("ORDER BY kds_score ASC", query)

        self.assertEqual(params, ("theme", "theme", 0, 100, 10))

    def test_engine_select_words_calls_db(self):
        # Setup Engine with mocked DB
        with patch('src.kombyphantike.DatabaseManager') as MockDBManager:
            mock_db_instance = MockDBManager.return_value
            # Mock DB returning some results
            mock_db_instance.select_words.return_value = [
                {
                    "lemma_text": "word1",
                    "pos": "noun",
                    "modern_def": "def1",
                    "greek_def": "gdef1",
                    "shift_type": "Direct",
                    "frequency_score": 0.8,
                    "kds_score": 10
                }
            ]

            engine = KombyphantikeEngine()
            # Force pos_col just in case
            engine.pos_col = "Part of speech"

            # Call select_words with specific level
            result = engine.select_words("theme", 5, target_level="A1")

            # Verify DB call
            mock_db_instance.select_words.assert_called_once()
            call_args = mock_db_instance.select_words.call_args
            # A1 maps to 0, 15
            self.assertEqual(call_args[0][1], 0)
            self.assertEqual(call_args[0][2], 15)
            # Limit should be 5 * 4 = 20
            self.assertEqual(call_args[1]['limit'], 20)

            # Verify Result DataFrame structure
            self.assertIsInstance(result, pd.DataFrame)
            self.assertFalse(result.empty)
            self.assertEqual(result.iloc[0]["Lemma"], "word1")
            # "noun" should map to "Ουσιαστικό"
            self.assertEqual(result.iloc[0]["Part of speech"], "Ουσιαστικό")
            self.assertEqual(result.iloc[0]["KDS_Score"], 10)

    def test_engine_select_words_fallback(self):
         # Setup Engine with mocked DB returning empty
        with patch('src.kombyphantike.DatabaseManager') as MockDBManager:
            mock_db_instance = MockDBManager.return_value
            mock_db_instance.select_words.return_value = [] # Empty!

            engine = KombyphantikeEngine()
            engine.pos_col = "Part of speech"

            # Mock spacy nlp for fallback logic
            engine.nlp = MagicMock()
            engine.nlp.return_value.similarity.return_value = 0.5

            # Call select_words
            result = engine.select_words("theme", 5, target_level="C2")

            # Verify DB call
            mock_db_instance.select_words.assert_called_once()
            # C2 maps to 60, 100
            self.assertEqual(mock_db_instance.select_words.call_args[0][1], 60)
            self.assertEqual(mock_db_instance.select_words.call_args[0][2], 100)

            # Verify fallback result (should come from mocked kelly via read_csv)
            self.assertFalse(result.empty)
            self.assertEqual(result.iloc[0]["Lemma"], "example")

if __name__ == '__main__':
    unittest.main()
