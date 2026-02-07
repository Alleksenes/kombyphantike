import sqlite3
import json
import logging
from pathlib import Path
from src.config import PROCESSED_DIR

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.db_path = PROCESSED_DIR / "kombyphantike_v2.db"
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def get_paradigm(self, lemma):
        """
        Retrieves paradigm. Follows 'form_of' links recursively.
        """
        try:
            cursor = self.conn.cursor()

            # 1. Find the Lemma ID (Direct)
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma,))
            row = cursor.fetchone()

            target_id = None
            if row:
                target_id = row[0]
            else:
                # 2. If not found, look for a PARENT (Soft Link)
                # "ισχύει" is not a lemma, but it points to "ισχύω"
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
                parent_row = cursor.fetchone()
                if parent_row:
                    target_id = parent_row[0]

            if not target_id:
                return []  # Return empty list, not None, to prevent crashes

            # 3. Fetch Forms for the Target
            cursor.execute(
                "SELECT form_text, tags_json FROM forms WHERE lemma_id = ?",
                (target_id,),
            )
            rows = cursor.fetchall()

            paradigm = []
            for r in rows:
                tags = json.loads(r["tags_json"]) if r["tags_json"] else []
                entry = {"form": r["form_text"], "tags": tags}
                # Highlight logic: If this form matches our input word
                if r["form_text"] == lemma:
                    entry["is_current_form"] = True
                paradigm.append(entry)

            return paradigm

        except Exception as e:
            logger.error(f"DB Error in get_paradigm: {e}")
            return []

    def get_metadata(self, lemma):
        """
        Fetches POS, IPA, Definitions (Greek/English), and Ancient Context (LSJ).
        """
        try:
            cursor = self.conn.cursor()
            # Join Lemmas with LSJ Entries
            query = """
                SELECT l.pos, l.ipa, l.greek_def, l.english_def, lsj.entry_json
                FROM lemmas l
                LEFT JOIN lsj_entries lsj ON l.lsj_id = lsj.id
                WHERE l.lemma_text = ?
            """
            cursor.execute(query, (lemma,))
            row = cursor.fetchone()

            if not row:
                return {
                    "pos": "Unknown",
                    "definition": "Definition not found.",
                    "ancient_context": None,
                }

            # 1. Definitions (Prefer English, fallback to Greek)
            definition = row["english_def"]
            if not definition:
                definition = row["greek_def"]

            # 2. Ancient Context (The Jewel Mining)
            ancient_context = None
            if row["entry_json"]:
                try:
                    entry = json.loads(row["entry_json"])
                    # Look for the first sense with a citation
                    senses = entry.get("senses", [])
                    for sense in senses:
                        if sense.get("citations"):
                            # Grab the first valid citation
                            cit = sense["citations"][0]
                            author = cit.get("author", "Ancient Source")
                            text = cit.get("text", "")
                            trans = cit.get("translation", "")
                            if text:
                                ancient_context = {
                                    "author": author,
                                    "greek": text,
                                    "translation": trans,
                                }
                                break
                except:
                    pass

            return {
                "pos": row["pos"],
                "ipa": row["ipa"],
                "definition": definition,
                "ancient_context": ancient_context,
            }

        except Exception as e:
            logger.error(f"DB Error in get_metadata: {e}")
            return {}
