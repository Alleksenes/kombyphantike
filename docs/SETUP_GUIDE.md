# Kombyphantike Setup Guide

## 1. Environment & Dependencies

This project uses **Poetry** for dependency management.

1.  **Install Poetry:**
    ```bash
    pip install poetry
    ```
2.  **Install Project Dependencies:**
    ```bash
    poetry install
    ```
    *Note: This includes `sentence-transformers`, `gspread`, `pandas`, `spacy`.*

3.  **Download NLP Models:**
    ```bash
    poetry run python -m spacy download en_core_web_md
    poetry run python -m spacy download el_core_news_lg
    poetry run python -c "import stanza; stanza.download('grc')"
    ```

## 2. Data Acquisition (The Treasury)

The engine requires raw datasets that are **not included** in the repository due to size and license.

### A. The Kelly List
*   **Source:** [Kelly Project](http://kelly.sketchengine.co.uk/)
*   **Action:** Download the Greek list.
*   **Path:** `data/dictionaries/KELLY_EL.xlsx`

### B. Wiktionary (Kaikki)
*   **Source:** [Kaikki.org](https://kaikki.org/dictionary/Greek/)
*   **File 1 (Greek):** `kaikki.org-dictionary-Greek-by-lang-Greek.jsonl.gz`
    *   **Rename to:** `kaikki-el.jsonl`
    *   **Path:** `data/dictionaries/kaikki-el.jsonl`
*   **File 2 (English):** `kaikki.org-dictionary-Greek.jsonl.gz`
    *   **Rename to:** `kaikki-en.jsonl`
    *   **Path:** `data/dictionaries/kaikki-en.jsonl`

### C. LSJ XMLs
*   **Source:** [PerseusDL/lexica](https://github.com/PerseusDL/lexica)
*   **Action:** Clone the repo or download the XMLs from `CTS_XML_TEI/perseus/pdllex/grc/lsj`.
*   **Path:** `data/dictionaries/lsj_xml/*.xml` (27 files).

## 3. Google Cloud (Optional Sync)
To enable `sync_sheets.py`:
1.  Go to [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a New Project (e.g., "Kombyphantike").
3.  **Enable APIs:**
    *   Search for "Google Sheets API" -> Enable.
    *   Search for "Google Drive API" -> Enable.
4.  **Create Credentials:**
    *   Go to "Credentials" -> "Create Credentials" -> "Service Account".
    *   Name it "kombyphantike-bot".
    *   Click "Done".
5.  **Download Key:**
    *   Click on the new Service Account (email address).
    *   Go to "Keys" tab -> "Add Key" -> "Create new key" -> JSON.
    *   Save this file as `kombyphantike-google-key.json` in your project root.
6.  **Share the Sheet:**
    *   Open your Google Sheet.
    *   Click "Share".
    *   Paste the `client_email` found inside your JSON key file.
    *   Give it **Editor** access.
7.  **Get Sheet ID:**
    *   Copy the long ID from your Sheet's URL.
    *   Add it to your `.env` file:
        `GOOGLE_SHEET_ID=your_long_id_here`

