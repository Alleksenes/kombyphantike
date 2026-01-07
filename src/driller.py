import pandas as pd
import random, json, glob, os
from src.config import SESSIONS_DIR, DRILLS_FILE


class Driller:
    def __init__(self):
        self.session_file = self.get_latest_session()

        if not self.session_file:
            print("No sessions found! Run 'src/shuffler.py' first.")
            exit()

        print(f"Loading Session: {self.session_file.name}")

        with open(self.session_file, "r", encoding="utf-8") as f:
            self.session = json.load(f)

        self.drills_db = pd.read_csv(DRILLS_FILE, dtype=str)
        session_lemmas = [w["Lemma"] for w in self.session["words"]]
        self.active_drills = self.drills_db[
            self.drills_db["Lemma"].isin(session_lemmas)
        ]

    def get_latest_session(self):
        """Finds the most recently created JSON file in sessions dir."""
        files = list(SESSIONS_DIR.glob("*-session.json"))
        if not files:
            return None
        # Sort by creation time (latest last)
        latest_file = max(files, key=os.path.getctime)
        return latest_file

    def start(self):
        drills = self.active_drills.to_dict(orient="records")
        if not drills:
            print(
                "No drills found for these words! (Maybe they are uninflected particles?)"
            )
            return

        random.shuffle(drills)

        print(f"\n--- GYMNASIUM OPENED ({len(drills)} cards) ---")
        print("Press ENTER to reveal answer. Press 'q' to quit.\n")

        for i, card in enumerate(drills):
            print(f"Card {i+1}/{len(drills)}")
            print(f"Word:  {card['Lemma']} ({card['POS']})")
            print(f"Form:  {card['Drill_Type'].upper()}")

            cmd = input(">> ")
            if cmd.lower() == "q":
                break

            print(f"Answer: {card['Back']}")
            print("-" * 30)
            input("(Next...)")


if __name__ == "__main__":
    gym = Driller()
    gym.start()
