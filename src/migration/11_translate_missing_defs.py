import sqlite3
import os
import sys
import logging
import time
import json
from pathlib import Path
from typing import Optional, List, Tuple
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from src.config import PROCESSED_DIR

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: google-genai library not found. Please install it.")
    sys.exit(1)

# --- CONFIGURATION ---
DB_PATH = PROCESSED_DIR / "kombyphantike_v2.db"
BATCH_SIZE = 100
SLEEP_TIME = 1.0  # Seconds between batches or calls to respect rate limits

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv()
API_KEY = os.environ.get("GOOGLE_API_KEY")

if not API_KEY:
    logger.error("GOOGLE_API_KEY not found in environment variables.")
    sys.exit(1)

# Initialize Gemini Client
try:
    client = genai.Client(api_key=API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini Client: {e}")
    sys.exit(1)


def _translate_with_ai(greek_definition: str) -> Optional[str]:
    """
    Translates a Greek definition to English using Gemini.
    Returns the translated string or None if failed.
    """
    if not greek_definition:
        return None

    prompt = f"""
Translate the following Greek dictionary definition into a concise, semi-colon separated English equivalent. Only return the English translation.

Greek Definition: "{greek_definition}"
English Translation:
"""
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="text/plain",
                temperature=0.3, # Low temperature for more deterministic/factual output
            ),
        )

        if response.text:
            return response.text.strip()
        return None

    except Exception as e:
        logger.warning(f"Gemini API Error for definition '{greek_definition[:50]}...': {e}")
        # Optional: Add specific handling for 429 (Rate Limit) if needed
        return None


def run_migration():
    if not DB_PATH.exists():
        logger.error(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Identify Targets
        # Find rows where modern_def is NULL or empty, and greek_def is present
        query = """
            SELECT id, greek_def
            FROM lemmas
            WHERE (modern_def IS NULL OR modern_def = '')
              AND (greek_def IS NOT NULL AND greek_def != '')
        """
        cursor.execute(query)
        targets = cursor.fetchall() # List of (id, greek_def)

        total_targets = len(targets)
        logger.info(f"Found {total_targets} lemmas needing translation.")

        if total_targets == 0:
            logger.info("No targets found. Migration complete.")
            return

        # 2. Batch Processing
        updated_count = 0
        failed_count = 0

        # Process in batches
        for i in range(0, total_targets, BATCH_SIZE):
            batch = targets[i : i + BATCH_SIZE]
            batch_updates: List[Tuple[str, int]] = []

            logger.info(f"Processing batch {i // BATCH_SIZE + 1} of {(total_targets + BATCH_SIZE - 1) // BATCH_SIZE} (Rows {i+1} to {min(i+BATCH_SIZE, total_targets)})")

            for row_id, greek_def in batch:
                translated_def = _translate_with_ai(greek_def)

                if translated_def:
                    batch_updates.append((translated_def, row_id))
                else:
                    failed_count += 1

                # Sleep slightly between individual calls if needed,
                # but with Flash usually we can go faster.
                # To be safe and respect "sleep timer", we sleep a tiny bit or just between batches.
                # The prompt said "Include error handling and a sleep timer to respect API rate limits."
                # I'll put a small sleep here.
                time.sleep(0.1)

            # 3. Update Batch
            if batch_updates:
                cursor.executemany("UPDATE lemmas SET modern_def = ? WHERE id = ?", batch_updates)
                conn.commit()
                updated_count += len(batch_updates)
                logger.info(f"  - Updated {len(batch_updates)} rows.")

            # Sleep between batches
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
