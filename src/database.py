import json
import logging
import sqlite3

from src.config import PROCESSED_DIR

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.db_path = PROCESSED_DIR / "kombyphantike_v2.db"
        # check_same_thread=False allows FastAPI to use the connection across requests
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def get_paradigm(self, lemma: str):
        """Fetches the full grammatical table for a word, following redirects."""
        try:
            cursor = self.conn.cursor()
            target_id = None

            # 1. Direct Lemma Lookup
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma,))
            row = cursor.fetchone()
            if row:
                target_id = row["id"]

            # 2. 'form_of' Redirect Lookup (If direct fails)
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
                    target_id = parent_row["id"]

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

    def get_metadata(self, lemma_text: str):
        """
        Retrieves the pre-calculated philological metadata.
        Because Script 7 (Propagator) has run, child forms already
        contain their parents' data in the database columns.
        """
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT id, lemma_text, pos, ipa, greek_def, modern_def, 
                       ancient_definitions, ancient_citations, 
                       lsj_id, kds_score
                FROM lemmas
                WHERE lemma_text = ?
            """
            cursor.execute(query, (lemma_text,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "id": row["id"],
                "lemma": row["lemma_text"],
                "pos": row["pos"],
                "ipa": row["ipa"],
                "greek_def": row["greek_def"],
                "modern_def": row["modern_def"],
                "ancient_definitions": row["ancient_definitions"],  # Semantics
                "ancient_citations": row["ancient_citations"],  # Golden Jewels
                "lsj_id": row["lsj_id"],
                "kds_score": row["kds_score"],
            }
        except Exception as e:
            logger.error(f"DB Error in get_metadata for '{lemma_text}': {e}")
            return None

    def get_relations(self, lemma_text: str) -> dict:
        """Fetches synonyms, antonyms, and etymological relatives."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM lemmas WHERE lemma_text = ?", (lemma_text,))
            row = cursor.fetchone()
            if not row:
                return {}

            lemma_id = row["id"]
            cursor.execute(
                "SELECT relation_type, parent_lemma_text FROM relations WHERE child_lemma_id = ?",
                (lemma_id,),
            )

            relations = {}
            for r in cursor.fetchall():
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
        """Thematic search constrained by the KDS (Pedagogical Filter)."""
        try:
            cursor = self.conn.cursor()
            # Theme search looks at the word itself AND our new pre-calculated meanings
            query = """
                SELECT * FROM lemmas
                WHERE (
                    lemma_text LIKE '%' || ? || '%'
                    OR modern_def LIKE '%' || ? || '%'
                    OR ancient_definitions LIKE '%' || ? || '%'
                )
                AND kds_score BETWEEN ? AND ?
                ORDER BY kds_score ASC
                LIMIT ?
            """
            cursor.execute(query, (theme, theme, theme, min_kds, max_kds, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"DB Error in select_words for theme '{theme}': {e}")
            return []

    def close(self):
        self.conn.close()
