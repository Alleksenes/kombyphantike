import sqlite3
import json
import logging
from pathlib import Path
from src.config import PROCESSED_DIR

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.db_path = PROCESSED_DIR / "kombyphantike_v2.db"
        if not self.db_path.exists():
            logger.warning(
                f"Database not found at {self.db_path}. Functionality may be limited."
            )

        # Connect to the database
        # check_same_thread=False allows using the connection across threads (e.g., in FastAPI)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def get_paradigm(self, lemma):
        """
        Retrieves the inflection paradigm for a given lemma.
        Returns a list of dicts: [{'form': '...', 'tags': [...]}, ...]
        """
        try:
            # 1. Try Direct Lookup
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma,))
            result = cursor.fetchone()

            target_id = None
            if result:
                target_id = result[0]
            else:
                # 2. Try Lookup via Relations (The Soft Link)
                # Find if this word is a form of another word
                cursor.execute(
                    """
                    SELECT l.id 
                    FROM relations r
                    JOIN lemmas l ON r.parent_lemma_text = l.lemma_text
                    JOIN lemmas child ON r.child_lemma_id = child.id
                    WHERE child.lemma_text = ? AND r.relation_type = 'form_of'
                """,
                    (lemma,),
                )
                parent_result = cursor.fetchone()
                if parent_result:
                    target_id = parent_result[0]  # Switch target to the Parent ID

            if not target_id:
                return None

            # 3. Fetch Forms for the Target ID (Child or Parent)
            cursor.execute(
                "SELECT form_text, tags_json FROM forms WHERE lemma_id = ?",
                (target_id,),
            )
            rows = cursor.fetchall()

            if not rows:
                # Check relations table: SELECT parent_lemma_text FROM relations WHERE child_lemma_id = ? AND relation_type = 'form_of'.
                query_rel = """
                    SELECT r.parent_lemma_text
                    FROM relations r
                    JOIN lemmas l ON r.child_lemma_id = l.id
                    WHERE l.lemma_text = ? AND r.relation_type = 'form_of'
                """
                cursor.execute(query_rel, (lemma,))
                row_rel = cursor.fetchone()

                if row_rel:
                    parent_lemma = row_rel["parent_lemma_text"]
                    # Query forms for the Parent ID (via lemma text)
                    cursor.execute(query_rel, (parent_lemma,))
                    rows = cursor.fetchall()

                    if rows:
                        paradigm = []
                        for row in rows:
                            tags = []
                            if row["tags_json"]:
                                try:
                                    tags = json.loads(row["tags_json"])
                                except json.JSONDecodeError:
                                    tags = []

                            entry = {"form": row["form_text"], "tags": tags}

                            # Verify if the original word exists in that paradigm and mark it as is_current_form: True.
                            if row["form_text"] == lemma:
                                entry["is_current_form"] = True

                            paradigm.append(entry)

                        return paradigm

                return None

            paradigm = []
            for row in rows:
                tags = []
                if row["tags_json"]:
                    try:
                        tags = json.loads(row["tags_json"])
                    except json.JSONDecodeError:
                        tags = []

                paradigm.append({"form": row["form_text"], "tags": tags})

            return paradigm
        except sqlite3.Error as e:
            logger.error(f"Database error in get_paradigm: {e}")
            return None

    def get_metadata(self, lemma):
        """
        Retrieves metadata for a given lemma, including POS, IPA, Etymology, and Ancient Context.
        Returns a dict: { "pos": ..., "ipa": ..., "ancient_context": ..., "etymology": ... }
        """
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT l.pos, l.ipa, l.etymology_json, lsj.entry_json
                FROM lemmas l
                LEFT JOIN lsj_entries lsj ON l.lsj_id = lsj.id
                WHERE l.lemma_text = ?
            """
            cursor.execute(query, (lemma,))
            row = cursor.fetchone()

            if not row:
                return None

            # Process Ancient Context from LSJ entry_json
            ancient_context = ""
            if row["entry_json"]:
                try:
                    entry = json.loads(row["entry_json"])
                    senses = entry.get("senses", [])
                    definitions = []
                    for sense in senses:
                        defn = sense.get("definition", "").strip()
                        if defn:
                            definitions.append(defn)
                    ancient_context = " || ".join(definitions)
                except json.JSONDecodeError:
                    pass

            return {
                "pos": row["pos"],
                "ipa": row["ipa"],
                "ancient_context": ancient_context,
                "etymology": row["etymology_json"],
            }
        except sqlite3.Error as e:
            logger.error(f"Database error in get_metadata: {e}")
            return None

    def close(self):
        self.conn.close()
