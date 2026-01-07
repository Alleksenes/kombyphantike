import pandas as pd
import difflib, random, unicodedata
from src.config import DATA_DIR, PROCESSED_DIR

WORKSHEET_PATH = DATA_DIR / "kombyphantike_worksheet.csv"
KELLY_PATH = PROCESSED_DIR / "kelly.csv"


class Examiner:
    def __init__(self):
        print("Initializing the Examiner...")

        if not WORKSHEET_PATH.exists():
            print(f"Error: {WORKSHEET_PATH} not found.")
            print("Run 'src/kombyphantike.py' first.")
            exit()

        self.df = pd.read_csv(WORKSHEET_PATH, dtype=str).fillna("")
        self.df = self.df[self.df["Greek Translation / Target Sentence"] != ""]

        if self.df.empty:
            print("Error: The worksheet is empty!")
            print(
                "You must fill the 'Greek Translation' column (manually or via AI) before testing."
            )
            exit()

        # Load Kelly for Ancient Root lookup
        self.kelly = pd.read_csv(KELLY_PATH, dtype=str)
        # Create fast lookup dict: Lemma -> Ancient Root
        self.root_map = dict(zip(self.kelly["Lemma"], self.kelly["AG_Antecedent"]))

    def normalize(self, text):
        """Standardizes text for comparison (NFC)."""
        return unicodedata.normalize("NFC", text.strip())

    def extract_focus_word(self, theme_str):
        """Extracts 'άνθρωπος' from 'Nature (Focus: άνθρωπος)'"""
        if "Focus:" in theme_str:
            try:
                return theme_str.split("Focus:")[1].replace(")", "").strip()
            except:
                return ""
        return ""

    def show_diff(self, user_input, target):
        """Prints a character-level diff."""
        matcher = difflib.SequenceMatcher(None, user_input, target)
        print("\n--- DIAGNOSIS ---")
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == "equal":
                print(f"  {user_input[a0:a1]}", end="")
            elif opcode == "insert":
                print(f"[\033[92mMISSING: {target[b0:b1]}\033[0m]", end="")
            elif opcode == "delete":
                print(f"[\033[91mDELETE: {user_input[a0:a1]}\033[0m]", end="")
            elif opcode == "replace":
                print(
                    f"[\033[91m{user_input[a0:a1]}\033[0m -> \033[92m{target[b0:b1]}\033[0m]",
                    end="",
                )
        print("\n")

    def start(self):
        print(f"\n--- SESSION START: {len(self.df)} SENTENCES ---")
        print("Type 'q' to quit. Type 'hint' for the first letter.")

        cards = self.df.to_dict(orient="records")

        score = 0

        for i, card in enumerate(cards):
            target = self.normalize(card["Greek Translation / Target Sentence"])
            english = card["Source Sentence"]
            rule = card["The Specific Sub-Condition / Nuance"]
            knot_id = card["Knot ID"]

            # Find Hero Word and Ancient Root
            hero = self.extract_focus_word(card["Theme"])
            ancient = self.root_map.get(hero, "???")

            print(f"\nCard {i+1}/{len(cards)}")
            print(f"KNOT: {knot_id}")
            print(f"RULE: {rule}")
            print(f"HERO: {hero}  (< {ancient})")
            print(f'TASK: Translate -> "{english}"')

            while True:
                user_input = input(">> ").strip()
                user_input = self.normalize(user_input)

                if user_input.lower() == "q":
                    print("Exiting...")
                    return

                if user_input.lower() == "hint":
                    print(f"Hint: {target[:3]}...")
                    continue

                if user_input == target:
                    print("✅ CORRECT.")
                    score += 1
                    break
                else:
                    print("❌ INCORRECT.")
                    self.show_diff(user_input, target)
                    print(f"Target: {target}")

                    retry = input("Try again? (y/n): ")
                    if retry.lower() != "y":
                        break

        print(f"\n--- SESSION COMPLETE ---")
        print(f"Score: {score}/{len(cards)}")


if __name__ == "__main__":
    exam = Examiner()
    exam.start()
