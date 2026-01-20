from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.kombyphantike import KombyphantikeEngine
import logging
import os
import json
import google.generativeai as genai

# Initialize Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="Kombyphantike API", version="0.1.0")

# Initialize Engine (Singleton)
try:
    engine = KombyphantikeEngine()
except Exception as e:
    logger.error(f"Failed to initialize engine: {e}")
    # In a real scenario, we might want to crash here,
    # but for resilience we'll keep the app alive and return 500s.
    engine = None

class WorksheetRequest(BaseModel):
    theme: str
    count: int
    complete_with_ai: bool = False

def generate_with_gemini(prompt_text: str):
    """
    Generates content using Google Gemini model.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables.")
        raise HTTPException(status_code=500, detail="Google API Key configuration missing")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-3.0-flash')

        strict_instruction = "\nOutput the result strictly as a JSON list of objects, where each object represents a row in the worksheet."
        full_prompt = prompt_text + strict_instruction

        response = model.generate_content(full_prompt)
        # response.text might raise if the response was blocked, but usually it returns text.
        text_response = response.text

        # Parse JSON
        clean_text = text_response.strip()
        # Remove markdown code blocks if present
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]

        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]

        clean_text = clean_text.strip()

        return json.loads(clean_text)

    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        # We might want to return partial result or fail?
        # User requirement implies we must return the completed worksheet.
        raise HTTPException(status_code=500, detail=f"AI Generation failed: {str(e)}")

@app.post("/generate_worksheet")
def generate_worksheet_endpoint(request: WorksheetRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    try:
        # Call the core logic
        result = engine.compile_curriculum(request.theme, request.count)

        if request.complete_with_ai:
            # Append the data to the prompt so AI knows what to complete
            rows_json = json.dumps(result["worksheet_data"], indent=2)
            prompt = result["instruction_text"] + "\n\n### DATA TO COMPLETE ###\n" + rows_json

            filled_rows = generate_with_gemini(prompt)

            # Merge logic: Assuming AI returns the list of rows
            if isinstance(filled_rows, list):
                result["worksheet_data"] = filled_rows
            else:
                logger.warning("AI response was not a list, returning original data.")
                # Alternatively raise error, but let's be safe and return original.

        # Persist progress (learning)
        engine.save_progress()

        return {
            "worksheet": result["worksheet_data"],
            "instructions": result["instruction_text"]
        }
    except Exception as e:
        logger.error(f"Error generating worksheet: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "engine_ready": engine is not None}
