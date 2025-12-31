import pandas as pd
import logging
import re
from src.config import KNOTS_PATH

logger = logging.getLogger(__name__)


class KnotLoader:
    def __init__(self):
        self.knots = pd.DataFrame()
        self.load_knots()

    def load_knots(self):
        if KNOTS_PATH.exists():
            try:
                self.knots = pd.read_csv(
                    KNOTS_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig"
                )
            except:
                self.knots = pd.read_csv(
                    KNOTS_PATH, dtype=str, keep_default_na=False, encoding="utf-8"
                )

            self.knots.columns = [c.strip() for c in self.knots.columns]

            if "Regex_Ending" in self.knots.columns:
                self.knots["Regex_Ending"] = self.knots["Regex_Ending"].str.replace(
                    "\\", "", regex=False
                )

            logger.info(f"Loaded {len(self.knots)} Knots.")
        else:
            logger.warning(f"Knot Database missing at {KNOTS_PATH}.")

    def get_knot(self, knot_id):
        row = self.knots[self.knots["Knot_ID"] == knot_id]
        if row.empty:
            logger.error(f"Knot {knot_id} not found.")
            return None
        return row.iloc[0].to_dict()

    def construct_regex(self, ending_string):
        if not ending_string:
            return None
        if "|" in ending_string:
            return f"({ending_string})$"
        return f"{ending_string}$"
