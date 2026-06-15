# Canvas-AI

A **local-first AI assistant for Canvas LMS**. It can browse your courses, read
modules and the content embedded inside pages (PDFs, slides, iframed videos/LTI
tools), and — with your confirmation — draft and post discussion replies or
submit work.

The "brain" runs **locally via [Ollama](https://ollama.com)** by default, so no
data leaves your machine except the calls to your own Canvas server. An optional
cloud brain (Anthropic) can be enabled if you want stronger reasoning.

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

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                 # core
pip install -e ".[browser]"      # optional: embedded iframe/LTI extraction
playwright install chromium      # if you installed the browser extra

cp .env.example .env             # then fill in CANVAS_BASE_URL + CANVAS_TOKEN
```

Get a token: Canvas → **Account → Settings → + New Access Token**.

Run a local model:
```bash
ollama pull llama3.1
ollama serve
```

## Usage

```bash
canvas-ai courses                                   # connectivity check
canvas-ai agent "Summarize Module 3 in Biology and list any due dates"
canvas-ai agent "Draft a reply to this week's discussion in History"
```

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
