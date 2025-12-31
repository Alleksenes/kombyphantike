# KOMBYPHANTIKE (Κομβυφαντική)
### The Diachronic Engine for the Antifluent Philologist

> **"ἱστὸν δ' ἐξαίνουσα λεπτὸν καὶ χαρίεντα"**
> *"Weaving a web, subtle and full of grace."* — (Odysseia 2.94)

**Kombyphantike** is not a language learning app. It is a **Computational Philology Engine** forged for the Classical Philologist who possesses a massive, dormant lexicon of Ancient Greek but struggles with the automaticity of Modern Greek.

Like **Talos**, the bronze automaton of Krete, this system is built to guard the perimeter of ancient heritage. It refuses to treat Modern Greek as a foreign language. Instead, it treats it as the latest stratification of a 3,000-year-old continuum.

## 🏛️ Ὁ Ἀγών τοῦ Ὑφάντου (The Agon of the Weaver)

I built this engine because I was drowning in the stream. I knew the roots of words like `ὕδωρ` and `ἄνθρωπος`, yet I stumbled over ordering a glass of water in Athens. The standard tools (Duolingo, Anki) treated me like a tabula rasa. *They ignored my heritage which pissed me off enof to create this beauty.*

I needed a tool that respected my past. I needed a machine that could:
1.  **Excavate** the ancient roots of every modern word I encountered.
2.  **Weave** them into sentences that forced me to practice specific, tricky grammar rules ("Knots").
3.  **Bridge** the gap between the poetic wisdom of Sophokles and the pragmatic reality of the modern street.

**Kombyphantike** is that machine. It is the Knot-Weaver. It takes the threads of the Ancient and the Modern and weaves them into an unbreakable fabric of fluency.

## ⚙️ The Philosophy

We do not memorize lists. We weave **Language Islands** based on two coordinates:
1.  **The Heritage (Deep Roots):** We prioritize words that have survived from Antiquity, explicitly linking them to their Ancient Antecedents and poetic contexts (Sophokles, Aiskhylos).
2.  **The Knot (Grammar Logic):** We isolate specific morphological rules (e.g., *Proparoxytone Nouns shifting stress in Genitive*) and force-multiply them into targeted drills.

## 🚀 Quick Start

1.  **Clone the Citadel:**
    ```bash
    git clone https://github.com/alleksenes/kombyphantike.git
    cd kombyphantike
    poetry install
    ```

2.  **Acquire Data:** (See [Setup Guide](docs/SETUP_GUIDE.md) for details).
    *   Place `kelly.csv` in `data/raw/`.
    *   Place `kaikki.org-dictionary-Greek.jsonl` in `data/dictionaries/`.
    *   Place LSJ XMLs in `data/dictionaries/lsj_xml/`.

3.  **Build the Engine:**
    ```bash
    poetry run python -m src.lsj_fuzzy_indexer
    poetry run python -m src.main
    poetry run python -m src.drill_generator
    ```

4.  **Weave a Curriculum:**
    ```bash
    poetry run python -m src.kombyphantike
    # Enter Theme: "Fate"
    # Enter Sentences: 50
    ```

5.  **Study:**
   (Usage Protocol)

    #### 1. The Weaving
    Generate your daily curriculum based on a theme.
    ```bash
    poetry run python -m src.kombyphantike
    # Enter Theme: "Fate"
    # Enter Sentences: 50
    ```
*   **Result:** Creates `data/kombyphantike_worksheet.csv` (The Template) and `data/ai_instruction.txt` (The Prompt).

    #### 2. The Synthesis
    *   **Action:** Copy the text from `ai_instruction.txt`.
    *   **Action:** Paste it into a high-quality LLM (ChatGPT-4, Claude 3.5 Sonnet).
    *   **Action:** Copy the CSV code block returned by the AI.
    *   **Action:** Paste it into `data/kombyphantike_worksheet.csv`, overwriting the file.

    #### 3. The Sync
    **Crucial:** This step saves your work to the Cloud and updates your local "Fatigue" stats so that the next session remains fresh.

    ```bash
    poetry run python -m src.sync_sheets
    ```

    **Select Option 1 (push):**
    *   *When:* After you have filled the worksheet with Greek sentences.
    *   *Action:* Uploads the new sentences to the "SENTENCES" tab of your Master Google Sheet.

    **Select Option 2 (pull):**
    *   *When:* Before starting a new batch, or if you edited the Google Sheet manually.
    *   *Action:* Downloads your entire history. Updates `user_progress.json` to mark words as "Known/Fatigued." Now only with a counter but it's prone to evolve.

    #### 4. The Gym
    Reinforce what you built. These tools use the *current session's* vocabulary.

    *   **Morphology:** `poetry run python -m src.driller`
        *   *Task:* Quiz on the specific forms (Genitive, Aorist) required by the batch's Knots.
    *   **Syntax:** `poetry run python -m src.examiner`
        *   *Task:* Reconstruct the Greek sentences from English memory. Character-perfect.

## 📚 Documentation
*   [Architecture & Logic](docs/ARCHITECTURE.md) - How the "Jewel Hunter" and "Tournament" work.
*   [Setup Guide](docs/SETUP_GUIDE.md) - Dependencies, API Keys for Google Sheets, and Data Sources.

## License
MIT. Built for the *kleos aphthiton* of the Hellenic heritage.