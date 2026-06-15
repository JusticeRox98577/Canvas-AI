# Canvas-AI one-shot setup for Windows (PowerShell).
# Usage:  powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"

Write-Host "== Canvas-AI setup (Windows) ==" -ForegroundColor Cyan

# 1. Python venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

# 2. Install Canvas-AI + browser support
Write-Host "Installing Python dependencies..."
python -m pip install --upgrade pip | Out-Null
pip install -e ".[browser,web]"
python -m playwright install chromium

# 3. Ollama (local model runtime)
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Ollama..."
    try {
        winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    } catch {
        Write-Host "winget failed. Install Ollama manually from https://ollama.com/download then re-run." -ForegroundColor Yellow
        exit 1
    }
}

# 4. Pull the model (8B fits your 3080's 10GB VRAM with headroom)
Write-Host "Pulling llama3.1:8b (one-time download, ~5GB)..."
ollama pull llama3.1:8b

# 5. .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env -- set CANVAS_BASE_URL to your school's Canvas URL." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Next (in a NEW terminal, from this folder):" -ForegroundColor Green
Write-Host "  1. .\.venv\Scripts\Activate.ps1   (activate the environment)"
Write-Host "  2. notepad .env                    -> set CANVAS_BASE_URL (https://yourschool.instructure.com)"
Write-Host "  3. canvas-ai login                 (sign in via Microsoft 365 in the browser window)"
Write-Host "  4. canvas-ai web                   (open the GUI)"
