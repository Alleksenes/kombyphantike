from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from src.kombyphantike import KombyphantikeEngine
from src.audio import generate_audio
from src.models import ConstellationGraph
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

class CurriculumRequest(BaseModel):
    theme: str
    sentence_count: int = 5

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


class SpeakRequest(BaseModel):
    text: str


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
    except json.JSONDecodeError as e:
        logger.warning(f"JSON Parse Error: {e}. Attempting emergency repair...")
        # If it ends abruptly, try adding the closing brackets
        if not clean.endswith("]"):
            clean += "]"
        if not clean.endswith("}") and not clean.endswith("]"):
             clean += "}]"
             
        try:
            return json.loads(clean)
        except:
            logger.error("Emergency repair failed.")
            raise ValueError(f"AI returned unrecoverable JSON: {e}")


# 5. Endpoints

@app.post("/draft_curriculum", response_model=ConstellationGraph) # Update response model to Graph
async def draft_curriculum(request: CurriculumRequest): # Use the Pydantic model
    # Access via request.theme
    """
    STEP 1: The Blueprint.
    Fast. Selects words, knots, and context. No AI generation.
    Returns a ConstellationGraph.
    """
    if not engine:
        raise HTTPException(500, "Engine not ready")

    try:
        logger.info(f"Drafting: {request.theme}")
        # Call core logic WITHOUT AI
        # engine.compile_curriculum now returns ConstellationGraph
        graph = engine.compile_curriculum(request.theme, request.sentence_count)

        # Return the structure directly
        return graph
    except Exception as e:
        logger.error(f"Draft Error: {e}")
        raise HTTPException(500, str(e))

@app.post("/fill_curriculum")
def fill_curriculum(request: FillRequest):
    """
    STEP 2: The Weave.
    Prunes the data to prevent Gemini from choking on Kelly metadata.
    """
    if not engine:
        raise HTTPException(500, "Engine not ready")

    try:
        logger.info(f"Preparing to fill {len(request.worksheet_data)} nodes with AI...")

        # --- THE PRUNER: Remove the Slop ---
        # We only send what the AI needs to write the sentences.
        lean_data = []
        for row in request.worksheet_data:
            # Check for various lemma keys (lemma_text, lemma, etc)
            lemma = row.get("lemma_text") or row.get("lemma") or row.get("id")
            
            # Extract only the essentials
            lean_row = {
                "id": row.get("id"),
                "lemma": lemma,
                "knot_rule": row.get("knot_definition") or row.get("knot_rule"),
                "theme": os.environ.get("CURRENT_THEME", "General") # Context
            }
            
            # Flatten ancient_context if it's a dict to save tokens
            actx = row.get("ancient_context")
            if isinstance(actx, dict):
                # JEWEL PRESERVATION: Provide the actual text to inspire the AI
                author = actx.get('author', 'Unknown')
                work = actx.get('work', '')
                greek = actx.get('greek', '')
                translation = actx.get('translation', '')
                lean_row["ancient_context"] = f"{author} ({work}): {greek} - {translation}"
            elif isinstance(actx, str) and actx:
                lean_row["ancient_context"] = actx
            
            lean_data.append(lean_row)

        # Use the LEAN data for the prompt
        rows_json = json.dumps(lean_data, indent=2)
        
        full_prompt = (
            request.instruction_text + 
            "\n\n### DATA TO COMPLETE ###\n" + 
            "Return a JSON array where each object has: id, target_sentence, source_sentence, knot_context.\n" +
            rows_json
        )

        # Call AI
        filled_rows = call_gemini(full_prompt)

        if isinstance(filled_rows, list):
            # --- THE WEAVER: Merge AI results back into the RICH data ---
            # We map by 'id' to ensure we don't lose the Kelly stats in the final response
            rich_map = {str(r['id']): r for r in request.worksheet_data}
            
            final_output = []
            for a_row in filled_rows:
                node_id = str(a_row.get("id"))
                if node_id in rich_map:
                    target_node = rich_map[node_id]
                    
                    # Update the node with AI generation
                    target_node["target_sentence"] = a_row.get("target_sentence")
                    target_node["source_sentence"] = a_row.get("source_sentence")
                    target_node["knot_context"] = a_row.get("knot_context")
                    
                    # Tokenize the new sentence
                    greek_text = target_node["target_sentence"]
                    if greek_text:
                        target_node["target_tokens"] = engine.tokenize_text(greek_text, "el")
                        target_node["target_transliteration"] = engine.transliterate_sentence(greek_text)
                    
                    final_output.append(target_node)

            return {"worksheet_data": final_output}
        else:
            raise ValueError("AI returned invalid JSON structure (not a list)")

    except Exception as e:
        logger.error(f"Fill Error: {e}")
        raise HTTPException(500, str(e))

@app.post("/speak")
async def speak(request: SpeakRequest):
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        # Calls ElevenLabs via src.audio
        # REMOVED 'await' because generate_audio is synchronous
        audio_base64 = generate_audio(request.text)
        
        # Ensure the prefix is correct for the frontend
        if not audio_base64.startswith("data:audio"):
             return {"audio_data": f"data:audio/mp3;base64,{audio_base64}"}
        return {"audio_data": audio_base64}
        
    except Exception as e:
        logger.error(f"Speak Error: {e}")
        raise HTTPException(500, str(e))

@app.get("/relations/{lemma_text}", response_model=Dict[str, List[str]])
def get_relations(lemma_text: str):
    """
    Returns semantic relationships for the given lemma (e.g. synonyms, antonyms).
    """
    if not engine:
        raise HTTPException(500, "Engine not ready")

    try:
        result = engine.db.get_relations(lemma_text)
        return result
    except Exception as e:
        logger.error(f"Relations Error: {e}")
        raise HTTPException(500, str(e))
