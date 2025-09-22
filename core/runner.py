# core/runner.py
from __future__ import annotations

import os
import re
import json
import time
import textwrap
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from pathlib import Path

# ---------- PyTorch + HF ----------
import torch

# keep CPU friendly threads
torch.set_num_threads(os.cpu_count() or 4)
torch.set_num_interop_threads(1)

from transformers import (
    pipeline,
    AutoTokenizer,
    Pipeline,
)

# ---------- Safeguards (user-provided) ----------
from core.safeguards import apply_safeguards


# ===================== Project Defaults =====================
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVENTS = PROJECT_ROOT / "events.json"
SAMPLES = PROJECT_ROOT / "samples"

# Default recipe (UI can override)
DEFAULT_RECIPE = "summary"

# Per-task default models
# Summaries (fast / quality / long)
MODEL_SUM_FAST = "sshleifer/distilbart-cnn-12-6"
MODEL_SUM_QUALITY = "google/pegasus-cnn_dailymail"
MODEL_SUM_LONG = "pszemraj/long-t5-tglobal-base-16384-book-summary"

# Action items / Brainstorm (instruction-following; fast / quality)
MODEL_TXT2TXT_FAST = "google/flan-t5-small"
MODEL_TXT2TXT_QUALITY = "google/flan-t5-base"

# For backward compatibility with callers that pass a model_name:
# if none is provided for a recipe, we’ll choose from these defaults.
DEFAULT_MODEL = MODEL_SUM_FAST

# Caches
_PIPELINE_CACHE: Dict[Tuple[str, str], Pipeline] = {}
_TOKENIZER_CACHE: Dict[str, AutoTokenizer] = {}

# ===================== Prompt Recipes =====================
RECIPES: Dict[str, str] = {
    "summary": (
        "Summarize the following STORY as clear bullet points. "
        "Focus on plot beats, key events, and changes to the main character. "
        "Return 5–8 concise bullet points:\n"
    ),
    "action_items": (
        "From the following text, extract ACTION ITEMS as bullet points. "
        "Each bullet must start with an imperative verb and include owner if present and an optional due hint. "
        "Do NOT invent owners or dates. Return 5–10 bullets if available:\n"
    ),
    "brainstorm": (
        "Brainstorm creative IDEAS based on the following text. "
        "Return 6–10 short, non-redundant bullet points. "
        "Make them concrete, varied, and useful; avoid fluff:\n"
    ),
}

# ===================== Utilities =====================

def _clean_text(s: str) -> str:
    s = s.replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def _get_tokenizer(model_name: str) -> AutoTokenizer:
    if model_name not in _TOKENIZER_CACHE:
        _TOKENIZER_CACHE[model_name] = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    return _TOKENIZER_CACHE[model_name]

def _load_pipeline(task: str, model_name: str) -> Pipeline:
    """
    Load & cache a transformers pipeline on CPU (-1).
    task: "summarization" or "text2text-generation"
    """
    key = (task, model_name)
    if key not in _PIPELINE_CACHE:
        print(f"[info] Loading pipeline: task={task} model={model_name}")
        device = -1  # CPU
        _PIPELINE_CACHE[key] = pipeline(task, model=model_name, device=device)
        # tiny warmup (non-fatal if it fails)
        try:
            _PIPELINE_CACHE[key]("Warm-up input.", max_length=16, do_sample=False)
        except Exception:
            pass
    return _PIPELINE_CACHE[key]

def _resolve_task(recipe: str) -> str:
    # Summary uses summarization; the others prefer instruction text2text
    return "summarization" if recipe == "summary" else "text2text-generation"

def _choose_model(recipe: str, requested: Optional[str], text_len_chars: int) -> str:
    """
    Heuristics per recipe. If the user chose a model in the UI, honor it.
    """
    if requested and requested.strip():
        return requested.strip()

    if recipe == "summary":
        if text_len_chars > 4000:
            return MODEL_SUM_LONG
        return MODEL_SUM_FAST
    elif recipe == "action_items":
        # instruction-following small model is usually enough
        return MODEL_TXT2TXT_FAST
    elif recipe == "brainstorm":
        return MODEL_TXT2TXT_FAST
    return MODEL_SUM_FAST

