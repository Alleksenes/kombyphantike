# Kombyphantike Roadmap: The Agora

## Phase 1: The Iron Core (Current)
- [x] **Hellenic Ingestion:** Merging English/Greek Wiktionary.
- [x] **LSJ Oracle:** Waterfall citation logic.
- [x] **API Exposure:** FastAPI + Docker.
- [ ] **Performance Optimization:** Pre-computing Semantic Vectors (MPNet) to reduce startup/generation time. **(PRIORITY)**
- [ ] **Data Persistence:** Database migration (SQLite/Postgres) for user history (replacing JSON files).

## Phase 2: The Fluid Experience (Next)
- [ ] **Streaming Responses:** Implementing Server-Sent Events (SSE) so the mobile app displays sentences as they are generated, reducing perceived latency.
- [ ] **Audio Synthesis:** Integrating EdgeTTS to provide audio for every sentence.
- [ ] **Smart Caching:** Redis caching for popular themes ("War", "Love") to serve instant results.

## Phase 3: The Gamified Agon (Future)
- [ ] **User Accounts:** Auth0 or Firebase integration.
- [ ] **Spaced Repetition:** Logic to push specific "Knots" based on user error rates.
- [ ] **The Collection:** A "Pokedex" for words, tracking which Ancient Citations have been discovered.