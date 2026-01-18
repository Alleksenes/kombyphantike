# Architecture of Kombyphantike

This document maps the anatomy of the engine. It details how raw data is transmuted into philological intelligence through four distinct layers: **Oracle**, **Pipeline**, **Application**, and **Persistence**:
- *The Oracle Layer*: Handling Ancient Greek Lexicography.
- *The Core Pipeline*: Transforming Modern Data into Diachronic Data.
- *The Application Layer*: Generating Curriculums and Worksheets.
- *The Gym*: Interactive CLI tools for practice.

## I. The Oracle Layer (Ancient Lexicography)
*Handling the raw TEI XML data of the Liddell-Scott-Jones (LSJ) Lexicon.*

### `src/lsj_fuzzy_indexer.py` (The Oracle Indexer)
Parses 27 volumes of LSJ XMLs into a high-speed JSON lookup (`lsj_index.json`).
*   **The Waterfall Logic:** A scoring algorithm for citations.
    *   *Tier 1 (Gods):* Sophokles, Homeros, Aiskhylos (+60).
    *   *Tier 2 (Philosophers):* Platon, Aristoteles (+30).
    *   *Tier 3 (Historians):* Thukydides, Herodotos (+10).
    *   *Bonus:* Presence of English Translation (+50).
*   **Canonicalization:** Strips accents, breathings, and numbers from keys (`ἔχω` → `exw`) to ensure fuzzy matching across eras.
*   **Homonym Merge:** Detects key collisions (e.g., `ωμός` vs. `ὦμος`) and merges their definitions rather than overwriting, preserving semantic breadth.
*   **Sibling Scanning:** Parses complex XML structures to link Greek text (`<foreign>`) with its translation (`<tr>`) and author (`<bibl>`) even when separated by intermediate nodes.

### `src/beta_code.py` (The *Peisistratean* Converter)
*   **Function:** Bidirectional conversion between Unicode Greek and Beta Code.
*   **Key Logic:** Implements the `canonicalize()` method, which converts between the Polytonic Greek (`ἄνθρωπος`) and the Beta Code of the digital classicist (`*a)/nqrwpos`), acting as the universal connector between the Modern dictionary (Kaikki) and the Ancient index (LSJ).

---

## II. The Core Pipeline (ETL & Analysis)
*Transforming the Modern Frequency List (Kelly) into a Diachronic Database.*

### `src/main.py` (The Orchestrator)
Executes the sequential build process: Ingestion → Enrichment → Analysis → Serialization.
*   **The Logic:** It runs the ETL (Extract, Transform, Load) sequence. It calls the Ingestor, the Enricher, and the Judge in order, producing the master `kelly.csv` database.

### `src/ingestion_hybrid.py` (The Hybrid Ingestor)
A multi-pass system that merges data from three sources:
1.  **Hellenic Core (`kaikki-el`):** The source of truth for Morphology, Etymology, and Real Examples.
2.  **English Gloss (`kaikki-en`):** The source for English definitions.
3.  **Compound Miner:** Detects sub-entries (e.g., `προβαίνω` inside `βαίνω`) and promotes them to first-class citizens.

### `src/enrichment_el.py` (The Brain)
Determines the Ancient Antecedent.
*   **Recursive Hunt:** Traces compound words back to their root (`χειμωνιάτικος` < `χειμώνας` < `χειμών`).
*   **Heuristic Reconstruction:** Reverses common phonetic shifts (e.g., `-ώνω` → `-οέω`) to find matches in LSJ when direct lookup fails.
*   **Blacklist:** Filters out meta-words like "Ancient" or "Hellenic" from being misidentified as roots.

### `src/enrichment_lsj.py` (The Bridge)
*   **Function:** Connects the Modern word (from Enrichment) to the Ancient Definition (from the Oracle).
*   **Logic:** Handles the "Sanitization" of philological characters (e.g., removing macrons `ῡ` → `υ`) before querying the Oracle. It formats the citation string (`Quote; Author; Definition`) for the final CSV.

### `src/lemmatizer.py` (The Heavy Artillery)
*   **Function:** A wrapper for `Stanza` and `OdyCy` (NLP models).
*   **Usage:** Used by `enrichment_el.py` as a fallback. If Regex fails to extract a root (e.g., `πατέρα` is Accusative, but the dictionary needs Nominative `πατήρ`), it asks the AI model to lemmatize it.

### `src/analysis.py` (The Judge)
Detects Semantic Drift.
*   **Triangulation:** Uses `paraphrase-multilingual-mpnet-base-v2` to compare the "Semantic Cloud" of Ancient meanings against Modern meanings.
*   **Metrics:** Calculates both *Centroid Distance* (General Drift) and *Max Overlap* (Survival of specific senses).

### `src/config.py` (The Map)
*   **Function:** Central configuration file defining all file paths (`data/raw`, `data/processed`, `data/dictionaries`). Ensures consistency across modules.

---

## III. The Application Layer (Curriculum Generation)
*The "Kombyphantike" (Knot-Weaving) logic.*

### `src/kombyphantike.py` (The Weaver)
Generates a targeted worksheet based on a user-provided Theme.
*   **Curator:** Selects words based on a weighted formula: `Theme Relevance (Semantic Search)` (60%) + `Ancient Heritage (Etymology)` (30%) + `Frequency` (10%).
*   **Knot Logic:** Selects Grammar Rules (`knots.csv`) that specifically govern the selected words (e.g., matching a Noun Knot to Nouns).
*   **Prompt Engineering:** Generates a strict instruction set for an LLM, demanding sentences that obey the Grammar Knot while explicitly citing the Ancient Context.
*   **Context Injection:** Now pulls `Modern_Examples` (real sentences from Kaikki) into the worksheet to ground the AI's generation in actual usage.

### `src/knot_loader.py` (The Librarian)
Parses the `knots.csv` database. Converts human-readable rules (Regex endings, POS tags, Morphological constraints) into filter logic used by the Weaver.

---

## IV. Persistence & Practice (The Gym)

### `src/sync_sheets.py` (The Bridge)
*   **Push:** Validates the local CSV worksheet and uploads completed rows to the "SENTENCES" tab of the Master Google Sheet.
*   **Pull:** Downloads the full study history to rebuild the local `user_progress.json`.
*   **Fatigue System:** Tracks word usage frequency. The Weaver uses this data to deprioritize "exhausted" words, forcing vocabulary rotation.
*   **Safety:** Uses `QUOTE_ALL` CSV handling to prevent data corruption from commas.

### `src/drill_generator.py` (The Armory)
Scans the Kaikki dictionary for inflection tables. Extracts high-value morphological forms (Aorist Stem, Genitive Singular) into `modern_drills.csv` for flashcard generation.

### `src/driller.py` (The Arena)
CLI tools that quiz the user on Morphology and Etymology, filtered strictly to the vocabulary of the current active session.
*   *Front:* `άνθρωπος (Genitive Singular)`
*   *Back:* `ανθρώπου`

### `src/examiner.py` (The Inquisitor)
A CLI tool that tests syntax retention. It takes your filled Worksheet, blanks out the Greek, and forces you to reconstruct the sentence character-by-character, providing a diff of errors.

### `src/noun_declension_extractor.py` (The Raw Evidence)
Extracts full declension tables for all nouns in the Kelly list. Used for debugging gender/declension class logic or building advanced declension drills.


