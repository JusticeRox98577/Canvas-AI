"""Fallback quiz solver that drives the real quiz page in a browser.

Only used when the fast API path can't read a quiz's questions — i.e. Canvas
"one question at a time" quizzes, which Canvas refuses to expose over the API.
It reuses the logged-in Playwright profile, reads each question off the page,
asks the AI to answer, fills it in, and clicks Next. It stops BEFORE the final
submit unless submit=True; Canvas auto-saves answers as you navigate, so the
attempt can then be finished from the app (API complete) or in Canvas.

This is best-effort and depends on Canvas's classic quiz HTML, so selectors may
need tweaking across Canvas versions.
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable

from canvas_ai.config import Config

CHOICE = {"multiple_choice_question", "true_false_question"}
MULTI = {"multiple_answers_question"}
TEXT = {"short_answer_question", "essay_question"}
NUMERIC = {"numerical_question"}
KNOWN = CHOICE | MULTI | TEXT | NUMERIC


def _qtype(css_class: str) -> str:
    for t in KNOWN:
        if t in css_class:
            return t
    return "unknown"


def _click_if_present(page, *selectors) -> bool:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def solve(
    config: Config,
    course_id: int,
    quiz_id: int,
    answer_fn: Callable[[str, str, list[str]], dict],
    *,
    submit: bool = False,
    max_questions: int = 200,
) -> dict[str, Any]:
    """Take a one-at-a-time quiz through the browser. Returns answered/skipped."""
    from canvas_ai.browser.session import BrowserCanvasClient

    client = BrowserCanvasClient(config, headless=True)
    ctx = client._ctx
    answered: list[dict] = []
    skipped: list[dict] = []
    submitted = False
    try:
        page = ctx.new_page()
        page.goto(
            f"{config.canvas_base_url}/courses/{course_id}/quizzes/{quiz_id}/take",
            wait_until="domcontentloaded",
        )
        # Start/resume the attempt if we landed on the quiz cover page.
        _click_if_present(
            page,
            "a:has-text('Resume Quiz')",
            "button:has-text('Resume Quiz')",
            "a:has-text('Take the Quiz')",
            "button:has-text('Take the Quiz')",
            "#take_quiz_link",
        )
        page.wait_for_timeout(800)

        seen: set[str] = set()
        for _ in range(max_questions):
            q = page.query_selector("div.question[id^='question_']")
            if not q:
                break
            qid = q.get_attribute("id") or ""
            if qid in seen:
                break  # can't advance any further
            seen.add(qid)

            css = q.get_attribute("class") or ""
            qtype = _qtype(css)
            tnode = q.query_selector(".question_text")
            qtext = (tnode.inner_text().strip() if tnode else "").strip()

            try:
                if qtype in CHOICE or qtype in MULTI:
                    ans_nodes = q.query_selector_all(".answer")
                    options = []
                    for a in ans_nodes:
                        inp = a.query_selector("input[type=radio], input[type=checkbox]")
                        lbl = (a.query_selector(".answer_label")
                               or a.query_selector(".answer_text") or a)
                        options.append((inp, (lbl.inner_text().strip() if lbl else "")))
                    choice = answer_fn(qtype, qtext, [o[1] for o in options])
                    idxs = [i for i in choice.get("indices", []) if 0 <= i < len(options)]
                    for i in idxs:
                        if options[i][0]:
                            options[i][0].check()
                    if idxs:
                        answered.append({"question": qtext[:300], "type": qtype,
                                         "answer": "; ".join(options[i][1] for i in idxs)})
                    else:
                        skipped.append({"question": qtext[:300], "type": qtype})

                elif qtype in TEXT or qtype in NUMERIC:
                    choice = answer_fn(qtype, qtext, [])
                    txt = (choice.get("text") or "").strip()
                    filled = False
                    if txt:
                        ta = q.query_selector("textarea")
                        inp = q.query_selector("input[type=text]")
                        if ta:
                            try:
                                ta.fill(txt); filled = True
                            except Exception:  # noqa: BLE001
                                pass
                        if not filled:
                            frame_el = q.query_selector("iframe")  # TinyMCE essay editor
                            if frame_el:
                                try:
                                    fr = frame_el.content_frame()
                                    if fr:
                                        fr.fill("body", txt); filled = True
                                except Exception:  # noqa: BLE001
                                    pass
                        if not filled and inp:
                            try:
                                inp.fill(txt); filled = True
                            except Exception:  # noqa: BLE001
                                pass
                    if filled:
                        answered.append({"question": qtext[:300], "type": qtype, "answer": txt[:300]})
                    else:
                        skipped.append({"question": qtext[:300], "type": qtype})
                else:
                    skipped.append({"question": qtext[:300], "type": qtype or "unknown"})
            except Exception as exc:  # noqa: BLE001
                skipped.append({"question": qtext[:300], "type": qtype, "error": str(exc)[:160]})

            page.wait_for_timeout(700)  # let Canvas auto-save the answer

            # Move to the next question; if there's no Next, we're at the end.
            moved = _click_if_present(
                page,
                "button.next-question",
                "a.next-question",
                "#next-question-button",
                "button:has-text('Next')",
            )
            if not moved:
                break
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(500)

        if submit:
            submitted = _click_if_present(
                page,
                "#submit_quiz_button",
                "button#submit_quiz_button",
                "button:has-text('Submit Quiz')",
                "input[type=submit][value*='Submit']",
            )
            if submitted:
                page.wait_for_load_state("domcontentloaded")
                time.sleep(1.0)

        return {"answered": answered, "skipped": skipped, "submitted": submitted}
    finally:
        client.close()
