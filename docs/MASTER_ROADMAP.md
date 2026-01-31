# Kombyphantike: The Grand Design

> **Mission:** To create a "Living Palimpsest"—a language learning entity that treats Modern Greek not as a flat surface, but as a transparent layer over Ancient Greek history.

## Ultimate Goals - Design

### A. The Brain (Backend - Python/FastAPI)
The backend is a **Microservice Orchestrator**. It transforms text into structured philological data.

*   **The Weaver (Content Gen):** Google Gemini (via `google-genai`) generating structured JSON based on strict "Grammar Knots."
*   **The Tokenizer (Structure):** `spaCy` (`el_core_news_lg`) breaking sentences into interactive tokens (`{lemma, pos, case, gender}`) to enable the Inspector.
*   **The Auditor (Verification):** `greek-nlp-toolkit` (Future) to programmatically verify if the AI-generated sentence obeys the requested Knot.
*   **The Orator (Audio):** `EdgeTTS` generating neural speech for sentences.
*   **The Oracle (Lexicography):** Custom LSJ Indexer + Kaikki Ingestor + (Future) Millas Turkish-Greek Dictionary.

### B. The Body (Frontend - React Native/Expo)
The frontend is a **Reactive Canvas** and **Persistence Layer**.

*   **The Scroll:** A vertical list of "Language Islands."
*   **The WordChip:** A component rendering individual tokens. Handles interactions (Tap/Hold).
*   **The Inspector:** A "Bottom Sheet" UI that reveals the data layers (Knot, Root, Paradigm) without leaving the context.
*   **The Garden Database:** **SQLite** (via `expo-sqlite`) storing the User's History, Word Strength, and Decay Rates.

## III. The Library Stack (Current & Future)
*   **Current:** `fastapi`, `uvicorn`, `sentence-transformers` (MPNet), `google-genai`.
*   **Sprint 1 Addition:** `spacy` (Tokenization).
*   **Sprint 3 Addition:** `edge-tts` (Audio).
*   **Future Expansion:** `epitran` (IPA/Phonetics), `nltk/wordnet` (Semantic Maps), `revenuecat` (Subscriptions).


----

## Sprints - Roadmap Steps

### **Sprint 1: Data Structuring (Backend)**
**Goal:** Convert string outputs into structured NLP objects to enable frontend interactivity.
**Dependency:** None.

1.  **Infrastructure Update:**
    *   Add `spacy` and `pydantic` to `pyproject.toml`.
    *   Update `Dockerfile` to download `el_core_news_lg` (Greek) and `en_core_web_md` (English) models during build.
2.  **Tokenization Service (`src/nlp_service.py`):**
    *   Initialize Spacy models.
    *   Create function `tokenize(text: str, lang: str) -> List[Dict]`.
    *   Output schema per token: `{ text, lemma, pos, tag, dep, is_alpha, start_char, end_char }`.
3.  **Paradigm Linking:**
    *   Load `paradigms.json` into memory (or efficient lookup).
    *   During tokenization, check if `token.lemma` exists in paradigms.
    *   Append field `has_paradigm: bool` and `paradigm_id: str` to the token object.
4.  **API Refactor:**
    *   Update `POST /fill_curriculum` response model.
    *   Include `target_sentence_tokens` (List) and `source_sentence_tokens` (List) alongside the raw strings.

### **Sprint 2: Interactive UI Components (Frontend)**
**Goal:** Render clickable tokens and display metadata.
**Dependency:** Sprint 1.

1.  **Component Implementation (`WordChip`):**
    *   Create `components/WordChip.tsx`.
    *   Accepts `token` object prop.
    *   Logic: If `has_paradigm` is true, apply specific style (underline/color).
    *   Event: `onPress` emits token data to parent.
2.  **Layout Refactor (`SentenceRenderer`):**
    *   Replace `<Text>` in `PhilologyCard` with a `<View style={{flexDirection: 'row', flexWrap: 'wrap'}}>`.
    *   Map `target_sentence_tokens` to `WordChip` components.
3.  **Inspector Module (`BottomSheet`):**
    *   Install `@gorhom/bottom-sheet`.
    *   Create `components/Inspector.tsx`.
    *   **State:** Selected Token.
    *   **View 1 (Morphology):** Display POS, Case, Gender from token data.
    *   **View 2 (Context):** Display the `Ancient Context` (passed from the parent Card).
    *   **View 3 (Paradigm):** (Placeholder for Sprint 3 data fetching).

### **Sprint 3: Local Persistence & Logic (Frontend)**
**Goal:** Save user history and track word decay ("The Garden").
**Dependency:** Sprint 2.

1.  **Database Setup:**
    *   Install `expo-sqlite`.
    *   Initialize DB `komby.db`.
    *   **Table `sessions`:** `id, date, theme, sentences_json`.
    *   **Table `word_stats`:** `lemma, last_seen, strength_score (0-100), encounter_count`.
2.  **Persistence Layer:**
    *   On successful generation (`/fill_curriculum`), write Session to DB.
    *   Iterate through tokens: Update/Insert into `word_stats`.
    *   Logic: `strength_score` increases on view, decreases over time (decay function).
3.  **UI Integration:**
    *   Create `app/history.tsx`.
    *   Query `sessions` table to display list.
    *   Clicking a session navigates to `Results` view with hydrated data (offline).

### **Sprint 4: Audio Synthesis (Backend + Frontend)**
**Goal:** Add Text-to-Speech functionality.
**Dependency:** Sprint 1.

1.  **Backend Service:**
    *   Add `edge-tts` dependency.
    *   Create `src/audio.py`.
    *   Implement `generate_audio(text, voice='el-GR-NestorNeural')`.
    *   Output: Base64 encoded MP3 string or serve file via static path.
2.  **API Endpoint:**
    *   `POST /audio/generate`: Input `{text}`, Output `{audio_data}`.
3.  **Frontend Player:**
    *   Install `expo-av`.
    *   Update `PhilologyCard`.
    *   Add "Play" icon.
    *   Logic: Fetch audio from API -> Decode -> Play.

### **Sprint 5: Production Polish & Monetization**
**Goal:** Prepare for release.
**Dependency:** Sprint 1-4.

1.  **Design System:**
    *   Implement Typography: *Gentium Plus* (Ancient), *Inter* (Modern).
    *   Refine Colors: Off-white background, high-contrast text.
2.  **Monetization Logic:**
    *   Install `react-native-purchases` (RevenueCat).
    *   Logic: Check `is_premium`.
    *   If `!is_premium`: Limit `POST /draft_curriculum` calls to 3/day.
    *   If `!is_premium`: Disable "Deep Inspector" (Paradigm tab).
3.  **Ad Integration:**
    *   Install `react-native-google-mobile-ads`.
    *   Place Banner Ad in `WeaverScreen` (bottom).
    *   Place Interstitial Ad during "Weaving" loading state.
