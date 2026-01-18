import json
import random
import os
import logging
from src.config import PROCESSED_DIR, DATA_DIR

# CONFIGURATION
SESSION_FILE = DATA_DIR / "current_session.json"
PARADIGMS_FILE = PROCESSED_DIR / "paradigms.json"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("Drill")


class PrecisionDriller:
    def __init__(self):
        print("Initializing the Precision Driller...")

        # 1. Load Session
        if not SESSION_FILE.exists():
            print(f"❌ No session found at {SESSION_FILE}")
            print("Run 'src/kombyphantike.py' first to generate a curriculum.")
            exit()

        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            self.session = json.load(f)

        # Extract Lemmas from Session
        self.session_lemmas = [w["Lemma"] for w in self.session["words"]]
        print(f"Loaded Session: {self.session.get('theme', 'Unknown Theme')}")
        print(f"Vocabulary: {len(self.session_lemmas)} words.")

        # 2. Load Paradigms
        if not PARADIGMS_FILE.exists():
            print(f"❌ Paradigms not found. Run 'src/main.py' first.")
            exit()

        with open(PARADIGMS_FILE, "r", encoding="utf-8") as f:
            self.all_paradigms = json.load(f)

    def clean_tags(self, raw_tags):
        """
        Filters noise from Kaikki-EL tags to show only the grammar.
        e.g. ['ρημα', 'ενεστωτας', 'α' ενικ'] -> "Ενεστώτας a' ενικ"
        """
        ignore = [
            "el-κλίσ",
            "inflection-template",
            "source",
            "header",
            "declension",
            "conjugation",
            "table-tags",
        ]
        keep = []
        for t in raw_tags:
            if t in ignore:
                continue
            if "κλίση" in t:
                continue
            keep.append(t)
        return " ".join(keep)

    def get_challenge(self):
        # Pick a random word from the session
        lemma = random.choice(self.session_lemmas)

        # Check if we have a paradigm for it
        if lemma not in self.all_paradigms:
            return None  # Skip (maybe an adverb or particle)

        forms = self.all_paradigms[lemma]
        if not forms:
            return None

        # Pick a random target form (that is NOT the lemma itself)
        # Filter out romanizations
        valid_forms = [
            f
            for f in forms
            if "romanization" not in f.get("tags", []) and f.get("form") != lemma
        ]

        if not valid_forms:
            return None

        target = random.choice(valid_forms)

        return {
            "lemma": lemma,
            "target_form": target["form"],
            "tags": target.get("raw_tags", target.get("tags", [])),
            "pos": (
                "Verb"
                if "ρημα" in str(target).lower() or "verb" in str(target).lower()
                else "Word"
            ),
        }

    def start(self):
        print("\n--- GYM OPEN: MORPHOLOGICAL MATRIX ---")
        print("Mode: Precision Drilling")
        print("Scope: Current Session Vocabulary Only")
        print("Press 'q' to quit, 'Enter' to reveal.\n")

        count = 0
        while True:
            challenge = self.get_challenge()
            if not challenge:
                continue  # Retry if word has no forms

            count += 1
            lemma = challenge["lemma"]
            tags_display = self.clean_tags(challenge["tags"])

            print(f"[{count}] HERO: {lemma}")
            print(f"    TARGET: {tags_display}")

            cmd = input(">> ")
            if cmd.lower() == "q":
                break

            print(f"    ANSWER: {challenge['target_form']}")
            print("-" * 40)


if __name__ == "__main__":
    drill = PrecisionDriller()
    drill.start()
