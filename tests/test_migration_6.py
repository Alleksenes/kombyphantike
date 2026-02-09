import sys
import os
import importlib.util
from pathlib import Path
import pytest

# Path to the script
MIGRATION_SCRIPT = Path(__file__).resolve().parent.parent / "src" / "migration" / "6_infer_difficulty_scores.py"

def load_module(path):
    spec = importlib.util.spec_from_file_location("migration6", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

migration = load_module(MIGRATION_SCRIPT)
calculate_kds = migration.calculate_kds

def test_kelly_bonus():
    # Base=50. A1=10. Length=4 -> +2. Total=12.
    assert calculate_kds("word", None, "A1") == 12
    # C2=60. +2. Total=62.
    assert calculate_kds("word", None, "C2") == 62
    # Whitespace/Case handling
    assert calculate_kds("word", None, " a1 ") == 12

def test_frequency_fallback():
    # Common (>500) -> 30. +2. Total=32.
    assert calculate_kds("word", 600, None) == 32
    # Rare (<5) -> 80. +2. Total=82.
    assert calculate_kds("word", 4, None) == 82
    # Rare (None -> 0) -> 80. +2. Total=82.
    assert calculate_kds("word", None, None) == 82
    # Medium (100) -> Base 50. +2. Total=52.
    assert calculate_kds("word", 100, None) == 52

def test_length_penalty():
    # "longword" = 8 chars -> +4.
    # Base 50.
    assert calculate_kds("longword", 100, None) == 54

def test_clamping():
    # Very rare + very long
    # Rare=80. Length=100 -> +50. Total=130 -> Clamp 100.
    long_word = "a" * 100
    assert calculate_kds(long_word, 0, None) == 100

    # Minimum clamp check (though logic ensures positive)
    # A1=10. "a" -> +0.5. Total 10.5 -> 10.
    assert calculate_kds("a", None, "A1") >= 1
