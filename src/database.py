import json
import logging
import sqlite3

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
                cursor.execute(
                    """
                    SELECT l.id FROM relations r
                    JOIN lemmas child ON r.child_lemma_id = child.id
                    JOIN lemmas l ON r.parent_lemma_text = l.lemma_text
                    WHERE child.lemma_text = ? AND r.relation_type = 'form_of'
                """,
                    (lemma,),
                )
                parent_row = cursor.fetchone()
                if parent_row:
                    target_id = parent_row[0]

            if not target_id:
                return []

            # 3. Fetch all forms for the resolved lemma ID
            cursor.execute(
                "SELECT form_text, tags_json FROM forms WHERE lemma_id = ?",
                (target_id,),
            )
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
                SELECT l.id, l.pos, l.ipa, l.greek_def, l.english_def, l.shift_type, l.semantic_warning, l.etymology, lsj.entry_json
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
            etymology_text = row["etymology_text"]
            lemma_id = row["id"]

            # Parent Inheritance Logic
            # Check if this lemma is a form of another lemma (the parent)
            cursor.execute(
                """
                SELECT parent_lemma_text
                FROM relations
                WHERE child_lemma_id = ? AND relation_type = 'form_of'
            """,
                (lemma_id,),
            )

            parent_rel = cursor.fetchone()

            target_lemma_for_gender = lemma
            target_id_for_gender = lemma_id

            if parent_rel:
                parent_lemma = parent_rel[0]

                # Fetch Parent Metadata
                cursor.execute(
                    """
                    SELECT id, english_def, greek_def, etymology_text
                    FROM lemmas
                    WHERE lemma_text = ?
                """,
                    (parent_lemma,),
                )

                parent_row = cursor.fetchone()

                if parent_row:
                    # Inherit Definition if missing in child
                    if not definition:
                        definition = (
                            parent_row["english_def"]
                            if parent_row["english_def"]
                            else parent_row["greek_def"]
                        )

                    # Inherit Etymology if missing in child
                    if not etymology_text:
                        etymology_text = parent_row["etymology_text"]

                    # Switch target for gender lookup to Parent
                    target_lemma_for_gender = parent_lemma
                    target_id_for_gender = parent_row["id"]

            # Gender Lookup
            # We look for the form entry that matches the target lemma text (canonical form)
            # This is where gender tags usually live (e.g. for nouns)
            gender = None
            cursor.execute(
                """
                SELECT tags_json
                FROM forms
                WHERE lemma_id = ? AND form_text = ?
            """,
                (target_id_for_gender, target_lemma_for_gender),
            )

            form_row = cursor.fetchone()
            if form_row and form_row["tags_json"]:
                try:
                    tags = json.loads(form_row["tags_json"])
                    for tag in tags:
                        if tag in ["masculine", "feminine", "neuter"]:
                            gender = tag
                            break
                except json.JSONDecodeError:
                    pass

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
                                        "translation": cit.get("translation", ""),
                                    }
                                    break  # Found a good one, stop searching
                        if ancient_context:
                            break  # Found a jewel in this sense, stop searching senses
                except Exception as e:
                    logger.warning(f"LSJ JSON parse error for {lemma}: {e}")

            if not ancient_context:
                ancient_context = {
                    "author": "LSJ",
                    "greek": "No direct citation found.",
                    "translation": "",
                }

            result = {
                "pos": row["pos"],
                "ipa": row["ipa"],
                "definition": definition,
                "shift_type": row["shift_type"],
                "semantic_warning": row["semantic_warning"],
                "etymology_text": etymology_text or "",
                "ancient_context": ancient_context,
            }

            if gender:
                result["gender"] = gender

            return result

        except Exception as e:
            logger.error(f"DB Error in get_metadata for '{lemma}': {e}")
            return {}

    def get_relations(self, lemma_text: str) -> dict:
        try:
            cursor = self.conn.cursor()

            # 1. Find the ID of the lemma
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma_text,))
            row = cursor.fetchone()

            if not row:
                return {}

            lemma_id = row[0]

            # 2. Query relations table
            cursor.execute(
                """
                SELECT relation_type, parent_lemma_text
                FROM relations
                WHERE child_lemma_id = ?
            """,
                (lemma_id,),
            )

            rows = cursor.fetchall()

            # 3. Group by relation_type
            relations = {}
            for r in rows:
                rtype = r["relation_type"]
                target = r["parent_lemma_text"]

                if rtype not in relations:
                    relations[rtype] = []
                relations[rtype].append(target)

            return relations

        except Exception as e:
            logger.error(f"DB Error in get_relations for '{lemma_text}': {e}")
            return {}

    def select_words(self, theme: str, min_kds: int, max_kds: int, limit: int) -> list:
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT * FROM lemmas
                WHERE (
                    lemma_text LIKE '%' || ? || '%'
                    OR modern_def LIKE '%' || ? || '%'
                )
                AND kds_score BETWEEN ? AND ?
                ORDER BY kds_score ASC
                LIMIT ?
            """
            cursor.execute(query, (theme, theme, min_kds, max_kds, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"DB Error in select_words for theme '{theme}': {e}")
            return []

    def close(self):
        self.conn.close()
