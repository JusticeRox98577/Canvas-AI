# Run the native desktop app from source (no build step).
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File windows\run.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "No .venv found. Run setup.ps1 first." -ForegroundColor Yellow
    exit 1
}
& .\.venv\Scripts\Activate.ps1
canvas-ai app
