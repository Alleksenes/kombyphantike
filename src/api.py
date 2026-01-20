from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.kombyphantike import KombyphantikeEngine
import logging

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

@app.post("/generate_worksheet")
def generate_worksheet_endpoint(request: WorksheetRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    try:
        # Call the core logic
        result = engine.compile_curriculum(request.theme, request.count)

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
