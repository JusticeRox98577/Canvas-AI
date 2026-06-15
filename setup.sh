#!/usr/bin/env bash
# Canvas-AI one-shot setup for macOS.
# Usage:  bash setup.sh
set -euo pipefail

echo "== Canvas-AI setup (macOS) =="

# 1. Python venv
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Install Canvas-AI + browser support
echo "Installing Python dependencies..."
python -m pip install --upgrade pip >/dev/null
pip install -e ".[browser]"
python -m playwright install chromium

# 3. Ollama (local model runtime)
if ! command -v ollama >/dev/null 2>&1; then
  echo "Installing Ollama..."
  if command -v brew >/dev/null 2>&1; then
    brew install ollama
  else
    echo "Homebrew not found. Install Ollama from https://ollama.com/download then re-run." >&2
    exit 1
  fi
fi

# 4. Make sure the Ollama server is running, then pull the model
if ! curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama server..."
  if command -v brew >/dev/null 2>&1; then
    brew services start ollama >/dev/null 2>&1 || (ollama serve >/dev/null 2>&1 &)
  else
    (ollama serve >/dev/null 2>&1 &)
  fi
  # give it a moment to come up
  for _ in $(seq 1 15); do
    curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && break
    sleep 1
  done
fi

echo "Pulling llama3.1:8b (one-time download, ~5GB)..."
ollama pull llama3.1:8b

# 5. .env
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env -- set CANVAS_BASE_URL to your school's Canvas URL."
fi

cat <<'EOF'

Done. Next (in a new terminal, from this folder):
  1. source .venv/bin/activate
  2. nano .env            # set CANVAS_BASE_URL (https://yourschool.instructure.com)
  3. canvas-ai login      # sign in via Microsoft 365 in the browser window
  4. canvas-ai courses    # confirm it works
EOF
