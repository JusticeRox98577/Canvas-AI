# Canvas-AI

A **local-first AI study assistant for Canvas LMS**. By default it helps you
**read, understand, study, and draft** your coursework — it does not submit
anything. Submitting/auto-doing graded work is an optional capability that is
**off until you explicitly enable it** (`ALLOW_SUBMIT=true`, or the toggle in
Settings); until then those buttons don't even appear. You are responsible for
following your school's academic-integrity policy.

A **local-first AI assistant for Canvas LMS**. It can browse your courses, read
modules and the content embedded inside pages (PDFs, slides, iframed videos/LTI
tools), and — with your confirmation — draft and post discussion replies or
submit work.

The "brain" runs on **your Claude Pro/Max subscription** by default (through the
Claude Code CLI), so usage counts against your chat plan — **not** API credits.
No Ollama, no API keys. A local model (Ollama) or the Anthropic API remain
available as alternatives.

## Authentication (no token? no problem)

Many K-12 districts disable personal access tokens. Canvas-AI handles both cases:

- **`AUTH_MODE=browser` (default):** you log in once through a real browser
  window — including your district's SSO/MFA — and the session is saved to a
  local profile. Canvas-AI then makes the *same official REST API calls* using
  your session cookies. No token, no admin approval needed; it can only do what
  you can already do when logged in.
- **`AUTH_MODE=token`:** use a personal access token (Canvas → Account →
  Settings → **+ New Access Token**) if your school allows them.

### Which brain (subscription vs. local vs. API)

Both chat (`LLM_PROVIDER`) and drafting (`DRAFT_PROVIDER`) default to
`claude_code`:

- `claude_code` — your **Claude Pro/Max subscription** via the Claude Code CLI
  (counts against your chat plan, *not* API credits). **Default.** Install it
  and log in once: on Windows `irm https://claude.ai/install.ps1 | iex`, then
  run `claude` and choose Subscription login.
- `ollama` — a local, free model (needs Ollama installed + a model pulled).
- `anthropic` — the Anthropic **API** (separate pay-as-you-go credits + an
  `ANTHROPIC_API_KEY`).

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
- **Writes** pass through a confirmation gate (`canvas_ai/agent/gates.py`).
  Graded submissions require explicit human approval unless you opt into
  `AUTO_SUBMIT=true` (see [Doing assignments directly](#doing-assignments-directly)).

## Setup (Windows, one command)

In PowerShell, from where you want it installed:

```powershell
git clone https://github.com/JusticeRox98577/Canvas-AI.git
cd Canvas-AI
powershell -ExecutionPolicy Bypass -File setup.ps1
```

`setup.ps1` creates a virtual environment, installs Canvas-AI + the browser and
desktop extras, installs the **Claude Code CLI**, and creates your `.env`
already set to use your Claude subscription. No Ollama, no API keys.

Then, in a new terminal from the project folder:

```powershell
.\.venv\Scripts\Activate.ps1
claude                # log in ONCE -> choose Subscription (Pro/Max)
notepad .env          # set CANVAS_BASE_URL to your school's Canvas URL
canvas-ai login       # sign in via Microsoft 365 in the browser window
canvas-ai app         # open the native Windows app
```

## Usage

```powershell
canvas-ai login                                     # browser mode: log in once
canvas-ai app                                       # native Windows window (recommended)
canvas-ai web                                       # same UI in your browser
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

## Native Windows app

A native desktop window lives in `windows/`. It launches the Python backend for
you on start and renders the UI with **WebView2** (built into Windows 10/11) —
no browser tab, no extra runtime to install.

Run it from source (after the setup above + `canvas-ai login`):

```powershell
canvas-ai app
# or:  powershell -ExecutionPolicy Bypass -File windows\run.ps1
```

Build a standalone `CanvasAI.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File windows\build.ps1   # -> dist\CanvasAI.exe
```

Keep your `.env` and the `.canvas_profile` folder next to the exe (or run it from
the project folder) so it can find your settings and saved login. See
[`windows/README.md`](windows/README.md) for details.

Tabs mirror the web app — Modules, Due Dates, Discussions, Chat.

## Make it sound like you

Everything Canvas-AI drafts (assignment responses, discussion posts, quiz
essays) is written to avoid the usual "AI tells" — no em dashes, no "Honestly,",
no forced three-bullet lists, plain first-person wording.

To go further and match **your own** voice, give it a writing sample:

```powershell
copy voice.example.txt voice.txt
notepad voice.txt        # paste a couple paragraphs of your real writing
```

The model reads `voice.txt` and imitates your word choices, sentence length, and
tone. The file stays on your computer and is git-ignored. (You can also set
`WRITING_SAMPLE` in `.env` instead.) Edits take effect on the next draft — no
restart needed.

## Doing assignments directly

Each assignment has a **"Do it for me"** button that uses the AI to write the
whole submission. By default it then shows you a confirm dialog before anything
is posted. To skip the confirmation and have it write **and** submit in one
click, set `AUTO_SUBMIT=true` in your `.env`:

```
WRITE_MODE=auto
AUTO_SUBMIT=true
```

This also lets the chat agent submit graded work on its own. It's off by default
because graded submissions are high-stakes — this is your account and your
coursework, so check your school's academic-integrity policy before enabling it.

### Quizzes

Classic quizzes have a **"Do quiz with AI"** button: it starts the attempt, has
the AI answer every supported question (multiple choice, true/false,
multiple-answer, short answer, numerical, essay), and shows the answers for your
review. Nothing is turned in until you click **Submit** (or immediately, if
`AUTO_SUBMIT=true`). **New Quizzes** (the LTI-based engine) are not reachable via
the Canvas API and can't be automated.

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
