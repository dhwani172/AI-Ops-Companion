# AI-Ops Companion (Local Toolkit)
AI-Ops Companion is a lightweight local toolkit that helps you experiment with AI pipelines for operations and productivity.
It combines a Hugging Face–powered text model, custom safeguards, a FastAPI service, and a Streamlit dashboard — giving you an end-to-end playground for AI-assisted workflows.

 Features

 Prompt recipes (summary, action items, brainstorm)

 Safeguards for PII redaction + output length limiting

 FastAPI service (/health, /run) for programmatic use

 Streamlit dashboard with a modern UI, live progress, and exportable results

 Configurable recipes (.md + .yaml) and educational docs

Built with: Python · Transformers · Torch · FastAPI · Streamlit
A tiny end-to-end toolkit:
- **Core pipeline** (Hugging Face model + prompt recipes)
- **Safeguards** (PII redaction + length caps)
- **API** (FastAPI `/health`, `/run`)
- **Dashboard** (Streamlit UI)
- **Docs** (prompt library, tool selector, AI mental models, tradeoffs)

## Install & Run (3 commands)
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
