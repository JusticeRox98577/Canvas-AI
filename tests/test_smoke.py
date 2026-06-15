"""Smoke tests that don't touch the network."""

from canvas_ai.agent.gates import HIGH_STAKES, approve
from canvas_ai.agent.tools import tool_schemas
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
