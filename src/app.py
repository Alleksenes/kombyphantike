import sys
import os
from pathlib import Path

# Add project root to Python Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
from src.kombyphantike import KombyphantikeEngine
from src.config import PROCESSED_DIR, DATA_DIR
from src.sync_sheets import CloudBridge

# Load Env
load_dotenv(dotenv_path=ROOT_DIR / ".env")

# Page Config
st.set_page_config(page_title="Kombyphantike", layout="wide", page_icon="🏛️")

st.title("🏛️ Kombyphantike: The Diachronic Engine")

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("The Weaver")
theme = st.sidebar.text_input("Theme", "Fate")
count = st.sidebar.number_input(
    "Sentence Count", min_value=10, max_value=100, value=20, step=10
)


# Initialize Engine
@st.cache_resource
def get_engine():
    return KombyphantikeEngine()


engine = get_engine()

# --- TAB STRUCTURE ---
tab_weave, tab_ai, tab_sync, tab_gym = st.tabs(
    ["1. Weave Template", "2. Ignite AI", "3. Cloud Sync", "4. The Gym"]
)

# --- TAB 1: WEAVE TEMPLATE ---
with tab_weave:
    st.markdown("### Step 1: Generate the Curriculum Structure")
    st.write("This creates the empty CSV with curated words and grammar knots.")

    if st.button("Weave New Worksheet"):
        with st.spinner("Consulting the Oracle..."):
            engine.generate_worksheet(theme, count)
            st.success("Worksheet Generated!")
            st.rerun()

    # Display Current Worksheet
    try:
        df = pd.read_csv(DATA_DIR / "kombyphantike_worksheet.csv")
        st.markdown(f"**Current Worksheet:** {len(df)} rows")
        st.dataframe(df, height=300)
    except:
        st.info("No worksheet found. Click 'Weave New Worksheet'.")

# --- TAB 2: IGNITE AI (GEMINI) ---
with tab_ai:
    st.markdown("### Step 2: Fill with Gemini")
    st.write("Send the worksheet to Google's AI to generate the sentences.")

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        st.error("GEMINI_API_KEY not found in .env file.")
    else:
        genai.configure(api_key=api_key)

        if st.button("Ignite Gemini (Generate Sentences)"):
            try:
                # 1. Load Instruction and CSV
                with open(DATA_DIR / "ai_instruction.txt", "r", encoding="utf-8") as f:
                    prompt_base = f.read()

                df = pd.read_csv(DATA_DIR / "kombyphantike_worksheet.csv")
                csv_content = df.to_csv(index=False)

                full_prompt = (
                    prompt_base + "\n\n### THE CSV TO FILL ###\n" + csv_content
                )

                # 2. Call Gemini
                with st.spinner("The Ghost is writing..."):
                    model = genai.GenerativeModel("gemini-3-flash-preview")
                    response = model.generate_content(full_prompt)

                    # 3. Parse Response (Extract CSV)
                    text = response.text
                    # Clean markdown code blocks if present
                    if "```csv" in text:
                        text = text.split("```csv")[1].split("```")[0]
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0]

                    # 4. Save back to file
                    from io import StringIO

                    new_df = pd.read_csv(StringIO(text))
                    new_df.to_csv(
                        DATA_DIR / "kombyphantike_worksheet.csv",
                        index=False,
                        encoding="utf-8-sig",
                    )

                st.success("Generation Complete! Check the table below.")
                st.dataframe(new_df)

            except Exception as e:
                st.error(f"AI Generation Failed: {e}")

# --- TAB 3: CLOUD SYNC ---
with tab_sync:
    st.markdown("### Step 3: Sync with Google Sheets")

    bridge = CloudBridge()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬆️ PUSH to Cloud"):
            with st.spinner("Uploading..."):
                # Redirect stdout to capture logs?
                # For now, just run it.
                bridge.push_local_to_cloud()
                st.success("Pushed completed rows to 'SENTENCES' tab.")

    with col2:
        if st.button("⬇️ PULL History"):
            with st.spinner("Downloading history..."):
                bridge.pull_stats_from_cloud()
                st.success("User Progress updated from Cloud.")

