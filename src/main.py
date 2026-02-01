from src.ingestion_hybrid import HybridIngestor
from src.enrichment_el import HellenicEnricher
from src.enrichment_lsj import LSJEnricher
from src.analysis import Analyzer
from src.config import (
    KELLY_FILE,
    KAIKKI_EL_FILE,
    KAIKKI_EN_FILE,
    COL_LEMMA,
    PROCESSED_DIR,
    OUTPUT_FILE,
)

DEBUG_MODE = False  # <--- SET TO FALSE FOR PRODUCTION
DEBUG_TARGETS = [
    "ωραία",
    "χρησιμοποιώ",
    "προβαίνω",
    "θερμαίνω",
    "αγαθό",
    "άγκιστρο",
    "αναδεικνύω",
    "εκμάθηση",
    "καθηγητής",
    "γραμματικός",
    "χειμωνιάτικος",
    "φαινόμενο",
    "φεμινιστικός",
    "υπενθύμιση",
    "θεολόγος",
]

debug_mode = DEBUG_MODE


def run_pipeline():
    print("--- INITIATING GREEK DIACHRONIC PIPELINE (HYBRID CORE) ---")
    if DEBUG_MODE:
        print(f"⚠️ DEBUG MODE ACTIVE. Targets: {DEBUG_TARGETS}")

    # 1. Ingest
    print("Igniting Hybrid Ingestor...")
    ingestor = HybridIngestor()

    # We need to load Kelly first to filter it
    ingestor.load_kelly()

    if DEBUG_MODE:
        # Filter the internal dataframe
        mask = ingestor.kelly_df[COL_LEMMA].isin(DEBUG_TARGETS)
        ingestor.kelly_df = ingestor.kelly_df[mask]
        ingestor.target_lemmas = set(ingestor.kelly_df[COL_LEMMA].unique())
        print(f"Filtered to {len(ingestor.target_lemmas)} words.")

    # Now run the scans (they will only scan the target lemmas)
    ingestor.scan_hellenic_core()
    ingestor.scan_english_gloss()
    # ingestor.bridge_gap_fallback() # Disabled
    # ingestor.save_paradigms()  #Disabled

    master_lookup = ingestor.master_lookup
    kelly_df = ingestor.kelly_df

    # 3. Oracle
    print("Awakening the Oracle...")
    lsj_oracle = LSJEnricher()

    # 4. Enrich
    print("Weaving Etymologies (Hellenic Source)...")
    enricher = HellenicEnricher()
    # Inject the oracle instance if needed, or let it init
    # enricher.lsj_oracle = lsj_oracle

    df = enricher.enrich_data(kelly_df, master_lookup)

    # 5. Definitions
    print("Retrieving Ancient Definitions...")
    df = lsj_oracle.enrich(df)

    # 6. Analyze
    print("Applying Philological Judgment...")
    analyzer = Analyzer()
    df = analyzer.apply_analysis(df)

    # 7. Save
    print(f"Saving Vast Data Table to {OUTPUT_FILE}...")
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    # Preview
    print("\n--- DEBUG REPORT ---")
    cols = ["Lemma", "AG_Antecedent", "Ancient_Context", "Shift_Type"]
    print(df[cols].to_string())


if __name__ == "__main__":
    run_pipeline()
