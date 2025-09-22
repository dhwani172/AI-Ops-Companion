# --- Ensure project root is importable BEFORE importing core ---
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------- Standard imports ----------------
import json, time
from datetime import datetime
import streamlit as st

from core.runner import run_on_text, DEFAULT_RECIPE

# ---------- Paths ----------
HERE = Path(__file__).parent
ASSETS = HERE / "assets"
CSS_FILE = ASSETS / "style.css"
JS_FILE = ASSETS / "script.js"         # optional
HTML_SNIPPET = ASSETS / "custom.html"  # optional
ROTATOR_ITEMS = ["Summaries", "Action Items", "Brainstorming"]

# ---------- Recipe / Model metadata for the hover dock ----------
RECIPE_INFO = {
    "summary": "Bullet summary of stories/long text\n• 5–8 concise plot or topic beats\n• De-duplicated & wrapped\n• Long text → chunk + merge",
    "action_items": "Extracts actionable tasks\n• Imperative phrasing\n• Owner kept if present\n• Caps ~12 bullets",
    "brainstorm": "Generates creative ideas\n• 6–10 bullets\n• Slightly higher temperature\n• Good for product/feature ideation",
}
MODEL_INFO = {
    "t5-small": "Tiny, CPU-friendly\n• Good for quick tests\n• Short inputs",
    "google/flan-t5-small": "Small instruction-tuned\n• Better for “action_items” & “brainstorm”\n• Still fast on CPU",
    "google/flan-t5-base": "Bigger FLAN-T5\n• Higher quality than small\n• Slower on CPU; fine on GPU",
    "sshleifer/distilbart-cnn-12-6": "Fast summarizer\n• Good quality on paragraphs\n• Default for summary",
}

# ---------- Page config ----------
st.set_page_config(page_title="AI-Ops Companion", layout="wide")

# ---------- Minimal inline fallback (prevents flash) ----------
st.markdown(
    """
    <style>
      html, body, .stApp,
      [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stSidebar"],
      .main, .block-container { background:#000 !important; color:#fff !important; }
      [data-testid="stHeader"]{ background:transparent !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Load full CSS / HTML / JS ----------
def _safe_read(p: Path) -> str:
    try: return p.read_text(encoding="utf-8")
    except Exception: return ""

if CSS_FILE.exists(): st.markdown(f"<style>{_safe_read(CSS_FILE)}</style>", unsafe_allow_html=True)
if HTML_SNIPPET.exists(): st.markdown(_safe_read(HTML_SNIPPET), unsafe_allow_html=True)
if JS_FILE.exists(): st.markdown(f"<script>{_safe_read(JS_FILE)}</script>", unsafe_allow_html=True)

# ---------- Header ----------
st.markdown(
    """
    <h1 class='app-title'>AI-Ops Companion</h1>
    <div class='app-rotator-row'>
      <span class='app-rotator-dot'>•</span>
      <span class='app-rotator-label'></span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(f"<script>window.__aiOpsRecipes = {json.dumps(ROTATOR_ITEMS)}</script>", unsafe_allow_html=True)
st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)

# ---------- TOP-RIGHT HOVER INFO DOCK ----------
dock_html = [
    "<div id='info-dock-root' class='info-dock'>",   # <-- unique id (important)
    "  <div class='info-section'>",
    "    <div class='info-title'>RECIPE</div>",
]
for name, tip in RECIPE_INFO.items():
    safe_tip = tip.replace("'", "&#39;")
    dock_html.append(f"    <button class='info-chip' data-tip='{safe_tip}'>{name}</button>")
dock_html += [
    "  </div>",
    "  <div class='info-section'>",
    "    <div class='info-title'>MODELS</div>",
]
for name, tip in MODEL_INFO.items():
    safe_tip = tip.replace("'", "&#39;")
    dock_html.append(f"    <button class='info-chip' data-tip='{safe_tip}'>{name}</button>")
dock_html.append("</div>")

st.markdown("\n".join(dock_html), unsafe_allow_html=True)

