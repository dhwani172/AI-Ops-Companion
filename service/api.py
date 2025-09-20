from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
from datetime import datetime

from core.runner import run_on_text, DEFAULT_RECIPE, DEFAULT_MODEL

app = FastAPI(title="AI Ops Companion API", version="0.1.0")

class RunRequest(BaseModel):
    text: str = Field(..., description="Input text to process")
    recipe: str = Field(DEFAULT_RECIPE, description="Which recipe to apply")
    model_name: str = Field(DEFAULT_MODEL, description="HF model")
    safe_mode: bool = Field(True, description="If true, redact PII & limit output")
    max_chars: int = Field(600, ge=50, le=4000, description="Max output length in safe mode")
    persist: bool = Field(True, description="Append event to events.json")

class RunResponse(BaseModel):
    status: str
    event: Dict[str, Any]

@app.get("/health")
def health():
    return {
        "status": "ok",
        "time_utc": datetime.utcnow().isoformat() + "Z",
        "default_model": DEFAULT_MODEL,
        "default_recipe": DEFAULT_RECIPE,
    }

@app.post("/run", response_model=RunResponse)
def run(req: RunRequest):
    try:
        event = run_on_text(
            text=req.text,
            recipe=req.recipe,
            model_name=req.model_name,
            safe_mode=req.safe_mode,
            max_chars=req.max_chars,
            persist=req.persist,
            meta={"source": "api"},
        )
        return {"status": "ok", "event": event}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
