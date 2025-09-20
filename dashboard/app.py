# --- Ensure project root is importable BEFORE importing core ---
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]   # .../AI-Ops-Companion
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------- Standard imports ----------------
import json
import time
from datetime import datetime

import streamlit as st
from core.runner import run_on_text, DEFAULT_MODEL, DEFAULT_RECIPE

# ---------- Paths ----------
HERE = Path(__file__).parent
ASSETS = HERE / "assets"
CSS_FILE = ASSETS / "style.css"
JS_FILE = ASSETS / "script.js"
HTML_SNIPPET = ASSETS / "custom.html"   # loads the Liquid Ether div + CDNs

# ---------- Page config (must be before any Streamlit output) ----------
st.set_page_config(page_title="AI-Ops Companion", layout="wide")

# ---------- Load CSS / JS / HTML ----------
def _safe_read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""

if CSS_FILE.exists():
    st.markdown(f"<style>{_safe_read(CSS_FILE)}</style>", unsafe_allow_html=True)
if HTML_SNIPPET.exists():
    st.markdown(_safe_read(HTML_SNIPPET), unsafe_allow_html=True)
if JS_FILE.exists():
    st.markdown(f"<script>{_safe_read(JS_FILE)}</script>", unsafe_allow_html=True)

# ---------- Header ----------
st.markdown("<h1 class='app-title'>AI-Ops Companion</h1>", unsafe_allow_html=True)
st.markdown("<p class='app-subtitle'>Local Toolkit • Hugging Face Pipeline + Safeguards</p>", unsafe_allow_html=True)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Run Settings")

    recipe_options = ["summary", "action_items", "brainstorm"]
    try:
        default_idx = recipe_options.index(DEFAULT_RECIPE)
    except ValueError:
        default_idx = 0
    recipe = st.selectbox("Recipe", recipe_options, index=default_idx)

    # Smart defaults per recipe (edit as needed)
    recommended_model = {
        "summary": "t5-small",
        "action_items": "google/flan-t5-small",
        "brainstorm": "google/flan-t5-small",
    }.get(recipe, DEFAULT_MODEL)

    model_name = st.text_input("Model", value=recommended_model, help="e.g., t5-small or google/flan-t5-small")

    safe_mode = st.checkbox("Safe mode (redact PII + limit length)", value=True)
    max_chars = st.slider("Max output chars", 120, 2000, 600, 40)

    st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)
    persist = st.checkbox("Persist run to events.json", value=False, help="Turn on if you want local audit logs.")

# ---------- Session state for textarea ----------
if "input_text" not in st.session_state:
    st.session_state.input_text = ""

def clear_box():
    st.session_state.input_text = ""
    st.rerun()

# ---------- New Run Card ----------
st.markdown("<div class='card'>", unsafe_allow_html=True)
st.subheader("New Run")

user_text = st.text_area(
    "Paste text to process",
    key="input_text",
    height=170,
    placeholder="enter your text..",
    help="This text will be used by the selected recipe and model."
)

c1, c2, _ = st.columns([1, 1, 5])
with c1:
    run_clicked = st.button("Run")
with c2:
    clear_clicked = st.button("Clear", on_click=clear_box)

# Placeholder for progressive UI
output_area = st.empty()

# ---------- Execute ----------
if run_clicked:
    if not user_text.strip():
        st.warning("Please paste some text.")
    else:
        with output_area.container():
            # Lightweight staged progress (kept tiny; remove sleeps for max speed)
            p = st.progress(0, text="Initializing…")
            time.sleep(0.03)
            p.progress(35, text="Preparing prompt…")
            with st.spinner("Generating…"):
                event = run_on_text(
                    text=user_text.strip(),
                    recipe=recipe,
                    model_name=model_name.strip(),
                    safe_mode=safe_mode,
                    max_chars=max_chars,
                    persist=persist,
                    meta={"source": "dashboard"},
                )
                time.sleep(0.05)
                p.progress(85, text="Applying safeguards…")
                time.sleep(0.05)
                p.progress(100, text="Done")

        # Render results
        with output_area.container():
            st.success(f"Completed in {event['latency_ms']} ms")

            # --- Badges (safe dict handling) ---
            sg = event.get("safeguards") or {}
            safe_mode_val = sg.get("safe_mode", True)
            truncated_val = sg.get("truncated", False)

            badges_html = (
                "<div>"
                f"<span class='badge'>Recipe: {event.get('recipe','')}</span>"
                f"<span class='badge'>Model: {event.get('model','')}</span>"
                f"<span class='badge'>Safe mode: {safe_mode_val}</span>"
                f"<span class='badge'>Truncated: {truncated_val}</span>"
                "</div>"
            )
            st.markdown(badges_html, unsafe_allow_html=True)

            # Output card (typewriter via assets/script.js -> typeWriter)
            st.markdown("<div class='output-card'><strong>Output</strong>", unsafe_allow_html=True)
            st.markdown("<div id='gen-output' class='output-text'></div>", unsafe_allow_html=True)
            payload = json.dumps(event["output"])
            st.markdown(f"<script>typeWriter({payload}, 'gen-output', 22);</script>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Safeguards JSON
            st.subheader("Safeguards Report")
            st.json(sg)

            # Download button
            export = {
                "status": "ok",
                "event": event,
                "exported_at_utc": datetime.utcnow().isoformat() + "Z",
            }
            st.download_button(
                label="Download result JSON",
                data=json.dumps(export, ensure_ascii=False, indent=2),
                file_name=f"aiops_result_{int(time.time())}.json",
                mime="application/json",
                use_container_width=True,
            )

st.markdown("</div>", unsafe_allow_html=True)  # close card
