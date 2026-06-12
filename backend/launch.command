#!/bin/bash
# Double-click this file (Resume Tailor Pro/backend/launch.command) to start the backend.
# First run sets up a virtual env and installs dependencies (one-time, ~1-2 min).
cd "$(dirname "$0")" || exit 1

echo "==> Resume Tailor Pro backend"

if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "==> Created .env from template. Open it and paste your API key(s):"
    echo "    $(pwd)/.env"
    echo "    (At minimum set GEMINI_API_KEY — it's free, no card.)"
  fi
fi

if [ ! -d ".venv" ]; then
  echo "==> Creating virtual environment (one-time)..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing/updating dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo ""
echo "==> Server starting at http://127.0.0.1:8000"
echo "    Leave this window open while you use the extension. Press Ctrl+C to stop."
echo ""
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
