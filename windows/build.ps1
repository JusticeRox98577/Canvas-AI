# Build the standalone Windows app: dist\CanvasAI.exe
# One command, from the repo root:
#   powershell -ExecutionPolicy Bypass -File windows\build.ps1
$ErrorActionPreference = "Stop"

Write-Host "== Building standalone CanvasAI.exe ==" -ForegroundColor Cyan

# Need a venv with the app installed.
if (-not (Test-Path ".venv")) {
    Write-Host "No .venv found. Run setup.ps1 first." -ForegroundColor Yellow
    exit 1
}
& .\.venv\Scripts\Activate.ps1

Write-Host "Installing build + desktop + browser dependencies..."
pip install -e ".[web,desktop,browser,build]" | Out-Null

# Install Chromium into a CLEAN, dedicated folder so the bundle only contains
# one browser (otherwise old Chromium revisions / Firefox / WebKit in the
# global cache bloat the exe, e.g. 337MB vs 677MB).
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) "build\pw-browsers"
if (Test-Path $env:PLAYWRIGHT_BROWSERS_PATH) { Remove-Item $env:PLAYWRIGHT_BROWSERS_PATH -Recurse -Force }
Write-Host "Installing Chromium into a clean folder (lean bundle)..."
python -m playwright install chromium

Write-Host "Running PyInstaller (this takes a few minutes and the exe is large)..."
pyinstaller --noconfirm --clean windows\CanvasAI.spec

Write-Host ""
if (Test-Path "dist\CanvasAI.exe") {
    $size = [math]::Round((Get-Item "dist\CanvasAI.exe").Length / 1MB, 0)
    Write-Host "Done -> dist\CanvasAI.exe  (~$size MB)" -ForegroundColor Green
    Write-Host "It's fully standalone: double-click it on any Windows PC (no Python needed)."
    Write-Host "First run opens a sign-in window; after that it remembers you."
} else {
    Write-Host "Build finished but dist\CanvasAI.exe was not found. Check the output above." -ForegroundColor Yellow
}
