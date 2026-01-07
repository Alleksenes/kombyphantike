from src.ingestion import DataIngestor
from src.enrichment import Enricher
from src.enrichment_lsj import LSJEnricher
from src.analysis import Analyzer
from src.config import COL_LEMMA, OUTPUT_FILE


def run_pipeline():
    print("--- INITIATING GREEK DIACHRONIC PIPELINE ---")

    # 1. Ingest
    ingestor = DataIngestor()
    df = ingestor.load_kelly_list()
    target_lemmas = set(df[COL_LEMMA].unique())

    # 2. Scan Kaikki
    print("Scanning Kaikki dictionary...")
    lookup_data = ingestor.create_lookup_table(target_lemmas)

    # 3. Initialize Oracle (LSJ)
    print("Awakening the Oracle...")
    lsj_oracle = LSJEnricher()

    # 4. Enrich (With Oracle Guidance)
    print("Weaving Etymologies (Lookup-Driven)...")
    enricher = Enricher(lsj_oracle=lsj_oracle)
    df = enricher.enrich_data(df, lookup_data)

    # 5. Enrich Definitions
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
    print("\n--- FINAL SAMPLE ---")
    print(df[["Lemma", "AG_Antecedent", "LSJ_Definition"]].head(10))


if __name__ == "__main__":
    run_pipeline()
