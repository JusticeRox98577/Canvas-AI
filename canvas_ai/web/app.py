"""FastAPI backend for the Canvas-AI web app.

Reads use the fast cookie-based client (saved browser-login session). Writes
(discussion replies, assignment submissions) are exposed as explicit endpoints
that the *user* triggers from the UI -- the agent itself runs read-only, so it
can read and propose but never posts on its own. Graded submissions require an
explicit confirm flag.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from canvas_ai.canvas import assignments, courses, discussions, pages
from canvas_ai.canvas.cookie_client import CookieCanvasClient, SessionExpired
from canvas_ai.config import Config
from canvas_ai.agent.loop import run as run_agent
from canvas_ai.agent.tools import Toolbox
from canvas_ai.llm import get_provider

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI(title="Canvas-AI")
_config = Config.load()
_brain = None  # lazily created on first agent call


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
def api_dashboard() -> list[dict]:
    """Upcoming assignments with due dates across all courses, soonest first."""
    def go():
        rows: list[dict] = []
        with client() as c:
            for course in courses.list_courses(c):
                for a in assignments.list_assignments(c, course["id"]):
                    if a.get("due_at"):
                        sub = a.get("submission") or {}
                        rows.append({
                            "course": course.get("name"),
                            "course_id": course["id"],
                            "id": a["id"],
                            "name": a.get("name"),
                            "due_at": a.get("due_at"),
                            "html_url": a.get("html_url"),
                            "submitted": bool(sub.get("submitted_at")),
                        })
        rows.sort(key=lambda r: r["due_at"])
        return rows
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


@app.post("/api/agent")
def api_agent(body: AgentIn) -> dict:
    global _brain
    if _brain is None:
        _brain = get_provider(_config)

    def go():
        with client() as c:
            toolbox = Toolbox(c, _config)
            answer = run_agent(_brain, toolbox, body.goal, include_writes=False)
        return {"answer": answer}
    return _guard(go)


# -- static frontend ------------------------------------------------------
@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
