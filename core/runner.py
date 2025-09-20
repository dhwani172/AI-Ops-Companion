import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from transformers import pipeline
from .prompts import apply_recipe
from .safeguards import apply_safeguards, report_dict
import torch
torch.set_num_threads(1)   # or 2–4 for multi-core machines

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR  = PROJECT_ROOT / "samples"
EVENTS_PATH  = PROJECT_ROOT / "events.json"

# Defaults
DEFAULT_SAMPLE = SAMPLES_DIR / "meeting.txt"
DEFAULT_RECIPE = "summary"
DEFAULT_MODEL = "sshleifer/distilbart-cnn-12-6"


# Cache the pipeline so the API is fast across requests
_PIPELINE_CACHE: Dict[str, Any] = {}

def _get_pipeline(model_name: str):
    if model_name not in _PIPELINE_CACHE:
        _PIPELINE_CACHE[model_name] = pipeline("text2text-generation", model=model_name)
    return _PIPELINE_CACHE[model_name]

def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Input text not found at: {path}")
    return path.read_text(encoding="utf-8").strip()

def _load_events() -> List[Dict[str, Any]]:
    if EVENTS_PATH.exists():
        try:
            return json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            backup = EVENTS_PATH.with_suffix(".bak.json")
            EVENTS_PATH.rename(backup)
            print(f"[warn] Corrupted events.json → backed up to {backup.name}")
    return []

def _save_events(events: List[Dict[str, Any]]):
    EVENTS_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

def run_on_text(
    *,
    text: str,
    recipe: str = DEFAULT_RECIPE,
    model_name: str = DEFAULT_MODEL,
    safe_mode: bool = True,
    max_chars: int = 600,
    persist: bool = True,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Core pipeline runner used by CLI and API.
    """
    nlp = _get_pipeline(model_name)
    prompt = apply_recipe(recipe, text)

    t0 = time.perf_counter()
    generation = nlp(prompt, max_new_tokens=160, do_sample=False)[0]["generated_text"].strip()
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # Safeguards on OUTPUT (and we scan INPUT for flags inside report)
    safe_output, report = apply_safeguards(generation, safe_mode=safe_mode, max_chars=max_chars)

    event: Dict[str, Any] = {
        "timestamp_utc": datetime.utcnow().isoformat() + "Z",
        "model": model_name,
        "recipe": recipe,
        "input_chars": len(text),
        "output": safe_output,
        "latency_ms": latency_ms,
        "safeguards": report_dict(report),
    }
    if meta:
        event["meta"] = meta

    if persist:
        events = _load_events()
        events.append(event)
        _save_events(events)

    return event

def main(input_path: Path = DEFAULT_SAMPLE, recipe: str = DEFAULT_RECIPE, model_name: str = DEFAULT_MODEL):
    print(f"[info] Loading model: {model_name}")
    raw_text = _read_text(input_path)
    print(f"[info] Running recipe='{recipe}' on {input_path.name}...")

    event = run_on_text(
        text=raw_text,
        recipe=recipe,
        model_name=model_name,
        safe_mode=True,      # default to ON for CLI
        max_chars=600,
        persist=True,
        meta={"input_file": str(input_path.relative_to(PROJECT_ROOT))}
    )

    print(f"[ok] Wrote result to events.json (latency: {event['latency_ms']} ms)")
    print("\n--- Output preview ---")
    print(event["output"])
    print("----------------------")

if __name__ == "__main__":
    # Minimal CLI arg support (optional)
    import sys
    recipe = DEFAULT_RECIPE
    input_path = DEFAULT_SAMPLE
    model_name = DEFAULT_MODEL
    if len(sys.argv) >= 2:
        recipe = sys.argv[1]
    if len(sys.argv) >= 3:
        input_path = Path(sys.argv[2])
    if len(sys.argv) >= 4:
        model_name = sys.argv[3]
    main(input_path=input_path, recipe=recipe, model_name=model_name)
