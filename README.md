# Canvas-AI

A **local-first AI assistant for Canvas LMS**. It can browse your courses, read
modules and the content embedded inside pages (PDFs, slides, iframed videos/LTI
tools), and — with your confirmation — draft and post discussion replies or
submit work.

The "brain" runs **locally via [Ollama](https://ollama.com)** by default, so no
data leaves your machine except the calls to your own Canvas server. An optional
cloud brain (Anthropic) can be enabled if you want stronger reasoning.

## Authentication (no token? no problem)

Many K-12 districts disable personal access tokens. Canvas-AI handles both cases:

- **`AUTH_MODE=browser` (default):** you log in once through a real browser
  window — including your district's SSO/MFA — and the session is saved to a
  local profile. Canvas-AI then makes the *same official REST API calls* using
  your session cookies. No token, no admin approval needed; it can only do what
  you can already do when logged in.
- **`AUTH_MODE=token`:** use a personal access token (Canvas → Account →
  Settings → **+ New Access Token**) if your school allows them.

Browser mode needs the browser extra:
```bash
pip install -e ".[browser]" && playwright install chromium
canvas-ai login        # opens a window; log in, it detects success, saves session
```
Your saved session lives in `.canvas_profile/` (git-ignored — it holds your
cookies, so never commit or share it).

**District uses Microsoft 365 / Entra SSO?** Supported. On `canvas-ai login`,
Canvas redirects to the Microsoft sign-in; complete it (with MFA) in the window
and pick *"Stay signed in: Yes"*. The login uses your real installed Chrome when
available, since Microsoft can reject automated browsers. Install Chrome if you
hit a "browser doesn't meet security requirements" message.

## How it works

```
You ──▶ Agent loop ──▶ Canvas REST API ──▶ your Canvas
          │  ▲
          ▼  │
        Tools (read: courses/modules/pages/discussions
               write: replies/submissions — all gated)
          │
          ▼
     Extractors (HTML, PDF/DOCX, iframe via Playwright)
```

- **Read** uses the official Canvas REST API (reliable, structured).
- **Embedded content** is discovered from page HTML, then resolved: Canvas files
  are downloaded + parsed; iframes/LTI tools fall back to a headless browser.
- **Writes** always pass through a confirmation gate (`canvas_ai/agent/gates.py`).
  Graded submissions are forced to require explicit human approval and can never
  be auto-submitted.

## Setup (Windows, one command)

In PowerShell, from where you want it installed:

```powershell
git clone https://github.com/JusticeRox98577/Canvas-AI.git
cd Canvas-AI
powershell -ExecutionPolicy Bypass -File setup.ps1
```

`setup.ps1` creates a virtual environment, installs Canvas-AI + the browser
extra, installs Ollama (via winget) and pulls **llama3.1:8b**, and creates your
`.env`. The 8B model runs fully on a 10GB GPU (e.g. RTX 3080) with VRAM to
spare, so your PC stays usable.

Then, in a new terminal from the project folder:

```powershell
.\.venv\Scripts\Activate.ps1
notepad .env          # set CANVAS_BASE_URL to your school's Canvas URL
canvas-ai login       # sign in via Microsoft 365 in the browser window
canvas-ai courses     # confirm it works
```

Ollama runs as a background service on Windows after install, so there's no
separate `ollama serve` step.

## Setup (macOS, one command)

In Terminal, from where you want it installed:

```bash
git clone https://github.com/JusticeRox98577/Canvas-AI.git
cd Canvas-AI
bash setup.sh
```

`setup.sh` creates a virtual environment, installs Canvas-AI + the browser
extra, installs Ollama (via Homebrew), starts the Ollama server, pulls
**llama3.1:8b**, and creates your `.env`. On Apple Silicon the 8B model runs on
the GPU via Metal using unified memory (~6GB), comfortable on 16GB+ Macs.

Then, in a new terminal from the project folder:

```bash
source .venv/bin/activate
nano .env             # set CANVAS_BASE_URL to your school's Canvas URL
canvas-ai login       # sign in via Microsoft 365 in the browser window
canvas-ai courses     # confirm it works
```

(Requires [Homebrew](https://brew.sh). If you don't have it, install Ollama from
https://ollama.com/download and re-run.)

## Usage

```bash
canvas-ai login                                     # browser mode: log in once
canvas-ai web                                       # launch the GUI (recommended)
canvas-ai courses                                   # connectivity check
canvas-ai agent "Summarize Module 3 in Biology and list any due dates"
canvas-ai agent "Draft a reply to this week's discussion in History"
```

### Web app (GUI)

`canvas-ai web` starts a local web app at http://127.0.0.1:8765 with:

- **Modules** — browse course → modules → items; read pages inline.
- **Due Dates** — upcoming assignments across all courses with submit status.
- **Discussions** — read a thread, *Draft with AI*, review, then *Post*.
- **Chat** — ask the agent about a course in plain English.

The agent in the web app runs **read-only** — it can read and propose, but
posting a reply or submitting an assignment is always an explicit button click,
and graded submissions show a confirm dialog first. Reads use your saved login
session (no browser relaunch), so it's fast.

`WRITE_MODE` in `.env` controls write behavior: `dry_run` (default, writes
nothing), `confirm` (asks before each write), or `auto` (graded work still asks).

## A note on responsible use

This is built to help you **read, organize, and draft** your own coursework. It
is not built to take quizzes/exams or submit graded work on your behalf without
review — that's why graded submissions always require your explicit confirmation.
Check your institution's academic-integrity policy before using AI assistance on
graded work.

## Layout

| Path | What it does |
|------|--------------|
| `canvas_ai/canvas/` | Canvas REST client + resource helpers |
| `canvas_ai/extract/` | HTML/PDF/DOCX/iframe text extraction |
| `canvas_ai/llm/` | Pluggable brain (Ollama default, Anthropic optional) |
| `canvas_ai/agent/` | Tool registry, write gate, reasoning loop |
| `canvas_ai/cli.py` | Command-line entry point |
