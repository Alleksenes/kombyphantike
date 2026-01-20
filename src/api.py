from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.kombyphantike import KombyphantikeEngine
import logging
import google.generativeai as genai
import os
import json
import re

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

def generate_with_gemini(prompt_text: str, worksheet_skeleton: list):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")

    genai.configure(api_key=api_key)

    # Using 1.5-flash as the standard fast model
    model = genai.GenerativeModel('gemini-1.5-flash')

    # Serialize the skeleton to JSON
    skeleton_json = json.dumps(worksheet_skeleton, ensure_ascii=False, indent=2)

    final_prompt = (
        f"{prompt_text}\n\n"
        f"### THE ATTACHED WORKSHEET SKELETON ###\n"
        f"Here is the JSON structure you must complete. Fill in the 'Source Sentence' and 'Greek Translation' fields according to the rules.\n"
        f"```json\n{skeleton_json}\n```\n\n"
        f"Output the result strictly as a JSON list of objects, where each object represents a completed row from the skeleton above."
    )

    try:
        response = model.generate_content(final_prompt)
        text = response.text

        # Clean markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[0] # Simple split if no language tag

        return json.loads(text)
    except Exception as e:
        logger.error(f"Gemini generation error: {e}")
        # We might want to return the skeleton if AI fails, but let's raise for now to alert the client
        raise HTTPException(status_code=502, detail=f"AI Generation failed: {e}")

@app.post("/generate_worksheet")
def generate_worksheet_endpoint(request: WorksheetRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    try:
        # Call the core logic
        result = engine.compile_curriculum(request.theme, request.count)

        worksheet_data = result["worksheet_data"]

        if request.complete_with_ai:
            instruction_text = result["instruction_text"]
            logger.info("Calling Gemini for completion...")

            # Pass both instructions and the data skeleton
            ai_data = generate_with_gemini(instruction_text, worksheet_data)

            if isinstance(ai_data, list):
                # Basic validation: check if it looks like our rows
                # Ideally, we should merge carefully to preserve Knot IDs if AI dropped them
                # For now, we trust the AI returned the full list as requested
                worksheet_data = ai_data
            else:
                 logger.warning("AI response was not a list, returning skeleton.")

        # Persist progress (learning)
        engine.save_progress()

        return {
            "worksheet": worksheet_data,
            "instructions": result["instruction_text"]
        }
    except Exception as e:
        logger.error(f"Error generating worksheet: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok", "engine_ready": engine is not None}
