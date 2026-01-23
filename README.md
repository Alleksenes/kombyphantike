# KOMBYPHANTIKE (Κομβυφαντική)
### The Diachronic Engine for the Antifluent Philologist

> **"ἀλλ' ὅτε δὴ μύθους καὶ μήδεα πᾶσιν ὕφαινον."**
> *"But when they began to weave the web of words and of devices in the presence of all..."* — (Homeros, Ilias, 3.212)

**Kombyphantike** is not a language learning app. It is a **Computational Philology Engine** forged for the Classical Philologist who possesses a massive, dormant lexicon of Ancient Greek but struggles with the automaticity of Modern Greek.

## 📚 Documentation
*   [Architecture & Logic](docs/ARCHITECTURE.md) - How the "Jewel Hunter" and "Tournament" work.
*   [Setup Guide](docs/SETUP_GUIDE.md) - Dependencies, API Keys, and Data Sources.
* [Bibliography & Sources](docs/BIBLIOGRAPHY.md) - The Giants we stand on.

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
3.  **The Context (The Agora):** We mine real-world usage examples from the Hellenic Core (`kaikki-el` & `kaikki-en`) to ground the ancient roots in modern reality.

## ⚙️ The Engine

*   **The Oracle:** An LSJ Indexer that hunts for "Jewel" citations (Poets > Philosophers > Historians).
*   **The Brain:** A Hybrid Ingestor that merges English and Greek Wiktionary data to find Compound Parents (`προβαίνω` < `βαίνω`).
*   **The Weaver:** A Curriculum Generator that uses Semantic AI (`MPNet`) to curate words by Theme + Heritage + Frequency.

## 🚀 Quick Start

### 1. Installation

This project uses **Poetry**.

```bash
git clone https://github.com/alleksenes/kombyphantike.git
cd kombyphantike
poetry install
```

### 2. Data Acquisition
*(See [Setup Guide](docs/SETUP_GUIDE.md) for detailed instructions on acquiring the copyrighted datasets: Kelly List, Kaikki Dictionary, and LSJ XMLs).*

*   Place kelly.csv in data/raw/.
*   Place kaikki-el.jsonl and kaikki-en.jsonl in data/dictionaries/.
*   Place LSJ XMLs in data/dictionaries/lsj_xml/.

### 3. Build the Database (One-Time)
Run these commands once to index the dictionaries and enrich the database.
```bash
# 1. Build the Ancient Index (The Oracle)
poetry run python -m src.lsj_fuzzy_indexer

# 2. Ingest & Enrich (The Core)
poetry run python -m src.main

# 3. Forge Drills (The Armory)
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

## ⚔️ The Study Mode - Kombyphantike Batch (Manual Mode)

If you prefer the command line or manual AI prompting:

### 1. Weaving The Curriculum
Generate your daily curriculum based on a theme.
```bash
poetry run python -m src.kombyphantike
# Enter Theme: "Fate"
# Enter Sentences: 50
```
*   **Output**: data/kombyphantike_worksheet.csv (The Worksheet) + data/ai_instruction.txt (The Prompt).
*   **Action**: Feed the prompt to an LLM. Paste the result back into the CSV.

### 2. The Sync & User Progress
**Crucial:** This step saves your work to the Cloud and updates your local "Fatigue" stats so that the next session remains fresh.
```bash
poetry run python -m src.sync_sheets
```
*   **Push (1)**: Uploads your curated and generated `kombyphantike_worksheet.csv` to Google Sheets.

*   **Pull (2)**: Updates "Word Fatigue" and "Knot Fatigue" to ensure rotation.

### 3. The Gym
Reinforce what you built.
*   **Morphology:** `poetry run python -m src.driller`
*   **Syntax:** `poetry run python -m src.examiner`

## Troubleshooting

### CSV/Sync Errors
If `sync_sheets.py` fails or uploads broken rows:
1.  **Check Quotes:** Ensure the AI output in `kombyphantike_worksheet.csv` wraps every cell in double quotes (`"sentence"`), especially if it contains commas.
2.  **Check Headers:** Ensure your Google Sheet has all columns matching the CSV headers.


## License
MIT. Built for the *kleos aphthiton* of the Hellenic heritage.