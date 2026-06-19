@echo off
rem ==== Double-click launcher for Canvas-AI ====
rem Runs from wherever this file lives, so the app finds your .env, voice.txt,
rem and saved login.
cd /d "%~dp0"

set "PYW=.venv\Scripts\pythonw.exe"
set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Canvas-AI isn't set up yet.
  echo In PowerShell, run:  powershell -ExecutionPolicy Bypass -File setup.ps1
  echo.
  pause
  exit /b 1
)

rem pythonw = no console window; fall back to python if it's missing.
if exist "%PYW%" (
  start "" "%PYW%" -m canvas_ai.cli app
) else (
  start "" "%PY%" -m canvas_ai.cli app
)
