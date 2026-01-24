import sys
import pickle
import logging
from src.kombyphantike import KombyphantikeEngine
from src.config import PROCESSED_DIR

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting vector pre-computation...")

    # Instantiate engine to leverage its data loading and model initialization logic.
    # This ensures we use the exact same logic for loading kelly.csv as the application.
    try:
        engine = KombyphantikeEngine()
    except Exception as e:
        logger.error(f"Failed to initialize KombyphantikeEngine: {e}")
        sys.exit(1)

    if not engine.use_transformer:
        logger.warning("Transformer model not available. Skipping pre-computation.")
        sys.exit(0)

    logger.info(f"Computing vectors for {len(engine.kelly)} rows...")

    # We work on a copy to avoid modifying the engine's dataframe,
    # though we only need to read.
    candidates = engine.kelly.copy()

    # Replicate the logic for Target_Def from select_words method
    # candidates["Target_Def"] = candidates["Greek_Def"].fillna(candidates["Modern_Def"])

    # We want to compute vectors for ALL rows in engine.kelly to maintain 1-to-1 alignment.
    # If a row has no definition, we can either:
    # 1. Compute embedding for empty string (result is a vector).
    # 2. Compute embedding for a placeholder.
    # 3. Use a zero vector.

    # Since select_words filters out empty Target_Def later:
    # candidates = candidates[candidates["Target_Def"].notna() & (candidates["Target_Def"] != "")]
    # It means rows with empty definitions are never used for similarity search.
    # So their embedding value doesn't matter much, as long as it exists to preserve index alignment.
    # An empty string embedding is fine.

    candidates["Target_Def"] = candidates["Greek_Def"].fillna(candidates["Modern_Def"])
    definitions = candidates["Target_Def"].fillna("").tolist()

    # Compute embeddings
    # convert_to_tensor=False returns numpy arrays (or list of numpy arrays)
    corpus_emb = engine.model.encode(
        definitions,
        convert_to_tensor=False,
        show_progress_bar=True
    )

    # Save the embeddings
    output_path = PROCESSED_DIR / "vectors.pkl"
    logger.info(f"Saving vectors to {output_path}...")

    with open(output_path, "wb") as f:
        pickle.dump(corpus_emb, f)

    logger.info("Pre-computation complete.")

if __name__ == "__main__":
    main()
