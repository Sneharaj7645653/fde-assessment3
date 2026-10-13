#!/usr/bin/env bash
# One-command start: creates the virtualenv if needed, installs dependencies, creates .env from the
# template if missing, runs the setup preflight, then starts the mock vendor-risk API and the UI.
set -euo pipefail
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv
fi
.venv/bin/python -m pip install -q -r requirements.txt
[ -f .env ] || { cp .env.example .env; echo "Created .env from .env.example (add a GROQ_API_KEY_1 to enable the AI agents; without it the app runs in deterministic mode)."; }
.venv/bin/python verify_setup.py
exec .venv/bin/python run_local.py