def _gen_kwargs_for_recipe(recipe: str) -> Dict[str, Any]:
    # Tuned for bullet-y outputs and low repetition
    if recipe == "summary":
        return dict(
            max_length=160, min_length=60,
            do_sample=False,
            num_beams=4,
            no_repeat_ngram_size=3,
            length_penalty=1.0,
            early_stopping=True,
        )
    if recipe == "action_items":
        return dict(
            max_length=180, min_length=60,
            do_sample=False,
            num_beams=4,
            no_repeat_ngram_size=3,
            length_penalty=1.0,
            early_stopping=True,
        )
    if recipe == "brainstorm":
        return dict(
            max_length=200, min_length=70,
            do_sample=True,
            top_p=0.92, top_k=50, temperature=0.95,
            no_repeat_ngram_size=3,
            num_return_sequences=1,
        )
    # fallback
    return dict(max_length=160, min_length=60, do_sample=False, num_beams=4, no_repeat_ngram_size=3)

# ---------- Chunking ----------

@dataclass
class ChunkPlan:
    max_src_tokens: int
    overlap_tokens: int = 48   # small overlap to not miss boundary facts

def _token_chunks(text: str, tok: AutoTokenizer, plan: ChunkPlan) -> List[List[int]]:
    """
    Split text into token chunks under max_src_tokens with overlap.
    Returns list of input_id lists.
    """
    ids = tok.encode(text, add_special_tokens=True)
    if len(ids) <= plan.max_src_tokens:
        return [ids]

    chunks: List[List[int]] = []
    i = 0
    while i < len(ids):
        end = min(i + plan.max_src_tokens, len(ids))
        chunk = ids[i:end]
        chunks.append(chunk)
        if end == len(ids):
            break
        i = end - plan.overlap_tokens  # step with overlap
        i = max(0, i)
    return chunks

def _decode(ids: List[int], tok: AutoTokenizer) -> str:
    return tok.decode(ids, skip_special_tokens=True)

# ---------- Output formatting ----------

_BULLET_RE = re.compile(r"^\s*[-•–]\s*")

def _as_bullets(s: str) -> List[str]:
    """
    Convert a block into bullet lines:
    - split on newlines or sentence ends
    - normalize to "- " prefix
    - drop empties and heavy duplicates
    """
    # Prefer line-based if model already returned bullets
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    if len(lines) >= 2:
        pts = []
        for ln in lines:
            ln = _BULLET_RE.sub("", ln).strip()
            if ln:
                pts.append(f"- {ln}")
        return _dedupe(pts)

    # Otherwise split by sentences
    sentences = re.split(r"(?<=[.!?])\s+", s.strip())
    pts = []
    for sent in sentences:
        t = sent.strip(" \n-•–")
        if len(t) > 0:
            pts.append(f"- {t}")
    return _dedupe(pts)

