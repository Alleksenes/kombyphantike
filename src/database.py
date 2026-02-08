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
        try:
            cursor = self.conn.cursor()
            target_id = None
            
            # 1. Direct Lemma Lookup
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma,))
            row = cursor.fetchone()
            if row:
                target_id = row[0]
            
            # 2. 'form_of' Redirect Lookup
            if not target_id:
                cursor.execute("""
                    SELECT l.id FROM relations r
                    JOIN lemmas child ON r.child_lemma_id = child.id
                    JOIN lemmas l ON r.parent_lemma_text = l.lemma_text
                    WHERE child.lemma_text = ? AND r.relation_type = 'form_of'
                """, (lemma,))
                parent_row = cursor.fetchone()
                if parent_row:
                    target_id = parent_row[0]

            if not target_id:
                return []

            # 3. Fetch all forms for the resolved lemma ID
            cursor.execute("SELECT form_text, tags_json FROM forms WHERE lemma_id = ?", (target_id,))
            rows = cursor.fetchall()

            paradigm = []
            for r in rows:
                tags = json.loads(r["tags_json"]) if r["tags_json"] else []
                entry = {"form": r["form_text"], "tags": tags}
                if r["form_text"] == lemma:
                    entry["is_current_form"] = True
                paradigm.append(entry)
            
            return paradigm

        except Exception as e:
            logger.error(f"DB Error in get_paradigm for '{lemma}': {e}")
            return []

    def get_metadata(self, lemma):
        try:
            cursor = self.conn.cursor()
            
            # THE CRITICAL FIX: SELECT *ALL* THE COLUMNS WE NEED
            query = """
                SELECT l.pos, l.ipa, l.greek_def, l.english_def, l.shift_type, l.semantic_warning, lsj.entry_json
                FROM lemmas l
                LEFT JOIN lsj_entries lsj ON l.lsj_id = lsj.id
                WHERE l.lemma_text = ?
            """
            cursor.execute(query, (lemma,))
            row = cursor.fetchone()

            if not row:
                return {"definition": "Not found in database."}

            # Prioritize English definition, fallback to Greek
            definition = row["english_def"] if row["english_def"] else row["greek_def"]

            # Robust Jewel Mining for Ancient Context
            ancient_context = None
            if row["entry_json"]:
                try:
                    entry = json.loads(row["entry_json"])
                    for sense in entry.get("senses", []):
                        citations = sense.get("citations", [])
                        if citations:
                            # Find the first good citation
                            for cit in citations:
                                if cit.get("text") and cit.get("author"):
                                    ancient_context = {
                                        "author": cit.get("author"),
                                        "work": cit.get("work", ""),
                                        "greek": cit.get("text"),
                                        "translation": cit.get("translation", "")
                                    }
                                    break # Found a good one, stop searching
                        if ancient_context:
                            break # Found a jewel in this sense, stop searching senses
                except Exception as e:
                    logger.warning(f"LSJ JSON parse error for {lemma}: {e}")
            
            if not ancient_context:
                 ancient_context = {"author": "LSJ", "greek": "No direct citation found.", "translation": ""}


            return {
                "pos": row["pos"],
                "ipa": row["ipa"],
                "definition": definition,
                "shift_type": row["shift_type"],
                "semantic_warning": row["semantic_warning"],
                "ancient_context": ancient_context
            }

        except Exception as e:
            logger.error(f"DB Error in get_metadata for '{lemma}': {e}")
            return {}

    def close(self):
        self.conn.close()