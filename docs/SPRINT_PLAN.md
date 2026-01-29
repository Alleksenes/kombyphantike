# Kombyphantike Sprint Plan

**Sprint Strategy:** 2-Week Cycles.
**Goal:** Transform the "Prototype" into the "Alpha App."

## Sprint 1: The Anatomical Structure (Backend Focus)
*Objective: Stop sending strings. Start sending data objects.*
1.  **Task 1.1:** Integrate `spaCy` into the API pipeline.
2.  **Task 1.2:** Refactor `/fill_curriculum` to return `tokenized_sentence` lists instead of raw strings.
3.  **Task 1.3:** Link Tokens to Paradigms (Backend logic to find the declension table for a specific token).

## Sprint 2: The Interactive Surface (Frontend Focus)
*Objective: Make the text touchable.*
1.  **Task 2.1:** Create `WordChip` component (Clickable UI).
2.  **Task 2.2:** Refactor `TheScroll` to render `WrapView` of tokens instead of `Text` blocks.
3.  **Task 2.3:** Implement the **Inspector** (Bottom Sheet) skeleton.

## Sprint 3: The Voice & Memory (Hybrid)
*Objective: Audio and Persistence.*
1.  **Task 3.1 (Back):** Implement `EdgeTTS` service and `/audio` endpoint.
2.  **Task 3.2 (Front):** Implement Audio Player in the UI.
3.  **Task 3.3 (Front):** Implement `AsyncStorage` to save History ("The Archive").

## Sprint 4: The Polish & Economy (Release Prep)
*Objective: Aesthetics and Monetization foundations.*
1.  **Task 4.1:** Typography Overhaul (Gentium/Inter).
2.  **Task 4.2:** "Loading State" AdMob placeholder integration.
3.  **Task 4.3:** "The Red Pen" (User Feedback mechanism).