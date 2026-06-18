"""Fallback quiz solver that drives the real quiz page in a browser.

Only used when the fast API path can't read a quiz's questions — i.e. Canvas
"one question at a time" quizzes, which Canvas refuses to expose over the API.
It reuses the logged-in Playwright profile, reads each question off the page,
asks the AI to answer, fills it in, and clicks Next. It stops BEFORE the final
submit unless submit=True; Canvas auto-saves answers as you navigate, so the
attempt can then be finished from the app (API complete) or in Canvas.

Question types are detected by the inputs actually present (radios, checkboxes,
text fields, essay editor) rather than Canvas CSS classes, which vary by version.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from canvas_ai.config import Config

_OPT_TEXT_JS = (
    "el => { const a = el.closest('.answer'); "
    "return (a ? a.innerText : (el.parentElement ? el.parentElement.innerText : '')); }"
)


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


def _current_qid(page) -> str | None:
    el = page.query_selector("div.question[id^='question_']")
    return el.get_attribute("id") if el else None


def _find_next(page):
    for sel in (
        "button.next-question", "a.next-question", "#next-question-button",
        ".submit_button.next-question",
        "button:has-text('Next')", "a:has-text('Next')",
        "input[type=submit][value*='Next' i]",
    ):
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:  # noqa: BLE001
            continue
    return None


def _opt_text(inp) -> str:
    try:
        return (inp.evaluate(_OPT_TEXT_JS) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def solve(
    config: Config,
    course_id: int,
    quiz_id: int,
    answer_fn: Callable[[str, str, list[str]], dict],
    *,
    submit: bool = False,
    max_questions: int = 200,
) -> dict[str, Any]:
    from canvas_ai.browser.session import BrowserCanvasClient

    client = BrowserCanvasClient(config, headless=True)
    ctx = client._ctx
    answered: list[dict] = []
    skipped: list[dict] = []
    debug: list[str] = []
    submitted = False
    try:
        page = ctx.new_page()
        page.goto(
            f"{config.canvas_base_url}/courses/{course_id}/quizzes/{quiz_id}/take",
            wait_until="domcontentloaded",
        )
        _click_if_present(
            page,
            "a:has-text('Resume Quiz')", "button:has-text('Resume Quiz')",
            "a:has-text('Take the Quiz')", "button:has-text('Take the Quiz')",
            "#take_quiz_link",
        )
        page.wait_for_timeout(900)

        seen: set[str] = set()
        for _ in range(max_questions):
            q = page.query_selector("div.question[id^='question_']")
            if not q:
                break
            qid = q.get_attribute("id") or ""
            if qid in seen:
                break
            seen.add(qid)

            tnode = q.query_selector(".question_text")
            qtext = (tnode.inner_text().strip() if tnode else "").strip()

            # Detect by inputs present, not CSS class.
            radios = q.query_selector_all("input[type=radio]")
            checks = q.query_selector_all("input[type=checkbox]")
            textboxes = q.query_selector_all("input[type=text]")
            textareas = q.query_selector_all("textarea")
            iframes = q.query_selector_all("iframe")

            try:
                if checks:
                    options = [(c, _opt_text(c)) for c in checks]
                    choice = answer_fn("multiple_answers_question", qtext, [o[1] for o in options])
                    idxs = [i for i in choice.get("indices", []) if 0 <= i < len(options)]
                    for i in idxs:
                        options[i][0].check()
                    (answered if idxs else skipped).append(
                        {"question": qtext[:300], "type": "multiple answers",
                         "answer": "; ".join(options[i][1] for i in idxs)} if idxs
                        else {"question": qtext[:300], "type": "multiple answers"})
                elif radios:
                    options = [(r, _opt_text(r)) for r in radios]
                    # true/false vs multiple choice is answered the same way
                    choice = answer_fn("multiple_choice_question", qtext, [o[1] for o in options])
                    idxs = [i for i in choice.get("indices", []) if 0 <= i < len(options)][:1]
                    for i in idxs:
                        options[i][0].check()
                    (answered if idxs else skipped).append(
                        {"question": qtext[:300], "type": "choice",
                         "answer": "; ".join(options[i][1] for i in idxs)} if idxs
                        else {"question": qtext[:300], "type": "choice"})
                elif textareas or iframes:
                    choice = answer_fn("essay_question", qtext, [])
                    txt = (choice.get("text") or "").strip()
                    ok = False
                    if txt and textareas:
                        try:
                            textareas[0].fill(txt); ok = True
                        except Exception:  # noqa: BLE001
                            pass
                    if txt and not ok and iframes:
                        try:
                            fr = iframes[0].content_frame()
                            if fr:
                                fr.fill("body", txt); ok = True
                        except Exception:  # noqa: BLE001
                            pass
                    (answered if ok else skipped).append(
                        {"question": qtext[:300], "type": "essay", "answer": txt[:300]} if ok
                        else {"question": qtext[:300], "type": "essay"})
                elif textboxes:
                    choice = answer_fn("short_answer_question", qtext, [])
                    txt = (choice.get("text") or "").strip()
                    ok = False
                    if txt:
                        try:
                            textboxes[0].fill(txt); ok = True
                        except Exception:  # noqa: BLE001
                            pass
                    (answered if ok else skipped).append(
                        {"question": qtext[:300], "type": "text", "answer": txt[:300]} if ok
                        else {"question": qtext[:300], "type": "text"})
                else:
                    cls = (q.get_attribute("class") or "")[:120]
                    skipped.append({"question": qtext[:300], "type": "unknown"})
                    debug.append(f"no inputs found; class={cls}")
            except Exception as exc:  # noqa: BLE001
                skipped.append({"question": qtext[:300], "type": "error"})
                debug.append(f"answer error: {str(exc)[:120]}")

            page.wait_for_timeout(700)  # let Canvas auto-save

            nxt = _find_next(page)
            if not nxt:
                debug.append("no Next button -> assuming last question")
                break
            try:
                nxt.click()
            except Exception as exc:  # noqa: BLE001
                debug.append(f"next click failed: {str(exc)[:80]}")
                break
            # Wait until the question actually changes.
            changed = False
            for _ in range(40):  # ~10s
                page.wait_for_timeout(250)
                if _current_qid(page) != qid:
                    changed = True
                    break
            if not changed:
                debug.append(f"page did not advance past {qid}")
                break

        if submit:
            submitted = _click_if_present(
                page,
                "#submit_quiz_button", "button#submit_quiz_button",
                "button:has-text('Submit Quiz')", "input[type=submit][value*='Submit']",
            )
            if submitted:
                time.sleep(1.5)

        return {"answered": answered, "skipped": skipped, "submitted": submitted, "debug": debug}
    finally:
        client.close()
