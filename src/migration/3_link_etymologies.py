import sqlite3
import json
import logging
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR
from src.beta_code import BetaCodeConverter

DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def extract_ancient_root(etym_json):
    """
    Parses kaikki-el etymology templates to find the Ancient Greek root.
    Target templates: 'κληρονομημένο' (inherited), 'ετυμ' (etymology), 'δάνειο' (loan).
    """
    if not etym_json:
        return None

    try:
        templates = json.loads(etym_json)
    except:
        return None

    for t in templates:
        name = t.get("name", "")
        args = t.get("args", {})

        # Check for Ancient Greek source ('grc')
        # Templates usually look like: {{κληρονομημένο|el|grc|λόγος}}
        # args: {'1': 'el', '2': 'grc', '3': 'λόγος'}

        source_lang = None
        root_word = None

        # Scan positional args for 'grc'
        for key, val in args.items():
            if val == "grc":
                source_lang = "grc"
                # The word is usually the NEXT argument
                # If 'grc' is at '2', word is at '3'.
                try:
                    next_key = str(int(key) + 1)
                    root_word = args.get(next_key)
                except:
                    pass
                break

        if source_lang == "grc" and root_word:
            return root_word

    return None


def link_etymologies():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    converter = BetaCodeConverter()

    # 1. Prepare LSJ Cache (Target)
    logging.info("Loading LSJ keys into memory...")
    cursor.execute("SELECT id, canonical_key, headword FROM lsj_entries")
    lsj_cache = {}

    for lid, key, head in cursor.fetchall():
        # Store by canonical beta code key (e.g., 'prostatew')
        if key:
            lsj_cache[key] = lid

        # Also store by Normalized Unicode Headword (fallback)
        # Ancient 'ἄνθρωπος' -> beta 'a)/nqrwpos' -> canonical 'anqrwpos'
        if head:
            try:
                beta = converter.to_beta_code(head)
                canon = converter.canonicalize(beta)
                lsj_cache[canon] = lid
            except:
                pass

    # 2. Iterate Modern Lemmas (Source)
    logging.info("Fetching Modern Lemmas...")
    cursor.execute("SELECT id, lemma_text, etymology_json FROM lemmas")
    lemmas = cursor.fetchall()

    logging.info(f"Weaving {len(lemmas)} words...")

    stats = {"etym_linked": 0, "direct_linked": 0, "failed": 0}

    for lemma_id, text, etym_json in tqdm(lemmas):
        target_lsj_id = None

        # STRATEGY A: The Philological Path (Parse Etymology)
        root_word = extract_ancient_root(etym_json)
        if root_word:
            try:
                # Convert the root (e.g. 'ὁμιλέω') to canonical key
                beta = converter.to_beta_code(root_word)
                canon = converter.canonicalize(beta)
                if canon in lsj_cache:
                    target_lsj_id = lsj_cache[canon]
                    stats["etym_linked"] += 1
            except:
                pass

        # STRATEGY B: The Direct Path (Fallback)
        # If no etymology found, check if the word ITSELF exists in LSJ
        # (e.g. 'άνθρωπος' -> 'ἄνθρωπος')
        if not target_lsj_id:
            try:
                beta = converter.to_beta_code(text)
                canon = converter.canonicalize(beta)
                if canon in lsj_cache:
                    target_lsj_id = lsj_cache[canon]
                    stats["direct_linked"] += 1
            except:
                pass

        # Update DB
        if target_lsj_id:
            cursor.execute(
                "UPDATE lemmas SET lsj_id = ? WHERE id = ?", (target_lsj_id, lemma_id)
            )
        else:
            stats["failed"] += 1

    conn.commit()
    conn.close()

    logging.info("--- WEAVING COMPLETE ---")
    logging.info(f"Linked via Etymology: {stats['etym_linked']}")
    logging.info(f"Linked via Direct Match: {stats['direct_linked']}")
    logging.info(
        f"Total Linked: {stats['etym_linked'] + stats['direct_linked']} / {len(lemmas)}"
    )


if __name__ == "__main__":
    link_etymologies()
