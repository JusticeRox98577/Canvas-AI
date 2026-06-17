# Build the standalone Windows app: dist\CanvasAI.exe
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File windows\build.ps1
$ErrorActionPreference = "Stop"

Write-Host "== Building Canvas-AI for Windows ==" -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "No .venv found. Run setup.ps1 first." -ForegroundColor Yellow
    exit 1
}
& .\.venv\Scripts\Activate.ps1

Write-Host "Installing build + desktop dependencies..."
pip install -e ".[web,desktop,build]" | Out-Null

Write-Host "Running PyInstaller..."
pyinstaller --noconfirm windows\CanvasAI.spec

Write-Host ""
Write-Host "Done. Your app is at:  dist\CanvasAI.exe" -ForegroundColor Green
Write-Host "Copy your .env (and .canvas_profile) next to the exe, or run it from this folder."
