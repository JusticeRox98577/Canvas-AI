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

## Launch it (no typing)

`setup.ps1` creates a **Canvas-AI** icon on your Desktop and in the Start Menu —
just double-click it. To (re)create those shortcuts anytime:

```powershell
powershell -ExecutionPolicy Bypass -File windows\create-shortcut.ps1
```

You can also double-click **`CanvasAI.bat`** in the project folder, or pin the
Desktop icon to your taskbar for one-click access.

## Run it from a terminal

```powershell
canvas-ai app
# or:  powershell -ExecutionPolicy Bypass -File windows\run.ps1
```

## Build a standalone CanvasAI.exe

One command from the repo root (after `setup.ps1`):

```powershell
powershell -ExecutionPolicy Bypass -File windows\build.ps1
```

This produces `dist\CanvasAI.exe` — a **fully self-contained** app. It bundles
the backend *and* the browser used for login (Playwright + Chromium), so you can
copy `CanvasAI.exe` to any Windows PC and just double-click it; no Python, no
venv, no separate login step. The first launch opens a sign-in window, then
remembers you.

Your current `.env` is **baked into the exe** as the built-in defaults, and
everything is editable in-app under the **Settings** tab (Canvas URL, brain,
write mode, auto-submit, your writing voice). Changes save to
`%APPDATA%\Canvas-AI\settings.json`, so they persist and override the baked-in
values — no external `.env` needed. Because Chromium is included, the exe is
large (roughly 300–400 MB).

> Building must happen on Windows — PyInstaller can't cross-compile. The build
> takes a few minutes.

## Publishing it to other people

1. Build the standalone exe: `powershell -File windows\build.ps1`.
2. Install [Inno Setup](https://jrsoftware.org/isdl.php) and compile the
   installer: `iscc windows\installer.iss` → `dist\Canvas-AI-Setup.exe`.
3. Share `Canvas-AI-Setup.exe` (or just `CanvasAI.exe`).

On first launch the app opens a **Setup** tab that walks each user through
installing Claude Code, logging into Claude, setting their Canvas URL, and
signing in to Canvas. The bundled `.env` is auto-sanitized at build time, so
secrets (tokens/keys) and your personal writing sample are never shipped.

Before you publish, read the "Heads-up before publishing" notes in the project
README — each user needs their own Claude subscription, and a tool that submits
graded work raises real academic-integrity and terms-of-service issues.

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
