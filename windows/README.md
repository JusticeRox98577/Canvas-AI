# Canvas-AI — native Windows app

A real native window (not a browser tab) around Canvas-AI. It launches the
local Python backend for you and renders the UI with **WebView2**, which is
built into Windows 10/11.

The window has the same tabs as the web app — **Modules, Due Dates,
Discussions, Chat** — plus a **"Do it for me"** button on each assignment that
writes the whole submission and (optionally) submits it. See
[Doing assignments directly](#doing-assignments-directly).

## One-time setup

From the repo root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1   # venv + deps + Ollama + .env
.\.venv\Scripts\Activate.ps1
notepad .env          # set CANVAS_BASE_URL to your school's Canvas URL
canvas-ai login       # sign in once (browser window); session is saved
```

## Run it (from source)

```powershell
powershell -ExecutionPolicy Bypass -File windows\run.ps1
# or:  canvas-ai app
```

## Build a standalone CanvasAI.exe

```powershell
powershell -ExecutionPolicy Bypass -File windows\build.ps1
```

This produces `dist\CanvasAI.exe`. Keep your `.env` and the `.canvas_profile`
folder (created by `canvas-ai login`) next to the exe, or launch the exe from
the project folder, so it can find your settings and saved login.

> Login uses a real browser (Playwright/Chromium) and is intentionally **not**
> bundled into the exe — do it once from the venv with `canvas-ai login`. The
> exe reuses that saved session for fast, cookie-based reads and writes.

## Doing assignments directly

By default, submitting graded work asks you to confirm first. To let the app
write **and submit** an assignment in a single click, set this in `.env`:

```
AUTO_SUBMIT=true
```

With `AUTO_SUBMIT=true`, the **"Do it for me ✨"** button on an assignment
drafts the full submission and posts it immediately. With it off (the default),
the same button drafts the work and then shows you a confirm dialog before
anything is submitted.

This is your own Canvas account and your own coursework — check your school's
academic-integrity policy before submitting AI-written work.
