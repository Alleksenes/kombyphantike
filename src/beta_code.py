import json
import unicodedata
import pandas as pd
from pathlib import Path
from src.config import DICT_DIR


class BetaCodeConverter:
    def __init__(self):
        self.beta_to_uni_path = DICT_DIR / "beta_code_to_unicode.json"
        self.uni_to_beta_path = DICT_DIR / "unicode_to_beta_code.json"
        self.BETA_TO_UNICODE = self._load_json(self.beta_to_uni_path)
        self.UNICODE_TO_BETA = self._load_json(self.uni_to_beta_path)

        # Pre-calc max key length for reverse conversion
        self._max_beta_key_len = (
            max(len(k) for k in self.BETA_TO_UNICODE) if self.BETA_TO_UNICODE else 0
        )

    def _load_json(self, file_path: Path) -> dict:
        if not file_path.exists():
            raise FileNotFoundError(f"Mapping file not found at: {file_path}")
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def to_beta_code(self, greek_string: str) -> str:
        if not greek_string or pd.isna(greek_string):
            return ""
        normalized_greek = unicodedata.normalize("NFC", greek_string)
        beta_code_chars = [
            self.UNICODE_TO_BETA.get(char, char) for char in normalized_greek
        ]
        return "".join(beta_code_chars)

    def to_greek(self, beta_code_string: str) -> str:
        """Converts Beta Code to Unicode (Greedy Match)."""
        if not beta_code_string:
            return ""
        normalized_beta = unicodedata.normalize("NFC", beta_code_string)

        greek_chars = []
        i = 0
        n = len(normalized_beta)

        while i < n:
            found_match = False
            for length in range(min(self._max_beta_key_len, n - i), 0, -1):
                substring = normalized_beta[i : i + length]
                if substring in self.BETA_TO_UNICODE:
                    greek_chars.append(self.BETA_TO_UNICODE[substring])
                    i += length
                    found_match = True
                    break

            if not found_match:
                greek_chars.append(normalized_beta[i])
                i += 1

        return "".join(greek_chars)

    def canonicalize(self, text: str) -> str:
        if not text:
            return ""
        decomp = unicodedata.normalize("NFD", text)
        filtered = []
        for char in decomp:
            # Keep Letters (L) AND Numbers (N) if needed?
            # Beta code uses letters.
            if unicodedata.category(char).startswith("L"):
                filtered.append(char)

        base_text = "".join(filtered).lower()
        # No need to map sigma if we are using Latin characters
        return base_text
