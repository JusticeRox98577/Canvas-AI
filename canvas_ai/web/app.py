"""FastAPI backend for the Canvas-AI web app.

Reads use the fast cookie-based client (saved browser-login session). Writes
(discussion replies, assignment submissions) are exposed as explicit endpoints
that the *user* triggers from the UI -- the agent itself runs read-only, so it
can read and propose but never posts on its own. Graded submissions require an
explicit confirm flag.
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from canvas_ai.canvas import assignments, courses, discussions, files as files_api, pages
from canvas_ai.canvas.cookie_client import CookieCanvasClient, SessionExpired
from canvas_ai.extract import documents
from canvas_ai.config import Config
from canvas_ai.agent.loop import SYSTEM_PROMPT, run as run_agent
from canvas_ai.agent.tools import Toolbox
from canvas_ai.llm import get_provider

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Canvas-AI")
_config = Config.load()
_brain = None        # agent brain (tool-using), lazily created
_draft_brain = None  # drafting brain (can be a different/better provider)


def client() -> CookieCanvasClient:
    try:
        return CookieCanvasClient(_config)
    except SessionExpired as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def _guard(fn):
    try:
        return fn()
    except SessionExpired as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


# -- status ---------------------------------------------------------------
@app.get("/api/status")
def status() -> dict:
    try:
        with CookieCanvasClient(_config) as c:
            me = c.get("/users/self")
        return {"authenticated": True, "name": me.get("name"), "base_url": _config.canvas_base_url}
    except Exception:  # noqa: BLE001
        return {"authenticated": False, "base_url": _config.canvas_base_url}


# -- reads ----------------------------------------------------------------
@app.get("/api/courses")
def api_courses() -> list[dict]:
    def go():
        with client() as c:
            return [{"id": x["id"], "name": x.get("name")} for x in courses.list_courses(c)]
    return _guard(go)


@app.get("/api/modules")
def api_modules(course_id: int) -> list[dict]:
    def go():
        with client() as c:
            out = []
            for m in courses.list_modules(c, course_id):
                items = courses.list_module_items(c, course_id, m["id"])
                out.append({"id": m["id"], "name": m.get("name"), "items": items})
            return out
    return _guard(go)


@app.get("/api/page")
def api_page(course_id: int, page_url: str) -> dict:
    def go():
        with client() as c:
            p = pages.read_page(c, course_id, page_url)
        return {"title": p.get("title"), "html": p.get("body", "")}
    return _guard(go)


@app.get("/api/assignments")
def api_assignments(course_id: int) -> list[dict]:
    def go():
        with client() as c:
            return assignments.list_assignments(c, course_id)
    return _guard(go)


@app.get("/api/assignment")
def api_assignment(course_id: int, assignment_id: int) -> dict:
    def go():
        with client() as c:
            return assignments.get_assignment(c, course_id, assignment_id)
    return _guard(go)


@app.get("/api/dashboard")
def api_dashboard(course_id: int | None = None) -> list[dict]:
    """Assignments with due dates, soonest first. Filtered to one course if given."""
    def go():
        rows: list[dict] = []
        with client() as c:
            for course in courses.list_courses(c):
                if course_id and course["id"] != course_id:
                    continue
                for a in assignments.list_assignments(c, course["id"], include=["submission"]):
                    if a.get("due_at"):
                        sub = a.get("submission") or {}
                        submitted = bool(sub.get("submitted_at")) or sub.get("workflow_state") in {"submitted", "graded"}
                        rows.append({
                            "course": course.get("name"),
                            "course_id": course["id"],
                            "id": a["id"],
                            "name": a.get("name"),
                            "due_at": a.get("due_at"),
                            "html_url": a.get("html_url"),
                            "submitted": submitted,
                        })
        rows.sort(key=lambda r: r["due_at"])
        return rows
    return _guard(go)


@app.get("/api/file")
def api_file(file_id: int) -> dict:
    def go():
        with client() as c:
            m = c.get(f"/files/{file_id}")
        return {
            "id": m.get("id"),
            "display_name": m.get("display_name"),
            "content_type": m.get("content-type") or m.get("content_type"),
            "size": m.get("size"),
        }
    return _guard(go)


@app.get("/api/file/raw")
def api_file_raw(file_id: int) -> Response:
    """Proxy the file bytes so PDFs/images render inside the app."""
    def go():
        with client() as c:
            m = c.get(f"/files/{file_id}")
        r = httpx.get(m["url"], follow_redirects=True, timeout=60)
        ct = m.get("content-type") or "application/octet-stream"
        return Response(content=r.content, media_type=ct)
    return _guard(go)


@app.get("/api/file/text")
def api_file_text(file_id: int) -> dict:
    """Extract text from a doc (PDF/DOCX) for in-app reading + AI study help."""
    def go():
        with client() as c:
            m = c.get(f"/files/{file_id}")
            path = files_api.download(c, m)
        return {"display_name": m.get("display_name"), "text": documents.extract_text(path)[:20000]}
    return _guard(go)


@app.get("/api/quiz")
def api_quiz(course_id: int, quiz_id: int) -> dict:
    def go():
        with client() as c:
            return c.get(f"/courses/{course_id}/quizzes/{quiz_id}")
    return _guard(go)


@app.get("/api/discussions")
def api_discussions(course_id: int) -> list[dict]:
    def go():
        with client() as c:
            return [
                {"id": d["id"], "title": d.get("title")}
                for d in discussions.list_discussions(c, course_id)
            ]
    return _guard(go)


@app.get("/api/discussion")
def api_discussion(course_id: int, topic_id: int) -> dict:
    def go():
        with client() as c:
            return discussions.read_discussion(c, course_id, topic_id)
    return _guard(go)


# -- writes (explicit user actions) --------------------------------------
class ReplyIn(BaseModel):
    course_id: int
    topic_id: int
    message: str
    entry_id: int | None = None


@app.post("/api/discussion/reply")
def api_reply(body: ReplyIn) -> dict:
    def go():
        with client() as c:
            if body.entry_id:
                return discussions.reply_to_entry(
                    c, body.course_id, body.topic_id, body.entry_id, body.message
                )
            return discussions.post_reply(c, body.course_id, body.topic_id, body.message)
    return _guard(go)


class SubmitIn(BaseModel):
    course_id: int
    assignment_id: int
    body: str
    confirm: bool = False


@app.post("/api/assignment/submit")
def api_submit(body: SubmitIn) -> dict:
    # Graded submissions are high-stakes: require an explicit confirm from the UI.
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Submission requires confirm=true.")

    def go():
        with client() as c:
            return assignments.submit_text(c, body.course_id, body.assignment_id, body.body)
    return _guard(go)


# -- agent (read-only) ----------------------------------------------------
class AgentIn(BaseModel):
    goal: str
    course_id: int | None = None
    course_name: str | None = None


def _course_outline(c: CookieCanvasClient, course_id: int, course_name: str | None) -> str:
    """Real module/item outline so the model can't invent course structure."""
    lines = [
        f"GROUNDING CONTEXT (real data from Canvas):",
        f"The user is currently viewing course '{course_name or course_id}' "
        f"(course_id={course_id}). Use this course_id for tool calls.",
        "Modules and items actually in this course:",
    ]
    try:
        mods = courses.list_modules(c, course_id)
        if not mods:
            lines.append("  (this course has no modules)")
        for m in mods:
            lines.append(f"- Module: {m.get('name')}")
            for it in courses.list_module_items(c, course_id, m["id"]):
                lines.append(f"    - [{it.get('type')}] {it.get('title')}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"  (could not load outline: {exc})")
    lines.append(
        "Base your answer ONLY on the outline above plus any tool results. "
        "To summarize a page's actual content, call read_page with its page_url."
    )
    text = "\n".join(lines)
    # Cap the context so big courses don't slow the local model to a crawl.
    if len(text) > 6000:
        text = text[:6000] + "\n…(outline truncated)"
    return text


DRAFT_SYSTEM = (
    "You are a writing assistant helping a student draft text they will review "
    "and edit. Output ONLY the requested text — no preamble, no explanation, and "
    "never mention tools, functions, APIs, or that you are an AI. Follow the "
    "requested voice, length, and format exactly."
)


class DraftIn(BaseModel):
    goal: str


@app.post("/api/draft")
def api_draft(body: DraftIn) -> dict:
    """Tool-free single-shot generation for drafting/explaining. The agent's
    tool machinery confuses small models into 'calling functions' instead of
    just writing, so this path uses a plain chat with no tools."""
    global _draft_brain
    if _draft_brain is None:
        _draft_brain = get_provider(_config, _config.draft_provider)

    def go():
        resp = _draft_brain.chat(
            [{"role": "system", "content": DRAFT_SYSTEM},
             {"role": "user", "content": body.goal}],
            tools=None,
        )
        return {"answer": resp.text}
    return _guard(go)


@app.post("/api/agent")
def api_agent(body: AgentIn) -> dict:
    global _brain
    if _brain is None:
        _brain = get_provider(_config)

    def go():
        with client() as c:
            toolbox = Toolbox(c, _config)
            history = [{"role": "system", "content": SYSTEM_PROMPT}]
            if body.course_id:
                history.append({"role": "system", "content": _course_outline(c, body.course_id, body.course_name)})
            answer = run_agent(_brain, toolbox, body.goal, include_writes=False, history=history)
        return {"answer": answer}
    return _guard(go)


# -- static frontend ------------------------------------------------------
@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
