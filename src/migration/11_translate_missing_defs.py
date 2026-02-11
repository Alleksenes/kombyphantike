import sqlite3
import os
import sys
import logging
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

try:
    from google.cloud import translate_v2 as translate
except ImportError:
    print("Error: google-cloud-translate library not found. Please install it.")
    sys.exit(1)

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
BATCH_SIZE = 100 # Adjust based on API quotas and needs
SLEEP_TIME = 0.5  # Seconds between batches

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv()

def run_migration():
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        return

    # Initialize Translate Client
    # Ensure GOOGLE_APPLICATION_CREDENTIALS is set in your environment
    try:
        translate_client = translate.Client()
    except Exception as e:
        logger.error(f"Failed to initialize Google Translate Client: {e}")
        logger.error("Ensure GOOGLE_APPLICATION_CREDENTIALS is set.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Identify Targets
        # Find rows where english_def is NULL or empty, and greek_def is present
        query = """
            SELECT id, greek_def
            FROM lemmas
            WHERE (english_def IS NULL OR english_def = '')
              AND (greek_def IS NOT NULL AND greek_def != '')
        """
        cursor.execute(query)
        targets = cursor.fetchall() # List of (id, greek_def)

        total_targets = len(targets)
        logger.info(f"Found {total_targets} lemmas needing English translation.")

        if total_targets == 0:
            logger.info("No targets found. Migration complete.")
            return

        # 2. Batch Processing
        updated_count = 0
        failed_count = 0

        # Process in batches
        for i in range(0, total_targets, BATCH_SIZE):
            batch = targets[i : i + BATCH_SIZE]
            batch_ids = [row[0] for row in batch]
            batch_greek_defs = [row[1] for row in batch]

            logger.info(f"Processing batch {i // BATCH_SIZE + 1} of {(total_targets + BATCH_SIZE - 1) // BATCH_SIZE} (Rows {i+1} to {min(i+BATCH_SIZE, total_targets)})")

            try:
                # Call Google Translate API with the batch of strings
                # format_='text' returns unescaped text (no HTML entities)
                results: List[Dict[str, Any]] = translate_client.translate(
                    batch_greek_defs,
                    target_language='en',
                    format_='text'
                )

                # Prepare updates
                batch_updates: List[Tuple[str, int]] = []

                # Verify we got the same number of results
                if len(results) != len(batch):
                    logger.error(f"Mismatch in translation results count. Expected {len(batch)}, got {len(results)}. Skipping batch.")
                    failed_count += len(batch)
                    continue

                for j, result in enumerate(results):
                    translated_text = result.get('translatedText')
                    if translated_text:
                        batch_updates.append((translated_text, batch_ids[j]))
                    else:
                        logger.warning(f"No translation returned for ID {batch_ids[j]}")
                        failed_count += 1

                # 3. Update Batch in Database
                if batch_updates:
                    cursor.executemany("UPDATE lemmas SET english_def = ? WHERE id = ?", batch_updates)
                    conn.commit()
                    updated_count += len(batch_updates)
                    logger.info(f"  - Updated {len(batch_updates)} rows.")

            except Exception as e:
                logger.error(f"Error processing batch starting at index {i}: {e}")
                failed_count += len(batch)
                # Determine if we should abort or continue.
                # For network/quota errors, maybe better to abort or sleep longer.
                # Here we continue to next batch.

            # Sleep between batches to be nice to the API
            if i + BATCH_SIZE < total_targets:
                time.sleep(SLEEP_TIME)

        logger.info(f"Migration Complete. Updated: {updated_count}, Failed: {failed_count}.")

    except Exception as e:
        logger.error(f"Critical Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
