"""FastAPI backend for the Canvas-AI web app.

Reads use the fast cookie-based client (saved browser-login session). Writes
(discussion replies, assignment submissions) are exposed as explicit endpoints
that the *user* triggers from the UI -- the agent itself runs read-only, so it
can read and propose but never posts on its own. Graded submissions require an
explicit confirm flag.
"""

from __future__ import annotations

import os
import re
import sys

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from canvas_ai.canvas import assignments, courses, discussions, files as files_api, pages, quizzes
from canvas_ai.canvas.cookie_client import CookieCanvasClient, SessionExpired
from canvas_ai.extract import documents
from canvas_ai.config import Config
from canvas_ai.agent.loop import SYSTEM_PROMPT, run as run_agent
from canvas_ai.agent.tools import Toolbox
from canvas_ai.llm import get_provider
from canvas_ai import voice

def _static_dir() -> str:
    # When frozen by PyInstaller, data files live under sys._MEIPASS.
    base = getattr(sys, "_MEIPASS", None)
    if base:
        bundled = os.path.join(base, "canvas_ai", "web", "static")
        if os.path.isdir(bundled):
            return bundled
    return os.path.join(os.path.dirname(__file__), "static")


STATIC_DIR = _static_dir()

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


@app.get("/api/config")
def api_config() -> dict:
    """Front-end-visible settings so the UI can adapt (e.g. enable direct submit)."""
    return {
        "write_mode": _config.write_mode,
        "auto_submit": _config.auto_submit,
        "draft_provider": _config.draft_provider,
    }


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


# -- do it for me: draft + (optionally) submit in one step ---------------
DO_BASE = (
    "You are completing a homework assignment as the student. Write the full "
    "submission that directly answers what the assignment asks for. Output ONLY "
    "the finished work itself: no preamble, no headings like 'Submission', no "
    "notes to the teacher. Match any length, format, or question structure the "
    "prompt specifies."
)


def DO_SYSTEM() -> str:
    return voice.style_system(DO_BASE)


def _strip_html(html: str) -> str:
    from canvas_ai.extract.html import parse_page_html

    try:
        return parse_page_html(html or "").text.strip()
    except Exception:  # noqa: BLE001
        return (html or "").strip()


class DoIn(BaseModel):
    course_id: int
    assignment_id: int
    submit: bool = True
    confirm: bool = False


@app.post("/api/assignment/do")
def api_do(body: DoIn) -> dict:
    """Read an assignment, draft a complete submission, and (if allowed) submit it.

    Submission happens when AUTO_SUBMIT is enabled in .env, or when the caller
    passes confirm=true (the UI's confirm dialog). With submit=false it only
    drafts so the user can review/edit first.
    """
    global _draft_brain
    if _draft_brain is None:
        _draft_brain = get_provider(_config, _config.draft_provider)

    def go():
        with client() as c:
            a = assignments.get_assignment(c, body.course_id, body.assignment_id)
            name = a.get("name") or "this assignment"
            desc = _strip_html(a.get("description", ""))[:6000]
            points = a.get("points_possible")

            prompt = (
                f'Assignment title: "{name}".\n'
                + (f"Worth {points} points.\n" if points is not None else "")
                + "Assignment instructions:\n"
                + (desc or "(no description was provided)")
                + "\n\nWrite the complete submission now."
            )
            resp = _draft_brain.chat(
                [{"role": "system", "content": DO_SYSTEM()},
                 {"role": "user", "content": prompt}],
                tools=None,
            )
            draft = voice.clean_output(resp.text)
            if not draft:
                raise HTTPException(status_code=502, detail="The model returned an empty draft.")

            result = {"assignment": name, "draft": draft, "submitted": False}
            if body.submit:
                if not (_config.auto_submit or body.confirm):
                    raise HTTPException(
                        status_code=400,
                        detail="Submission requires confirm=true or AUTO_SUBMIT=true in .env.",
                    )
                sub = assignments.submit_text(c, body.course_id, body.assignment_id, draft)
                result["submitted"] = True
                result["submission"] = {
                    "id": sub.get("id"),
                    "workflow_state": sub.get("workflow_state"),
                    "submitted_at": sub.get("submitted_at"),
                }
            return result

    return _guard(go)


