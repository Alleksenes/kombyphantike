# Kombyphantike Backend Roadmap: The Engine

> *"The Soul of the Machine."*

This roadmap defines the evolution of the Python-based backend, moving from a static script to a dynamic, philologically aware API service.

## Phase 1: The Foundation (Completed)
- [x] **Hellenic Core Ingestion:** Replaced English-centric data with `kaikki-el` (Greek Wiktionary) for deep morphology and real-world examples.
- [x] **The Waterfall Oracle:** Perfected the LSJ Indexer to prioritize "Jewel" citations (Poets > Philosophers > Historians) and merge homonyms.
- [x] **Compound Deconstruction:** Implemented recursive etymology hunting (`χειμωνιάτικος` < `χειμώνας` < `χειμών`).
- [x] **Vector Optimization:** Implemented `precompute_vectors.py` to freeze the Semantic Brain (`MPNet`), reducing startup time to near-zero.
- [x] **API Exposure:** Refactored CLI logic into `FastAPI` with Docker containerization.
- [x] **Server-Side AI:** Integrated Google Gemini (via `google-genai` SDK) to handle sentence generation on the server.

## Phase 2: The Philological Microservices (Current Focus)
*Objective: To transform strings into structured data objects.*

- [ ] **Response Tokenization (The Dissector):**
    - Integrate `spaCy` (`el_core_news_lg`) into the API response pipeline.
    - **Goal:** Return sentences not as strings, but as lists of token objects (`{text, lemma, pos, case}`) to enable interactivity in the frontend.
- [ ] **The Philology Engine (`src/philology.py`):**
    - **The Phonologist:** Integrate `epitran` to generate IPA for both Ancient and Modern forms (visualizing the "Phonetic Collapse").
    - **The Cartographer:** Integrate `WordNet` (via NLTK) to map synonyms and hypernyms.
- [ ] **Paradigm Linking:**
    - Update the API to attach specific Declension Tables (from `paradigms.json`) to the tokenized response.

## Phase 3: The Voice & The Cloud (Next)
- [ ] **Audio Synthesis (The Orator):**
    - Integrate `EdgeTTS` to generate audio files for sentences on demand.
    - Endpoint: `GET /audio/{sentence_hash}`.
- [ ] **Cloud Deployment:**
    - Deploy Docker container to Google Cloud Run or Railway.
    - Set up Redis for caching frequent Theme requests.

## Phase 4: The Deinomolpe (Future)
- [ ] **Advanced Grammar Audit:** Integrate `greek-nlp-toolkit` (AUEB) to programmatically verify if the AI-generated sentence actually obeys the requested Grammar Knot.
- [ ] **User Accounts:** Transition from local JSON files to a PostgreSQL database to track user progress across devices.