# Kombyphantike Setup Guide

## 1. Google Cloud Setup (For Sync)
To enable the `sync_sheets` module, you need a Google Service Account.

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

## 2. Data Acquisition (The Raw Materials)

*This repo does not contain the raw datasets due to licensing/size.*

1.  **Kelly Wordlist:** Place `kelly.csv` in `data/raw/`.
2.  **Kaikki Dictionary:** Download JSONL to `data/dictionaries/`.
3.  **LSJ XMLs:** Download Perseus TEI XMLs to `data/dictionaries/lsj_xml/`.


