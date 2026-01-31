from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.kombyphantike import KombyphantikeEngine
import re
import logging
from pathlib import Path
import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. Logging & Config
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kombyphantike-api")

app = FastAPI(title="Kombyphantike API", version="0.2.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Secure this for production later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Engine Lifecycle
engine = None


@app.on_event("startup")
async def startup_event():
    global engine
    logger.info(">>> STARTUP SEQUENCE <<<")

    # Load Env
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    # Init Engine
    try:
        engine = KombyphantikeEngine()
        logger.info("--- ENGINE: Ready.")
    except Exception as e:
        logger.error(f"--- ENGINE ERROR: {e}")


# 3. Data Models
class DraftRequest(BaseModel):
    theme: str
    count: int


class FillRequest(BaseModel):
    # The client sends back the draft data to be filled
    worksheet_data: list
    instruction_text: str


# 4. Helper: Gemini
def call_gemini(prompt_text: str):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise Exception("Google API Key missing")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",  # Stable model
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE",
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE",
                    ),
                ],
            ),
        )
        if not response.text:
            raise ValueError("Empty response from AI")

        # Clean Markdown
        clean = response.text.strip()
        # Remove Markdown
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]

        clean = clean.strip()

        # SANITIZATION: Fix common JSON escape errors
        # 1. Escape backslashes that aren't already escaped?
        # Actually, let's try a library if standard fails, but regex is faster.
        # This regex looks for a backslash that is NOT followed by a valid escape char.
        # But this is risky.

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON Parse Error: {e}. Attempting repair...")
            # Fallback: Use 'dirtyjson' or simple regex patch if installed?
            # Let's try to just log the bad text for now to see what Gemini did.
            logger.error(f"Bad JSON Content: {clean[:500]}...")  # Print first 500 chars
            raise ValueError(f"AI returned invalid JSON: {e}")
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        raise e


# 5. Endpoints


@app.post("/draft_curriculum")
def draft_curriculum(request: DraftRequest):
    """
    STEP 1: The Blueprint.
    Fast. Selects words, knots, and context. No AI generation.
    """
    if not engine:
        raise HTTPException(500, "Engine not ready")

    try:
        logger.info(f"Drafting: {request.theme}")
        # Call core logic WITHOUT AI
        result = engine.compile_curriculum(request.theme, request.count)

        # Return the structure
        return {
            "worksheet_data": result["worksheet_data"],
            "instruction_text": result["instruction_text"],
        }
    except Exception as e:
        logger.error(f"Draft Error: {e}")
        raise HTTPException(500, str(e))


@app.post("/fill_curriculum")
def fill_curriculum(request: FillRequest):
    """
    STEP 2: The Weave.
    """
    if not engine:
        raise HTTPException(500, "Engine not ready")

    try:
        logger.info("Filling curriculum with AI...")

        rows_json = json.dumps(request.worksheet_data, indent=2)
        full_prompt = (
            request.instruction_text + "\n\n### DATA TO COMPLETE ###\n" + rows_json
        )

        filled_rows = call_gemini(full_prompt)

        if isinstance(filled_rows, list):
            # --- THE TOKENIZATION INJECTION ---
            for row in filled_rows:
                # Tokenize Greek
                greek_text = row.get("target_sentence") or row.get(
                    "Greek Translation / Target Sentence"
                )
                if greek_text:
                    row["target_tokens"] = engine.tokenize_text(greek_text, "el")

                # Tokenize English (Optional)
                eng_text = row.get("source_sentence") or row.get("Source Sentence")
                if eng_text:
                    row["source_tokens"] = engine.tokenize_text(eng_text, "en")
            # ----------------------------------

            return {"worksheet_data": filled_rows}
        else:
            raise ValueError("AI returned invalid structure")

    except Exception as e:
        logger.error(f"Fill Error: {e}")
        raise HTTPException(500, str(e))