def _dedupe(lines: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for ln in lines:
        key = re.sub(r"\W+", " ", ln.lower()).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(ln)
    return out

def _limit_bullets(bullets: List[str], min_n=5, max_n=8) -> List[str]:
    if len(bullets) < min_n:
        return bullets
    return bullets[:max_n]

def _postprocess_to_bullets(recipe: str, text: str) -> str:
    bullets = _as_bullets(text)

    # Recipe-specific trimming
    if recipe == "summary":
        bullets = _limit_bullets(bullets, 5, 8)
    elif recipe == "action_items":
        # Prefer 5–10; hard cap 12
        if len(bullets) > 12:
            bullets = bullets[:12]
    elif recipe == "brainstorm":
        # Prefer 6–10; hard cap 12
        if len(bullets) > 12:
            bullets = bullets[:12]

    s = "\n".join(bullets)
    # gentle wrap for wide cards in Streamlit (keep bullets intact)
    wrapped: List[str] = []
    for line in s.splitlines():
        if line.startswith("- "):
            body = line[2:]
            wrapped_body = textwrap.fill(body, width=120, subsequent_indent="  ")
            wrapped.append(f"- {wrapped_body}")
        else:
            wrapped.append(textwrap.fill(line, width=120))
    return "\n".join(wrapped).strip()

# ---------- Safeguards adapter (robust to different signatures) ----------

def _fallback_redact(text: str, output: str, *, max_chars: int, safe_mode: bool) -> Dict[str, Any]:
    import re as _re
    meta = {"engine": "fallback", "safe_mode": bool(safe_mode), "max_chars": max_chars}
    if not safe_mode:
        return {"redacted_output": output, **meta, "truncated": False, "redactions": {}}

    redactions = {}
    red = output

    email_re = _re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    emails = email_re.findall(red)
    if emails:
        redactions["emails"] = sorted(set(emails))
        red = email_re.sub("[REDACTED_EMAIL]", red)

    phone_re = _re.compile(r"(?:\+?\d[\d\-\s]{7,}\d)")
    phones = phone_re.findall(red)
    if phones:
        redactions["phones"] = sorted(set(phones))
        red = phone_re.sub("[REDACTED_PHONE]", red)

    truncated = False
    if max_chars and len(red) > max_chars:
        red = red[:max_chars].rstrip() + "…"
        truncated = True

    return {"redacted_output": red, **meta, "truncated": truncated, "redactions": redactions}

def _apply_safeguards_adapt(text: str, output: str, *, max_chars: int, safe_mode: bool) -> Dict[str, Any]:
    attempts = [
        lambda: apply_safeguards(text, output, max_chars=max_chars, safe_mode=safe_mode),
        lambda: apply_safeguards(output, max_chars=max_chars, safe_mode=safe_mode),
        lambda: apply_safeguards(text, max_chars=max_chars, safe_mode=safe_mode),
        lambda: apply_safeguards({"input": text, "output": output, "max_chars": max_chars, "safe_mode": safe_mode}),
    ]
    for fn in attempts:
        try:
            res = fn()
            if isinstance(res, tuple) and len(res) == 2 and isinstance(res[0], str) and isinstance(res[1], dict):
                red, meta = res
                meta = {**meta}
                meta.setdefault("safe_mode", safe_mode)
                meta.setdefault("max_chars", max_chars)
                meta.setdefault("engine", "user")
                meta.setdefault("truncated", meta.get("truncated", False))
                return {"redacted_output": red, **meta}
            if isinstance(res, str):
                return {
                    "redacted_output": res,
                    "safe_mode": safe_mode,
                    "max_chars": max_chars,
                    "engine": "user",
                    "truncated": len(res) >= max_chars if (safe_mode and max_chars) else False,
                    "redactions": {},
                }
            if isinstance(res, dict):
                red = res.get("redacted_output")
                base = {
                    "safe_mode": res.get("safe_mode", safe_mode),
                    "max_chars": res.get("max_chars", max_chars),
                    "engine": res.get("engine", "user"),
                    "truncated": res.get("truncated", False),
                    "redactions": res.get("redactions", {}),
                }
                if isinstance(red, str):
                    return {"redacted_output": red, **{**res, **base}}
                fb = _fallback_redact(text, output, max_chars=max_chars, safe_mode=safe_mode)
                merged = {**fb, **res}
                merged.setdefault("engine", "user+fallback")
                return merged
        except TypeError:
            continue
        except Exception:
            break
    return _fallback_redact(text, output, max_chars=max_chars, safe_mode=safe_mode)

# ===================== Generation Core =====================

def _generate_single(
    task: str,
    model_name: str,
    prompt: str,
    gen_kwargs: Dict[str, Any],
) -> str:
    pl = _load_pipeline(task, model_name)
    out = pl(prompt, **gen_kwargs)
    if isinstance(out, list) and len(out) > 0:
        # pipeline key can be "summary_text" (summarization) or "generated_text" (t5/flan)
        return out[0].get("summary_text") or out[0].get("generated_text") or ""
    return str(out)

def _map_reduce_generate(
    task: str,
    model_name: str,
    full_text: str,
    recipe: str,
    gen_kwargs: Dict[str, Any],
) -> str:
    """
    Tokenizer-aware chunking + local reduce (bullet merge).
    Suitable for all three recipes.
    """
    tok = _get_tokenizer(model_name)
    max_src = min(tok.model_max_length or 1024, 2048)  # safety cap
    plan = ChunkPlan(max_src_tokens=max_src - 64, overlap_tokens=48)  # leave space for specials

    chunks_ids = _token_chunks(full_text, tok, plan)
    parts: List[str] = []

    instr = RECIPES.get(recipe, "")  # instruction prefix

    for ids in chunks_ids:
        piece = _decode(ids, tok)
        prompt = f"{instr}\n{piece}"
        piece_out = _generate_single(task, model_name, prompt, gen_kwargs)
        parts.append(piece_out.strip())

    # Local reduce: merge & re-bullet
    merged = "\n".join(parts)
    return _postprocess_to_bullets(recipe, merged)

# ===================== Public API =====================

def run_on_text(
    text: str,
    recipe: str = DEFAULT_RECIPE,
    model_name: str = DEFAULT_MODEL,   # UI can override
    safe_mode: bool = True,
    max_chars: int = 600,
    persist: bool = True,
    meta: dict | None = None,
):
    t0 = time.time()

    cleaned = _clean_text(text)
    task = _resolve_task(recipe)

    # choose effective model
    eff_model = _choose_model(recipe, model_name, len(cleaned))

    gen_kwargs = _gen_kwargs_for_recipe(recipe)
    instr = RECIPES.get(recipe, "")
    prompt = f"{instr}\n{cleaned}"

    # Decide chunk vs single pass by tokenizer limits
    try:
        tok = _get_tokenizer(eff_model)
        max_src = min(tok.model_max_length or 1024, 2048)
        input_ids = tok.encode(cleaned, add_special_tokens=True)
        needs_chunks = len(input_ids) > (max_src - 64)
    except Exception:
        needs_chunks = len(cleaned) > 2800  # rough fallback

    if needs_chunks:
        raw = _map_reduce_generate(task, eff_model, cleaned, recipe, gen_kwargs)
    else:
        raw_single = _generate_single(task, eff_model, prompt, gen_kwargs)
        raw = _postprocess_to_bullets(recipe, raw_single)

    # Safeguards
    sg = _apply_safeguards_adapt(cleaned, raw, max_chars=max_chars, safe_mode=safe_mode)

    latency = int((time.time() - t0) * 1000)
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "recipe": recipe,
        "model": eff_model,
        "input": cleaned[:2000],
        "output": sg.get("redacted_output", raw),
        "latency_ms": latency,
        "safeguards": sg,
        "meta": meta or {},
    }

    if persist:
        _persist_event(event)

    return event

# ---------- Persistence ----------
def _persist_event(event: dict):
    try:
        if EVENTS.exists():
            all_events = json.loads(EVENTS.read_text(encoding="utf-8"))
        else:
            all_events = []
    except Exception:
        all_events = []
    all_events.append(event)
    EVENTS.write_text(json.dumps(all_events, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- CLI ----------
if __name__ == "__main__":
    sample_path = SAMPLES / "meeting.txt"
    if not sample_path.exists():
        print(f"[warn] No sample file found at {sample_path}")
        exit(1)
    sample_text = sample_path.read_text(encoding="utf-8")
    for r in ("summary", "action_items", "brainstorm"):
        print(f"\n=== {r.upper()} ===")
        event = run_on_text(sample_text, recipe=r, model_name="")
        print(event["output"])
    print("\n[ok] Wrote results to events.json")