# Pin the dock to <body> after Streamlit renders, so it’s not inside a transformed container
st.markdown(
    """
    <script>
    (function () {
      function pinDock() {
        const el = document.getElementById('info-dock-root');
        if (!el) return;
        if (el.parentNode !== document.body) {
          document.body.appendChild(el);
        }
        // make sure the 'fixed' coords are correct after each rerender
        el.style.position = 'fixed';
        el.style.top = '14px';
        el.style.right = '18px';
        el.style.zIndex = '99999';
      }
      // run now & whenever Streamlit re-renders
      if (document.readyState !== 'loading') pinDock();
      else document.addEventListener('DOMContentLoaded', pinDock, { once:true });
      document.addEventListener('streamlit:rendered', () => requestAnimationFrame(pinDock));
      window.addEventListener('resize', pinDock);
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Run Settings")
    recipe_options = ["summary", "action_items", "brainstorm"]
    try: default_idx = recipe_options.index(DEFAULT_RECIPE)
    except ValueError: default_idx = 0
    recipe = st.selectbox("Recipe", recipe_options, index=default_idx)

    model_options = [
        "t5-small",
        "google/flan-t5-small",
        "sshleifer/distilbart-cnn-12-6",
        "google/flan-t5-base",
    ]
    recommended_model = {
        "summary": "sshleifer/distilbart-cnn-12-6",
        "action_items": "google/flan-t5-small",
        "brainstorm": "google/flan-t5-small",
    }.get(recipe, "t5-small")
    try: model_default_idx = model_options.index(recommended_model)
    except ValueError: model_default_idx = 0
    model_name = st.selectbox("Model", model_options, index=model_default_idx)

    safe_mode = st.checkbox("Safe mode (redact PII + limit length)", value=True)
    max_chars = st.slider("Max output chars", 120, 2000, 600, 40)
    st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)
    persist = st.checkbox("Persist run to events.json", value=False, help="Turn on if you want local audit logs.")

# ---------- Session state ----------
if "input_text" not in st.session_state: st.session_state.input_text = ""

def clear_box():
    st.session_state.input_text = ""
    st.rerun()

# ---------- New Run (glass title row + card feel just with CSS) ----------
st.subheader("New Run")
user_text = st.text_area(
    "Paste text to process",
    key="input_text",
    height=170,
    placeholder="Enter your text...",
    help="This text will be used by the selected recipe and model.",
)

c1, c2, _ = st.columns([1, 1, 5])
with c1: run_clicked = st.button("Run", use_container_width=True)
with c2: st.button("Clear", on_click=clear_box, use_container_width=True)

out = st.empty()

def _normalize_output(payload) -> str:
    if payload is None: return ""
    if isinstance(payload, str): return payload.strip()
    if isinstance(payload, list):
        lines = []
        for item in payload:
            if isinstance(item, str): lines.append(item)
            else:
                try: lines.append(json.dumps(item, ensure_ascii=False))
                except Exception: lines.append(str(item))
        return "\n".join(lines).strip()
    try: return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception: return str(payload)

# ---------- Execute ----------
if run_clicked:
    if not user_text.strip():
        st.warning("Please paste some text.")
    else:
        t0 = time.time()
        with st.spinner("Running model..."):
            event = run_on_text(
                text=user_text.strip(),
                recipe=recipe,
                model_name=model_name.strip(),
                safe_mode=safe_mode,
                max_chars=max_chars,
                persist=persist,
                meta={"source": "dashboard"},
            )
        latency_ms = int((time.time() - t0) * 1000)

        with out.container():
            st.markdown(
                f"<div class='latency-banner'><span class='dot ok'></span> Completed in <strong>{latency_ms} ms</strong></div>",
                unsafe_allow_html=True,
            )
            sg = event.get("safeguards") or {}
            st.markdown(
                "<div class='badge-row'>"
                f"<span class='badge'>Recipe: {event.get('recipe','')}</span>"
                f"<span class='badge'>Model: {event.get('model','')}</span>"
                f"<span class='badge'>Safe mode: {sg.get('safe_mode', True)}</span>"
                f"<span class='badge'>Truncated: {sg.get('truncated', False)}</span>"
                "</div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div class='soft-divider'></div>", unsafe_allow_html=True)

            st.markdown("### Output")
            st.code(_normalize_output(event.get("output")), language="text")

            st.markdown("### Safeguards Report")
            st.json(sg)

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
