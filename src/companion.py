import pandas as pd
import json
import random
import re
from src.config import PROCESSED_DIR

KELLY_PATH = PROCESSED_DIR / "kelly.csv"
PARADIGMS_PATH = PROCESSED_DIR / "paradigms.json"


class Companion:
    def __init__(self):
        print("Initializing the Companion...")
        self.kelly = pd.read_csv(KELLY_PATH, dtype=str).fillna("")

        with open(PARADIGMS_PATH, "r", encoding="utf-8") as f:
            self.paradigms = json.load(f)

        # Filter for "Playable" words (Have Examples + Paradigms + Ancient Root)
        self.playable = self.kelly[
            (self.kelly["Modern_Examples"] != "")
            & (self.kelly["Lemma"].isin(self.paradigms.keys()))
            & (self.kelly["AG_Antecedent"] != "")
        ]
        print(f"Loaded {len(self.playable)} Playable Words.")

    def get_mutation_target(self, lemma):
        """Picks a random form to target (e.g. Future)."""
        forms = self.paradigms.get(lemma, [])
        valid = [
            f
            for f in forms
            if f.get("form") != lemma and "romanization" not in f.get("tags", [])
        ]
        if not valid:
            return None
        return random.choice(valid)

    def drill_mutation(self, row):
        lemma = row["Lemma"]
        examples = row["Modern_Examples"].split(" || ")
        if not examples:
            return

        # Pick one example
        sentence_pair = random.choice(examples)
        # Format: "Greek (English)"
        parts = sentence_pair.split(" (")
        greek_sent = parts[0]
        eng_sent = parts[1][:-1] if len(parts) > 1 else ""

        # Pick Target Form
        target_form = self.get_mutation_target(lemma)
        if not target_form:
            return

        target_word = target_form["form"]
        tags = " ".join(target_form.get("raw_tags", target_form.get("tags", [])))

        print("\n" + "=" * 40)
        print(f"HERO: {lemma.upper()} (< {row['AG_Antecedent']})")
        print(f"CONTEXT: {eng_sent}")
        print(f"SOURCE:  {greek_sent}")
        print(f"MISSION: Mutate to -> {tags}")

        # The user must type the new sentence OR just the new verb form?
        # Typing the whole sentence is hard if you don't know the other words.
        # Let's ask for the FORM first, then mental sentence.

        ans = input(f"Type the form ({tags}): ")

        if ans.strip() == target_word:
            print("✅ Correct.")
            print(
                f"Now say it: {greek_sent.replace(lemma, target_word)}"
            )  # Naive replacement for visualization
        else:
            print(f"❌ Incorrect. Target: {target_word}")

    def start(self):
        while True:
            row = self.playable.sample(1).iloc[0]
            self.drill_mutation(row)
            if input("\nNext? (y/n): ") != "y":
                break


if __name__ == "__main__":
    ai = Companion()
    ai.start()