# --- TAB 4: THE GYM ---
# --- TAB 4: THE GYM ---
with tab_gym:
    st.markdown("### Step 4: Practice")

    # 1. Select Mode
    mode = st.radio(
        "Select Gym Mode:", ["Morphology Drill", "Syntax Examiner"], horizontal=True
    )

    st.divider()

    # --- MODE A: MORPHOLOGY DRILL ---
    if mode == "Morphology Drill":
        if st.button("Load New Drill Card"):
            try:
                # Load Drills
                drills = pd.read_csv(
                    PROCESSED_DIR / "modern_drills.csv", encoding="utf-8-sig"
                )

                # Handle Column Name Ambiguity (Lemma vs Λήμμα)
                lemma_col = "Lemma" if "Lemma" in drills.columns else "Λήμμα (Lemma)"

                if lemma_col not in drills.columns:
                    st.error(
                        f"CSV Error: Could not find Lemma column. Found: {drills.columns.tolist()}"
                    )
                else:
                    # Pick random card
                    card = drills.sample(1).iloc[0]
                    st.session_state["morph_card"] = card
                    # Clear previous state to avoid confusion
                    if "drill_revealed" in st.session_state:
                        del st.session_state["drill_revealed"]

            except Exception as e:
                st.error(f"Could not load drills: {e}")

        if "morph_card" in st.session_state:
            card = st.session_state["morph_card"]

            # Dynamic Column Access
            lemma_col = "Lemma" if "Lemma" in card else "Λήμμα (Lemma)"

            st.info(f"**Word:** {card[lemma_col]} ({card['POS']})")
            st.write(f"**Form Required:** {card['Drill_Type']}")

            # Input
            user_ans = st.text_input("Your Answer", key="morph_input")

            if st.button("Reveal Answer"):
                st.markdown(f"### Correct: `{card['Back']}`")

                if user_ans.strip().lower() == str(card["Back"]).strip().lower():
                    st.success("Correct! 🎉")
                elif user_ans:
                    st.error("Incorrect.")

    # --- MODE B: SYNTAX EXAMINER ---
    elif mode == "Syntax Examiner":
        # Load Worksheet
        try:
            worksheet = pd.read_csv(DATA_DIR / "kombyphantike_worksheet.csv").fillna("")
            # Filter for rows that actually have a translation
            target_col = "Greek Translation / Target Sentence"
            if target_col in worksheet.columns:
                valid = worksheet[
                    worksheet[target_col].astype(str).str.strip().str.len() > 1
                ]
            else:
                valid = pd.DataFrame()
        except:
            valid = pd.DataFrame()

        if valid.empty:
            st.warning(
                "No completed sentences found in the worksheet. Run the Weaver and Ignite AI first."
            )
        else:
            if st.button("Load New Sentence"):
                row = valid.sample(1).iloc[0]
                st.session_state["exam_row"] = row
                st.session_state["exam_revealed"] = False

            if "exam_row" in st.session_state:
                row = st.session_state["exam_row"]

                # Display Challenge
                st.markdown(f"### {row['Source Sentence']}")
                st.caption(f"**Rule:** {row['The Specific Sub-Condition / Nuance']}")
                st.caption(f"**Hero:** {row['Theme']}")

                user_greek = st.text_input("Translate to Greek:", key="syntax_input")

                if st.button("Check Translation"):
                    st.session_state["exam_revealed"] = True

                if st.session_state.get("exam_revealed", False):
                    target = row["Greek Translation / Target Sentence"]
                    st.markdown(f"**Target:** `{target}`")

                    # Simple Normalization for comparison
                    import unicodedata

                    def norm(t):
                        return unicodedata.normalize(
                            "NFC", str(t).strip().lower().strip(".,;")
                        )

                    if norm(user_greek) == norm(target):
                        st.success("Perfect Match! 🏛️")
                        st.balloons()
                    else:
                        st.warning("Close! Check accents and spelling.")
