# Canvas-AI one-shot setup for Windows (PowerShell).
# Runs entirely on your Claude Pro/Max SUBSCRIPTION (no Ollama, no API credits).
# Usage:  powershell -ExecutionPolicy Bypass -File setup.ps1
$ErrorActionPreference = "Stop"

Write-Host "== Canvas-AI setup (Windows, Claude subscription) ==" -ForegroundColor Cyan

# 1. Python venv
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

# 2. Install Canvas-AI + browser support + native desktop window
Write-Host "Installing Python dependencies..."
python -m pip install --upgrade pip | Out-Null
pip install -e ".[browser,web,desktop]"
python -m playwright install chromium

# 3. Claude Code CLI (this is what links your Claude CHAT subscription)
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Claude Code..."
    try {
        Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    } catch {
        Write-Host "Auto-install failed. Install Claude Code manually, then re-run:" -ForegroundColor Yellow
        Write-Host "  npm install -g @anthropic-ai/claude-code   (needs Node.js)" -ForegroundColor Yellow
    }
}

# 4. .env -- default to the Claude subscription for chat AND drafting
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env -- set CANVAS_BASE_URL to your school's Canvas URL." -ForegroundColor Yellow
}
(Get-Content ".env") `
    -replace '^LLM_PROVIDER=.*',  'LLM_PROVIDER=claude_code' `
    -replace '^DRAFT_PROVIDER=.*', 'DRAFT_PROVIDER=claude_code' |
    Set-Content ".env"

Write-Host ""
Write-Host "Done. Next (in a NEW terminal, from this folder):" -ForegroundColor Green
Write-Host "  1. .\.venv\Scripts\Activate.ps1   (activate the environment)"
Write-Host "  2. claude                          (log in ONCE -> choose Subscription / Pro-Max)"
Write-Host "  3. notepad .env                    -> set CANVAS_BASE_URL (https://yourschool.instructure.com)"
Write-Host "  4. canvas-ai login                 (sign in to Canvas in the browser window)"
Write-Host "  5. canvas-ai app                   (open the native Windows app)"
