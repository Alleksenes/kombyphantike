# Kombyphantike: The Grand Design

> **Mission:** To create a "Living Palimpsest"—a language learning entity that treats Modern Greek not as a flat surface, but as a transparent layer over Ancient Greek history.

## I. The Core Philosophy
1.  **Alchemical Inspection:** Text is not static. Every word is an interactive object containing Morphology, Etymology, and Paradigms.
2.  **The Garden (Paschein):** We do not drill; we expose. The user undergoes the language through high-quality, context-rich "Language Islands."
3.  **The Noble Gate:** A Freemium model that restricts *frequency* but never *quality*.

## II. The Technical Architecture

### A. The Brain (Backend - Python/FastAPI)
The backend is a **Microservice Orchestrator**. It does not just serve text; it processes philology.

*   **The Weaver (Content Gen):** Google Gemini (via `google-genai`) generating structured JSON.
*   **The Tokenizer (Structure):** `spaCy` (`el_core_news_lg`) breaking sentences into interactive tokens (Lemma, POS, Morphology).
*   **The Auditor (Grammar Check):** `greek-nlp-toolkit` (Future) to verify if the AI obeyed the Grammar Knot.
*   **The Orator (Audio):** `EdgeTTS` generating neural speech for sentences.
*   **The Oracle (Lexicography):** Custom LSJ Indexer + Kaikki Ingestor.

### B. The Body (Frontend - React Native/Expo)
The frontend is a **Reactive Canvas**.

*   **The Scroll:** A vertical list of "Language Islands."
*   **The WordChip:** A component rendering individual tokens. Handles interactions (Tap/Hold).
*   **The Inspector:** A "Bottom Sheet" UI that reveals the data layers (Knot, Root, Paradigm) without leaving the context.
*   **The Persistence:** Local Storage (SQLite/AsyncStorage) for history; eventually Cloud Sync.

## III. The Library Stack (Current & Future)
*   **Current:** `fastapi`, `uvicorn`, `sentence-transformers` (MPNet), `google-genai`.
*   **Immediate Addition:** `spacy` (Tokenization), `edge-tts` (Audio).
*   **Future Expansion:** `epitran` (IPA/Phonetics), `nltk/wordnet` (Semantic Maps), `revenuecat` (Subscriptions).