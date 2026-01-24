from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.kombyphantike import KombyphantikeEngine
import logging
from pathlib import Path
import os
import json
from dotenv import load_dotenv

# --- NEW SDK IMPORT ---
from google import genai
from google.genai import types

# 1. Setup Logging FIRST
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kombyphantike-api")

app = FastAPI(title="Kombyphantike API", version="0.1.0")

# --- CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Define Global Engine
engine = None


@app.on_event("startup")
async def startup_event():
    global engine
    logger.info(">>> STARTUP SEQUENCE INITIATED <<<")

    # 3. BULLETPROOF ENV LOADING
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    env_path = project_root / ".env"

    logger.info(f"--- DEBUG: Looking for .env at: {env_path}")

    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info("--- DEBUG: .env file found and loaded.")
    else:
        logger.error(f"--- DEBUG: .env file NOT found at {env_path}")

    # 4. Check Key
    key_check = os.getenv("GOOGLE_API_KEY")
    if key_check:
        masked_key = key_check[:4] + "..." + key_check[-4:]
        logger.info(f"--- DEBUG: Key loaded successfully: {masked_key}")
    else:
        logger.error("--- DEBUG: Key variable is EMPTY after loading.")

    # 5. Initialize Engine
    try:
        engine = KombyphantikeEngine()
        logger.info("--- ENGINE: Initialized successfully.")
    except Exception as e:
        logger.error(f"--- ENGINE: Initialization failed: {e}")


class WorksheetRequest(BaseModel):
    theme: str
    count: int
    complete_with_ai: bool = False


def generate_with_gemini(prompt_text: str):
    """
    Generates content using the new Google GenAI SDK (v1.0+).
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("CRITICAL: GOOGLE_API_KEY missing.")
        raise HTTPException(
            status_code=500, detail="Google API Key configuration missing"
        )

    try:
        # Initialize the new Client
        client = genai.Client(api_key=api_key)

        strict_instruction = "\nOutput the result strictly as a JSON list of objects, where each object represents a row in the worksheet. Do not include markdown code blocks, just raw JSON."
        full_prompt = prompt_text + strict_instruction

        # Call the new API
        response = client.models.generate_content(
            model="gemini-3-flash-preview",  # The Bleeding Edge
            contents=full_prompt,
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

        # Handle Response
        if not response.text:
            raise ValueError("AI returned empty response text.")

        text_response = response.text

        # Clean JSON markdown
        clean_text = text_response.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]

        return json.loads(clean_text.strip())

    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI Generation failed: {str(e)}")


@app.post("/generate_worksheet")
def generate_worksheet_endpoint(request: WorksheetRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    try:
        logger.info(f"Received request: {request.theme}")

        # Use new method to get clean data structure
        result = engine.compile_curriculum_data(request.theme, request.count)
        worksheet_data = result["worksheet_data"]

        # Generate clean JSON-oriented instructions
        instruction_text = engine.generate_ai_instruction(
            request.theme, request.count, result["words_df"], output_format="json"
        )

        if request.complete_with_ai:
            logger.info("AI Completion requested...")
            rows_json = json.dumps(worksheet_data, indent=2)
            prompt = (
                instruction_text
                + "\n\n### DATA TO COMPLETE ###\n"
                + rows_json
            )

            filled_rows = generate_with_gemini(prompt)

            if isinstance(filled_rows, list):
                worksheet_data = filled_rows
            else:
                logger.warning("AI response was not a list.")

        engine.save_progress()
        return {
            "worksheet": worksheet_data,
            "instructions": instruction_text,
        }
    except Exception as e:
        logger.error(f"Error in endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
