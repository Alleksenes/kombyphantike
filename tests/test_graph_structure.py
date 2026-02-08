import sys
import os
from unittest.mock import MagicMock, patch
import pandas as pd

# Mock modules before importing src.kombyphantike
sys.modules["spacy"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
# We need to mock src.database before importing src.kombyphantike if it's imported at top level
# But src.kombyphantike imports DatabaseManager from src.database
sys.modules["src.database"] = MagicMock()

# Now import
from src.kombyphantike import KombyphantikeEngine
from src.models import ConstellationGraph, ConstellationNode, ConstellationLink

def test_compile_curriculum_graph_structure():
    # Mock DatabaseManager
    mock_db = MagicMock()
    mock_db.get_metadata.return_value = {"ancient_context": "Test Context", "pos": "Noun"}
    mock_db.get_relations.return_value = {}
    mock_db.get_paradigm.return_value = []

    # Mock KnotLoader
    mock_knot_loader = MagicMock()
    # Mock knots DataFrame
    mock_knots_df = pd.DataFrame({
        "Knot_ID": ["K1"],
        "POS_Tag": ["Noun"],
        "Regex_Ending": ["os"],
        "Morpho_Constraint": [""],
        "Parent_Concept": ["Declension"],
        "Description": ["Test Knot"],
        "Nuance": ["Simple"],
        "Example_Word": ["logos"]
    })
    mock_knot_loader.knots = mock_knots_df
    mock_knot_loader.construct_regex.return_value = ".*"

    with patch("src.kombyphantike.DatabaseManager", return_value=mock_db), \
         patch("src.kombyphantike.KnotLoader", return_value=mock_knot_loader), \
         patch("src.kombyphantike.pd.read_csv") as mock_read_csv, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", new_callable=MagicMock) as mock_open: # For file checks

        mock_open.return_value.__enter__.return_value.read.return_value = "{}"

        # Mock Kelly Data
        mock_kelly_df = pd.DataFrame({
            "ID": ["1", "2"],
            "Lemma": ["logos", "anthropos"],
            "Part of speech": ["Ουσιαστικό", "Ουσιαστικό"],
            "Modern_Def": ["reason", "human"],
            "Greek_Def": ["log", "hum"],
            "Shift_Type": ["Direct", "Direct"],
            "Semantic_Warning": ["", ""],
            "Modern_Examples": ["Ex 1 || Ex 2", "Ex 3"],
            "Synonyms": ["", ""],
            "Similarity_Score": [0.9, 0.8]
        })

        # Mock Declensions Data (for Gender)
        mock_decls_df = pd.DataFrame({
            "Lemma": ["logos", "anthropos"],
            "Gender": ["Masc", "Masc"]
        })

        def read_csv_side_effect(*args, **kwargs):
            path_str = str(args[0]) if args else ""
            if "kelly.csv" in path_str:
                return mock_kelly_df
            elif "noun_declensions.csv" in path_str:
                return mock_decls_df
            return mock_kelly_df # Fallback

        mock_read_csv.side_effect = read_csv_side_effect

        # Initialize Engine
        engine = KombyphantikeEngine()
        # Fix pos_col detection since we mocked read_csv
        engine.pos_col = "Part of speech"

        # Override select_words to return our mock df directly
        engine.select_words = MagicMock(return_value=mock_kelly_df)
        engine._expand_word_pool = MagicMock(return_value=mock_kelly_df)

        # Override select_strategic_knots to ensure we get knots
        mock_knot = mock_knots_df.iloc[0].to_dict()
        engine.select_strategic_knots = MagicMock(return_value=[mock_knot])

        # Call compile_curriculum
        theme = "Philosophy"
        target_sentences = 4
        graph = engine.compile_curriculum(theme, target_sentences)

        # Assertions
        assert isinstance(graph, ConstellationGraph)
        assert len(graph.nodes) > 0
        assert len(graph.links) > 0

        # Check Node Attributes (x, y)
        for node in graph.nodes:
            assert hasattr(node, "x")
            assert hasattr(node, "y")
            assert isinstance(node.x, float)
            assert isinstance(node.y, float)

        # Check Center Node
        center_nodes = [n for n in graph.nodes if n.type == "theme"]
        assert len(center_nodes) == 1
        center = center_nodes[0]
        assert center.label == theme
        assert "instruction_text" in center.data
        assert "session_data" in center.data

        # Check Lemma Nodes
        lemma_nodes = [n for n in graph.nodes if n.type == "lemma"]
        assert len(lemma_nodes) > 0

        # Check Rule Nodes
        rule_nodes = [n for n in graph.nodes if n.type == "rule"]
        assert len(rule_nodes) > 0

        # Check Links
        # Should have links from Center to Lemmas
        for lemma in lemma_nodes:
            links_to_lemma = [l for l in graph.links if l.source == center.id and l.target == lemma.id]
            assert len(links_to_lemma) == 1

        # Should have links from Lemmas to Rules
        for rule in rule_nodes:
            # Find link targeting this rule
            links_to_rule = [l for l in graph.links if l.target == rule.id]
            assert len(links_to_rule) == 1
            source_id = links_to_rule[0].source
            assert source_id.startswith("lemma_")

if __name__ == "__main__":
    test_compile_curriculum_graph_structure()
    print("Test passed!")
