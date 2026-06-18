# Create Desktop + Start Menu shortcuts for Canvas-AI.
# Usage (from the repo root):  powershell -ExecutionPolicy Bypass -File windows\create-shortcut.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
$pyw  = Join-Path $root ".venv\Scripts\pythonw.exe"
$py   = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "No .venv yet. Run setup.ps1 first." -ForegroundColor Yellow
    exit 1
}

$target = if (Test-Path $pyw) { $pyw } else { $py }
$icon = Join-Path $root "windows\CanvasAI.ico"
$iconLoc = if (Test-Path $icon) { "$icon,0" } else { "$target,0" }

function New-CanvasShortcut($path) {
    $ws = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut($path)
    $lnk.TargetPath = $target
    $lnk.Arguments = "-m canvas_ai.cli app"
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation = $iconLoc
    $lnk.Description = "Canvas-AI"
    $lnk.Save()
    Write-Host "Created: $path" -ForegroundColor Green
}

$desktop = [Environment]::GetFolderPath("Desktop")
New-CanvasShortcut (Join-Path $desktop "Canvas-AI.lnk")

$startMenu = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
New-CanvasShortcut (Join-Path $startMenu "Canvas-AI.lnk")

Write-Host ""
Write-Host "Done. Look for 'Canvas-AI' on your Desktop and in the Start Menu." -ForegroundColor Cyan
