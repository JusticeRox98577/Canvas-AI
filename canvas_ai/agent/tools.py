"""Tool registry exposed to the LLM brain.

Each tool has a JSON schema (sent to the model) and a Python handler. Read
tools run freely; write tools route through the confirmation gate.
"""

from __future__ import annotations

from typing import Any, Callable

from canvas_ai.canvas import assignments, courses, discussions, pages
from canvas_ai.canvas.client import CanvasClient
from canvas_ai.config import Config
from canvas_ai.extract import embedded as embed
from canvas_ai.extract.html import parse_page_html
from canvas_ai.agent import gates


class Toolbox:
    """Binds tools to a live Canvas client + config (for the write mode)."""

    def __init__(self, client: CanvasClient, config: Config):
        self.client = client
        self.config = config
        self._handlers: dict[str, Callable[..., Any]] = {
            "list_courses": self._list_courses,
            "list_modules": self._list_modules,
            "list_module_items": self._list_module_items,
            "read_page": self._read_page,
            "list_discussions": self._list_discussions,
            "read_discussion": self._read_discussion,
            "post_discussion_reply": self._post_discussion_reply,
            "reply_to_entry": self._reply_to_entry,
            "submit_assignment_text": self._submit_assignment_text,
        }

    # -- dispatch --------------------------------------------------------
    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name not in self._handlers:
            return {"error": f"unknown tool {name!r}"}
        return self._handlers[name](**args)

    # -- read tools ------------------------------------------------------
    def _list_courses(self) -> list[dict]:
        return [
            {"id": c["id"], "name": c.get("name")}
            for c in courses.list_courses(self.client)
        ]

    def _list_modules(self, course_id: int) -> list[dict]:
        return [
            {"id": m["id"], "name": m.get("name")}
            for m in courses.list_modules(self.client, course_id)
        ]

    def _list_module_items(self, course_id: int, module_id: int) -> list[dict]:
        return courses.list_module_items(self.client, course_id, module_id)

    def _read_page(self, course_id: int, page_url: str, follow_embedded: bool = False) -> dict:
        page = pages.read_page(self.client, course_id, page_url)
        parsed = parse_page_html(page.get("body", ""))
        result: dict[str, Any] = {
            "title": page.get("title"),
            "text": parsed.text,
            "embedded": [e.__dict__ for e in parsed.embedded],
        }
        if follow_embedded:
            result["embedded_text"] = {
                e.url: embed.resolve(self.client, e) for e in parsed.embedded
            }
        return result

    def _list_discussions(self, course_id: int) -> list[dict]:
        return [
            {"id": d["id"], "title": d.get("title")}
            for d in discussions.list_discussions(self.client, course_id)
        ]

    def _read_discussion(self, course_id: int, topic_id: int) -> dict:
        return discussions.read_discussion(self.client, course_id, topic_id)

    # -- write tools (gated) --------------------------------------------
    def _post_discussion_reply(self, course_id: int, topic_id: int, message: str) -> dict:
        if not gates.approve("post_discussion_reply", message, mode=self.config.write_mode):
            return {"status": "skipped"}
        return discussions.post_reply(self.client, course_id, topic_id, message)

    def _reply_to_entry(
        self, course_id: int, topic_id: int, entry_id: int, message: str
    ) -> dict:
        if not gates.approve("reply_to_entry", message, mode=self.config.write_mode):
            return {"status": "skipped"}
        return discussions.reply_to_entry(self.client, course_id, topic_id, entry_id, message)

    def _submit_assignment_text(self, course_id: int, assignment_id: int, body: str) -> dict:
        # HIGH_STAKES: gate forces 'confirm' unless the user opted into AUTO_SUBMIT.
        if not gates.approve(
            "submit_assignment_text",
            body,
            mode=self.config.write_mode,
            auto_submit=self.config.auto_submit,
        ):
            return {"status": "skipped"}
        return assignments.submit_text(self.client, course_id, assignment_id, body)


WRITE_TOOLS = {"post_discussion_reply", "reply_to_entry", "submit_assignment_text"}


def tool_schemas(include_writes: bool = True) -> list[dict[str, Any]]:
    """JSON schemas advertised to the LLM (Ollama/Anthropic compatible shape).

    Set include_writes=False (e.g. in the web UI) so the agent can only read and
    propose; actual posting/submitting then happens through explicit user action.
    """

    def fn(name: str, desc: str, props: dict, required: list[str]) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": desc,
                "parameters": {"type": "object", "properties": props, "required": required},
            },
        }

    cid = {"course_id": {"type": "integer"}}
    schemas = [
        fn("list_courses", "List the user's active courses.", {}, []),
        fn("list_modules", "List modules in a course.", cid, ["course_id"]),
        fn(
            "list_module_items",
            "List items inside a module (pages, files, quizzes, embedded tools).",
            {**cid, "module_id": {"type": "integer"}},
            ["course_id", "module_id"],
        ),
        fn(
            "read_page",
            "Read a page's text and discover embedded content. Set follow_embedded to also extract embedded text.",
            {**cid, "page_url": {"type": "string"}, "follow_embedded": {"type": "boolean"}},
            ["course_id", "page_url"],
        ),
        fn("list_discussions", "List discussion topics in a course.", cid, ["course_id"]),
        fn(
            "read_discussion",
            "Read a discussion topic and all its replies.",
            {**cid, "topic_id": {"type": "integer"}},
            ["course_id", "topic_id"],
        ),
        fn(
            "post_discussion_reply",
            "Post a new top-level reply to a discussion (routed through write gate).",
            {**cid, "topic_id": {"type": "integer"}, "message": {"type": "string"}},
            ["course_id", "topic_id", "message"],
        ),
        fn(
            "reply_to_entry",
            "Reply to another person's discussion post (routed through write gate).",
            {
                **cid,
                "topic_id": {"type": "integer"},
                "entry_id": {"type": "integer"},
                "message": {"type": "string"},
            },
            ["course_id", "topic_id", "entry_id", "message"],
        ),
        fn(
            "submit_assignment_text",
            "Submit a text assignment. ALWAYS requires explicit human confirmation.",
            {**cid, "assignment_id": {"type": "integer"}, "body": {"type": "string"}},
            ["course_id", "assignment_id", "body"],
        ),
    ]
    if not include_writes:
        schemas = [s for s in schemas if s["function"]["name"] not in WRITE_TOOLS]
    return schemas
