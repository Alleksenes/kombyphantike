import logging
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

from deep_translator import GoogleTranslator

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import DATA_DIR, PROCESSED_DIR

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
CHECKPOINT_FILE = DATA_DIR / "logs" / "translation_checkpoint.txt"
BATCH_SIZE = 50  # Deep Translator batch size (keep moderate to avoid IP bans)
SLEEP_TIME = 1.0  # Respect the public endpoint

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_checkpoint(checkpoint_path: Path) -> int:
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, "r") as f:
                content = f.read().strip()
                if content:
                    return int(content)
        except Exception as e:
            logger.warning(f"Failed to read checkpoint file: {e}")
    return 0


def save_checkpoint(checkpoint_path: Path, last_id: int):
    try:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with open(checkpoint_path, "w") as f:
            f.write(str(last_id))
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")


def run_migration(db_path: Path = DB_PATH, checkpoint_path: Path = CHECKPOINT_FILE):
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    # Initialize Deep Translator (No API Key needed)
    try:
        translator = GoogleTranslator(source="el", target="en")
        logger.info("Initialized Deep Translator (Google Engine).")
    except Exception as e:
        logger.error(f"Failed to initialize Translator: {e}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    translation_cache: Dict[str, str] = {}
    last_id = get_checkpoint(checkpoint_path)
    logger.info(f"Resuming from ID: {last_id}")

    try:
        # 1. Identify Targets
        # Filtering out morphological pointers ("... of ...") to save time/bandwidth
        query = """
            SELECT id, greek_def
            FROM lemmas
            WHERE id > ?
              AND (modern_def IS NULL OR modern_def = '')
              AND (greek_def IS NOT NULL AND greek_def != '')
              AND greek_def NOT LIKE '% του %' 
              AND greek_def NOT LIKE '% της %'
            ORDER BY id ASC
        """
        cursor.execute(query, (last_id,))
        targets = cursor.fetchall()

        total_targets = len(targets)
        logger.info(
            f"Found {total_targets} lemmas needing English translation (filtered by ID > {last_id})."
        )

        if total_targets == 0:
            logger.info("No targets found. Migration complete.")
            return

        # 2. Batch Processing
        updated_count = 0
        failed_count = 0

        for i in range(0, total_targets, BATCH_SIZE):
            batch = targets[i : i + BATCH_SIZE]

            # Prepare batch for API
            api_batch_indices = []
            api_batch_texts = []
            batch_updates: List[Tuple[str, int]] = []

            # Check cache first
            for idx, (lid, g_def) in enumerate(batch):
                if g_def in translation_cache:
                    batch_updates.append((translation_cache[g_def], lid))
                else:
                    api_batch_indices.append(idx)
                    api_batch_texts.append(g_def)

            # Call API only for missing items
            if api_batch_texts:
                logger.info(
                    f"Translating {len(api_batch_texts)} new items in batch {i // BATCH_SIZE + 1}..."
                )
                try:
                    # Deep Translator supports batch translation directly
                    translated_texts = translator.translate_batch(api_batch_texts)

                    if len(translated_texts) != len(api_batch_texts):
                        logger.error(
                            f"Mismatch in translation results. Expected {len(api_batch_texts)}, got {len(translated_texts)}. Skipping."
                        )
                        failed_count += len(api_batch_texts)
                    else:
                        for j, translated_text in enumerate(translated_texts):
                            original_idx = api_batch_indices[j]
                            original_id = batch[original_idx][0]
                            original_g_def = batch[original_idx][1]

                            if translated_text:
                                translation_cache[original_g_def] = translated_text
                                batch_updates.append((translated_text, original_id))
                            else:
                                logger.warning(
                                    f"No translation returned for ID {original_id}"
                                )
                                failed_count += 1
                except Exception as e:
                    logger.error(f"Translation API Error processing batch: {e}")
                    failed_count += len(api_batch_texts)
                    # If we hit a rate limit, sleep longer
                    time.sleep(SLEEP_TIME * 2)

            # 3. Update Batch in Database
            if batch_updates:
                cursor.executemany(
                    "UPDATE lemmas SET modern_def = ? WHERE id = ?", batch_updates
                )  # Note: Updating modern_def (English)
                conn.commit()
                updated_count += len(batch_updates)
                logger.info(f"  - Updated {len(batch_updates)} rows.")

            # Update Checkpoint
            if batch:
                max_id_in_batch = batch[-1][0]
                save_checkpoint(checkpoint_path, max_id_in_batch)

            # Sleep to prevent IP ban
            if i + BATCH_SIZE < total_targets:
                time.sleep(SLEEP_TIME)

        logger.info(
            f"Migration Complete. Updated: {updated_count}, Failed: {failed_count}."
        )

    except KeyboardInterrupt:
        logger.info("Migration paused by user. Checkpoint saved.")
    except Exception as e:
        logger.error(f"Critical Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
