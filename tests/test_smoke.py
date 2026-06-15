"""Smoke tests that don't touch the network."""

import os

import pytest

from canvas_ai.agent.gates import HIGH_STAKES, approve
from canvas_ai.agent.tools import WRITE_TOOLS, tool_schemas
from canvas_ai.extract.html import parse_page_html


def test_tool_schemas_well_formed():
    schemas = tool_schemas()
    assert schemas
    for s in schemas:
        assert s["type"] == "function"
        assert s["function"]["name"]
        assert "parameters" in s["function"]


def test_parse_page_finds_embedded():
    html = """
    <p>Hello world</p>
    <iframe src="https://youtube.com/embed/abc" title="Lecture"></iframe>
    <a href="/courses/1/files/42/download">slides.pdf</a>
    """
    parsed = parse_page_html(html)
    assert "Hello world" in parsed.text
    kinds = {e.kind for e in parsed.embedded}
    assert "iframe" in kinds
    assert "file" in kinds


def test_graded_work_is_high_stakes():
    assert "submit_assignment_text" in HIGH_STAKES


def test_dry_run_never_writes():
    assert approve("post_discussion_reply", "hi", mode="dry_run") is False


def test_recovers_tool_call_emitted_as_text():
    from canvas_ai.agent.loop import extract_text_tool_calls

    # The exact shape llama3.1:8b produced in the UI (note Python-style False).
    raw = '{"name": "read_discussion", "parameters": {"follow_embedded": False, "course_id": 48174, "topic_id": 1}}'
    calls = extract_text_tool_calls(raw)
    assert len(calls) == 1
    assert calls[0].name == "read_discussion"
    assert calls[0].arguments["course_id"] == 48174

    # Plain prose should yield nothing.
    assert extract_text_tool_calls("Here is the summary of module 3.") == []


def test_read_only_schemas_exclude_writes():
    names = {s["function"]["name"] for s in tool_schemas(include_writes=False)}
    assert not (names & WRITE_TOOLS)


def test_web_app_builds_and_handles_no_session():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    os.environ.setdefault("CANVAS_BASE_URL", "https://x.instructure.com")
    from canvas_ai.web.app import app

    c = TestClient(app)
    assert c.get("/api/status").json()["authenticated"] is False
    assert c.get("/api/courses").status_code == 401  # no saved session
    assert c.get("/").status_code == 200