# -- do it for me: quizzes (Classic quizzes only) ------------------------
def _quiz_choose(brain, q: dict) -> tuple[dict | None, str]:
    """Ask the brain to answer one quiz question. Returns (answer_payload, display)."""
    qtype = q.get("question_type")
    text = _strip_html(q.get("question_text", ""))
    answers = q.get("answers", []) or []

    def opt_text(a: dict) -> str:
        return _strip_html(a.get("text") or a.get("html") or a.get("comments") or "")

    if qtype in quizzes.CHOICE_TYPES or qtype in quizzes.MULTI_TYPES:
        multi = qtype in quizzes.MULTI_TYPES
        opts = "\n".join(f"[{a['id']}] {opt_text(a)}" for a in answers)
        ask = "Choose ALL correct option ids" if multi else "Choose the single best option id"
        prompt = (f"Question: {text}\n\nOptions:\n{opts}\n\n{ask}. "
                  "Reply with ONLY the id number(s), comma-separated. Nothing else.")
        resp = brain.chat(
            [{"role": "system", "content": "You answer quiz questions correctly and concisely."},
             {"role": "user", "content": prompt}], tools=None)
        valid = {a["id"] for a in answers}
        ids = [int(n) for n in re.findall(r"\d+", resp.text or "") if int(n) in valid]
        if not multi:
            ids = ids[:1]
        if not ids:
            return None, ""
        display = "; ".join(opt_text(a) for a in answers if a["id"] in ids)
        return {"answer": ids if multi else ids[0]}, display

    if qtype in quizzes.TEXT_TYPES:
        prompt = f"Question: {text}\n\nWrite the answer the question asks for."
        resp = brain.chat(
            [{"role": "system", "content": DO_SYSTEM()},
             {"role": "user", "content": prompt}], tools=None)
        ans = voice.clean_output(resp.text)
        return ({"answer": ans}, ans[:300]) if ans else (None, "")

    if qtype in quizzes.NUMERIC_TYPES:
        prompt = f"Question: {text}\n\nReply with ONLY the numeric answer."
        resp = brain.chat(
            [{"role": "system", "content": "You answer quiz questions correctly and concisely."},
             {"role": "user", "content": prompt}], tools=None)
        m = re.search(r"-?\d+(?:\.\d+)?", resp.text or "")
        return ({"answer": m.group(0)}, m.group(0)) if m else (None, "")

    return None, ""  # unsupported question type -> leave blank


def _quiz_choose_browser(qtype: str, text: str, options: list[str]) -> dict:
    """Answer a question read off the quiz page. Returns {"indices":[...]} for
    choice questions or {"text": "..."} for written ones."""
    if qtype in ("multiple_choice_question", "true_false_question", "multiple_answers_question"):
        multi = qtype == "multiple_answers_question"
        opts = "\n".join(f"[{i}] {o}" for i, o in enumerate(options))
        ask = "Choose ALL correct option numbers" if multi else "Choose the single best option number"
        prompt = (f"Question: {text}\n\nOptions:\n{opts}\n\n{ask}. "
                  "Reply with ONLY the number(s), comma-separated. Nothing else.")
        resp = _draft_brain.chat(
            [{"role": "system", "content": "You answer quiz questions correctly and concisely."},
             {"role": "user", "content": prompt}], tools=None)
        idxs = [int(n) for n in re.findall(r"\d+", resp.text or "") if int(n) < len(options)]
        return {"indices": idxs if multi else idxs[:1]}

    if qtype == "numerical_question":
        prompt = f"Question: {text}\n\nReply with ONLY the numeric answer."
        resp = _draft_brain.chat(
            [{"role": "system", "content": "You answer quiz questions correctly and concisely."},
             {"role": "user", "content": prompt}], tools=None)
        m = re.search(r"-?\d+(?:\.\d+)?", resp.text or "")
        return {"text": m.group(0) if m else ""}

    prompt = f"Question: {text}\n\nWrite the answer the question asks for."
    resp = _draft_brain.chat(
        [{"role": "system", "content": DO_SYSTEM()},
         {"role": "user", "content": prompt}], tools=None)
    return {"text": voice.clean_output(resp.text)}


class QuizDoIn(BaseModel):
    course_id: int
    quiz_id: int


