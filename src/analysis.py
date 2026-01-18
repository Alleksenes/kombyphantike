import pandas as pd
import logging
import warnings
import numpy as np
import torch
from tqdm import tqdm
from src.config import OUTPUT_FILE

# Suppress warnings
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class Analyzer:
    def __init__(self):
        logger.info("Initializing Batch Triangulation Engine (MPNet)...")
        try:
            from sentence_transformers import SentenceTransformer, util
            from pathlib import Path

            # Try Local Path first
            MODEL_PATH = Path("models/mpnet")
            if MODEL_PATH.exists():
                self.model = SentenceTransformer(str(MODEL_PATH))
            else:
                self.model = SentenceTransformer(
                    "paraphrase-multilingual-mpnet-base-v2"
                )

            self.util = util
            self.use_transformer = True

            # Check for GPU
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            logger.info(f"Model loaded on: {self.device.upper()}")

        except Exception as e:
            logger.error(f"Transformer load failed: {e}")
            self.use_transformer = False

    def parse_definitions(self, text):
        """Splits by ; and , to create granular meaning units."""
        if not text or pd.isna(text):
            return []
        chunks = str(text).replace("|", ";").split(";")
        final = []
        for c in chunks:
            # Split by comma if chunk is long, but keep short phrases
            parts = c.split(",")
            for p in parts:
                clean = p.strip()
                if len(clean) > 2:
                    final.append(clean)
        return final

    def apply_analysis(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.use_transformer:
            logger.warning("Transformer missing. Skipping.")
            return df

        logger.info("Preparing Data for Batch Processing...")

        # 1. PREPARE LISTS
        # We need to flatten all definitions into a single list for encoding,
        # but keep track of which definitions belong to which row.

        all_ancient_texts = []
        all_modern_texts = []

        # Maps row_index -> (start_index, length) in the flattened lists
        ancient_map = []
        modern_map = []

        # Iterate once to parse text
        for _, row in df.iterrows():
            antecedent = row.get("AG_Antecedent", "")

            # If no antecedent, we skip semantic check (store empty range)
            if not antecedent or pd.isna(antecedent):
                ancient_map.append((0, 0))
                modern_map.append((0, 0))
                continue

            # Get Definitions
            lsj_raw = row.get("LSJ_Definition", "")
            mod_en_raw = row.get("Modern_Def", "")
            mod_el_raw = row.get("Greek_Def", "")

            # Prioritize Greek Def if available (Polyglot Power)
            target_modern = (
                mod_el_raw
                if pd.notna(mod_el_raw) and len(str(mod_el_raw)) > 3
                else mod_en_raw
            )

            # Parse
            anc_senses = self.parse_definitions(lsj_raw)
            mod_senses = self.parse_definitions(target_modern)

            # Map Ancient
            start_a = len(all_ancient_texts)
            all_ancient_texts.extend(anc_senses)
            len_a = len(anc_senses)
            ancient_map.append((start_a, len_a))

            # Map Modern
            start_m = len(all_modern_texts)
            all_modern_texts.extend(mod_senses)
            len_m = len(mod_senses)
            modern_map.append((start_m, len_m))

        # 2. BATCH ENCODE
        logger.info(
            f"Encoding {len(all_ancient_texts)} Ancient senses and {len(all_modern_texts)} Modern senses..."
        )

        # Encode in batches (MPNet handles batching internally, but we show progress)
        embeddings_ancient = self.model.encode(
            all_ancient_texts,
            convert_to_tensor=True,
            show_progress_bar=True,
            batch_size=64,
            device=self.device,
        )

        embeddings_modern = self.model.encode(
            all_modern_texts,
            convert_to_tensor=True,
            show_progress_bar=True,
            batch_size=64,
            device=self.device,
        )

        # 3. CALCULATE SCORES ROW-BY-ROW (Using Slices)
        logger.info("Calculating Vector Distances...")

        shift_types = []
        warnings_list = []
        scores = []

        for i, row in tqdm(df.iterrows(), total=len(df)):
            # Get Slices
            a_start, a_len = ancient_map[i]
            m_start, m_len = modern_map[i]

            # Default Values
            final_cen = 0.0
            final_max = 0.0

            # Only calculate if we have data for both sides
            if a_len > 0 and m_len > 0:
                # Slice Tensors
                cloud_a = embeddings_ancient[a_start : a_start + a_len]
                cloud_m = embeddings_modern[m_start : m_start + m_len]

                # A. Centroid Similarity
                centroid_a = torch.mean(cloud_a, dim=0)
                centroid_b = torch.mean(cloud_m, dim=0)
                final_cen = self.util.cos_sim(centroid_a, centroid_b).item()

                # B. Max Overlap
                # Compute matrix of all-vs-all for this word
                sim_matrix = self.util.cos_sim(cloud_a, cloud_m)
                final_max = torch.max(sim_matrix).item()

            # 4. DETERMINE SHIFT TYPE (Logic Gate)
            lemma = str(row["Lemma"]).lower()
            antecedent = str(row.get("AG_Antecedent", "")).lower()

            if not antecedent or antecedent == "nan":
                shift_types.append("New Coinage / Loanword")
                warnings_list.append("")
                scores.append(0.0)
                continue

            if lemma == antecedent:
                base_type = "Direct Inheritance"
            else:
                base_type = "Morphological Evolution"

            # Drift Logic
            # If we have no definitions (score 0), we assume stable if ancient context exists?
            # No, assume neutral.

            shift_res = base_type
            warn_res = "Stable Meaning"

            if a_len > 0 and m_len > 0:
                if final_max < 0.50:
                    shift_res = "False Friend / Total Drift"
                    warn_res = f"CRITICAL DRIFT (Max: {final_max:.2f})"
                elif final_max > 0.80 and final_cen < 0.60:
                    shift_res = "Semantic Focus Shift"
                    warn_res = f"MEANING NARROWED (Centroid: {final_cen:.2f})"
                elif final_max < 0.70:
                    warn_res = f"Nuance Shift (Max: {final_max:.2f})"

            shift_types.append(shift_res)
            warnings_list.append(warn_res)
            scores.append(final_cen)  # Store Centroid as main score

        # 5. ASSIGN TO DATAFRAME
        df["Shift_Type"] = shift_types
        df["Semantic_Warning"] = warnings_list
        df["Similarity_Score"] = scores

        return df
