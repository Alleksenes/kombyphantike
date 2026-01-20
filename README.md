# KOMBYPHANTIKE (Κομβυφαντική)
### The Diachronic Engine for the Antifluent Philologist

> **"ἀλλ' ὅτε δὴ μύθους καὶ μήδεα πᾶσιν ὕφαινον."**
> *"But when they began to weave the web of words and of devices in the presence of all..."* — (Homeros, Ilias, 3.212)

**Kombyphantike** is not a language learning app. It is a **Computational Philology Engine** forged for the Classical Philologist who possesses a massive, dormant lexicon of Ancient Greek but struggles with the automaticity of Modern Greek.

## 📚 Documentation
*   [Architecture & Logic](docs/ARCHITECTURE.md) - How the "Jewel Hunter" and "Tournament" work.
*   [Setup Guide](docs/SETUP_GUIDE.md) - Dependencies, API Keys, and Data Sources.

## 🏛️ Ὁ Ἀγών τοῦ Ὑφάντου (The Agon of the Weaver)

I built this engine because I was drowning in the stream. I knew the roots of words like `ὕδωρ` and `ἄνθρωπος`, yet I stumbled over ordering a glass of water in Athens. The standard tools (Duolingo, Anki) treated me like a tabula rasa. *They ignored my heritage which pissed me enof to create this beauty.*

I needed a tool that respected my past. I needed a machine that could:
1.  **Excavate** the ancient roots of every modern word I encountered.
2.  **Weave** them into sentences that forced me to practice specific, tricky grammar rules ("Knots").
3.  **Bridge** the gap between the poetic wisdom of Sophocles and the pragmatic reality of the modern street.

**Kombyphantike** is that machine. It is the Knot-Weaver. It takes the threads of the Ancient and the Modern and weaves them into an unbreakable fabric of fluency.

## ⚙️ The Philosophy

We do not memorize lists. We weave **Language Islands** based on two coordinates:
1.  **The Heritage (Deep Roots):** We prioritize words that have survived from Antiquity, explicitly linking them to their Ancient Antecedents and poetic contexts (Sophocles, Aeschylus).
2.  **The Knot (Grammar Logic):** We isolate specific morphological rules (e.g., *Proparoxytone Nouns shifting stress in Genitive*) and force-multiply them into targeted drills.

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/alleksenes/kombyphantike.git
cd kombyphantike
poetry install
```

### 2. Data Acquisition
*(See [Setup Guide](docs/SETUP_GUIDE.md) for detailed instructions on acquiring the copyrighted datasets: Kelly List, Kaikki Dictionary, and LSJ XMLs).*

### 3. Build the Engine
Run these commands once to index the dictionaries and enrich the database.
```bash
poetry run python -m src.lsj_fuzzy_indexer
poetry run python -m src.main
poetry run python -m src.drill_generator
```

---

## 🐳 Docker Deployment

To deploy the Kombyphantike API using Docker:

### 1. Build the Image
```bash
docker build -t kombyphantike-api .
```

### 2. Run the Container
```bash
docker run -p 8000:8000 kombyphantike-api
```
The API will be available at `http://localhost:8000`. You can access the automatic documentation at `http://localhost:8000/docs`.

---

## 💻 The Web Interface (In Progress)

The engine includes a **Streamlit Command Console** that integrates the Weaver, the AI (Gemini), and the Cloud Sync into a single UI.

```bash
poetry run streamlit run src/app.py
```

*   **Tab 1 (Weave):** Select a Theme ("Fate", "Sea") and generate a Curriculum.
*   **Tab 2 (Ignite):** Send the curriculum to Google Gemini to auto-generate sentences.
*   **Tab 3 (Sync):** Push your work to Google Sheets.
*   **Tab 4 (Gym):** Practice Morphology and Syntax interactively.

---

## ⚔️ The CLI Protocol (Manual Mode)

If you prefer the command line or manual AI prompting:

### 1. The Weaving
Generate your daily curriculum based on a theme.
```bash
poetry run python -m src.kombyphantike
# Enter Theme: "Fate"
# Enter Sentences: 50
```
*   **Result:** Creates `data/kombyphantike_worksheet.csv` (The Template) and `data/ai_instruction.txt` (The Prompt).

### 2. The Synthesis
*   **Action:** Copy the text from `ai_instruction.txt`.
*   **Action:** Paste it into a high-quality LLM.
*   **Action:** Copy the CSV code block returned by the AI.
*   **Action:** Paste it into `data/kombyphantike_worksheet.csv`, overwriting the file.

### 3. The Sync
**Crucial:** This step saves your work to the Cloud and updates your local "Fatigue" stats so that the next session remains fresh.

```bash
poetry run python -m src.sync_sheets
```
*   **Push:** Uploads new sentences to your Master Google Sheet.
*   **Pull:** Downloads history to update "Known Words" tracking.

### 4. The Gym
Reinforce what you built.
*   **Morphology:** `poetry run python -m src.driller`
*   **Syntax:** `poetry run python -m src.examiner`

## License
MIT. Built for the *kleos aphthiton* of the Hellenic heritage.