@app.post("/api/quiz/answer")
def api_quiz_answer(body: QuizDoIn) -> dict:
    """Start the attempt, let the AI answer every supported question, and save
    those answers — but do NOT submit. The user reviews, then calls /submit."""
    global _draft_brain
    if _draft_brain is None:
        _draft_brain = get_provider(_config, _config.draft_provider)

    def go():
        with client() as c:
            sub = quizzes.start_submission(c, body.course_id, body.quiz_id)
            sid = sub["id"]
            attempt = sub.get("attempt")
            token = sub.get("validation_token")

            review: list[dict] = []
            skipped: list[dict] = []
            seen: set = set()

            # Re-fetch each pass: "can't go back" quizzes only reveal the next
            # question after the current one is answered, so we answer-and-save
            # in order, then look again for the next.
            for _ in range(500):  # safety cap
                try:
                    qs = quizzes.get_questions(c, sid)
                except Exception as exc:  # noqa: BLE001
                    if "one question at a time" in str(exc).lower():
                        # API can't read this quiz type; fall back to driving the
                        # real quiz page in a browser. Stops before final submit.
                        from canvas_ai.canvas import quiz_browser

                        res = quiz_browser.solve(
                            _config, body.course_id, body.quiz_id,
                            _quiz_choose_browser, submit=False,
                        )
                        return {
                            "submission_id": sid,
                            "total": len(res["answered"]) + len(res["skipped"]),
                            "answered": res["answered"],
                            "skipped": res["skipped"],
                            "method": "browser",
                            "note": ("This quiz only shows one question at a time, so I filled "
                                     "it in on the quiz page directly. Review below, then Submit."),
                        }
                    raise
                progressed = False
                for q in qs:
                    if q["id"] in seen:
                        continue
                    seen.add(q["id"])
                    progressed = True
                    payload, display = _quiz_choose(_draft_brain, q)
                    qtext = _strip_html(q.get("question_text", ""))[:300]
                    qtype = q.get("question_type")
                    if payload and payload.get("answer") not in (None, "", []):
                        try:
                            # Save each answer before moving on, so locked
                            # quizzes accept it and reveal the next question.
                            quizzes.save_answers(c, sid, attempt, token, [{"id": q["id"], **payload}])
                            review.append({"question": qtext, "type": qtype, "answer": display})
                        except Exception as exc:  # noqa: BLE001
                            skipped.append({"question": qtext, "type": qtype, "error": str(exc)[:200]})
                    else:
                        skipped.append({"question": qtext, "type": qtype})
                    # In locked mode the next question appears only after a save,
                    # so re-fetch right after answering one.
                    break
                if not progressed:
                    break

            return {"submission_id": sid, "total": len(seen), "answered": review, "skipped": skipped}

    return _guard(go)


class QuizSubmitIn(BaseModel):
    course_id: int
    quiz_id: int
    submission_id: int
    confirm: bool = False


@app.post("/api/quiz/submit")
def api_quiz_submit(body: QuizSubmitIn) -> dict:
    """Turn in the quiz. Requires confirm=true (the UI dialog) or AUTO_SUBMIT."""
    if not (_config.auto_submit or body.confirm):
        raise HTTPException(status_code=400, detail="Submitting a quiz requires confirm=true or AUTO_SUBMIT=true.")

    def go():
        with client() as c:
            sub = quizzes.current_submission(c, body.course_id, body.quiz_id)
            quizzes.complete(
                c, body.course_id, body.quiz_id, body.submission_id,
                sub.get("attempt"), sub.get("validation_token"),
            )
            done = quizzes.current_submission(c, body.course_id, body.quiz_id)
            return {
                "completed": True,
                "score": done.get("score") if done.get("score") is not None else done.get("kept_score"),
                "workflow_state": done.get("workflow_state"),
            }

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


DRAFT_BASE = (
    "You are helping a student draft text they will review and edit. Output ONLY "
    "the requested text: no preamble, no explanation, and never mention tools, "
    "functions, APIs, or that you are an AI. Follow the requested length and format."
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
            [{"role": "system", "content": voice.style_system(DRAFT_BASE)},
             {"role": "user", "content": body.goal}],
            tools=None,
        )
        return {"answer": voice.clean_output(resp.text)}
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
