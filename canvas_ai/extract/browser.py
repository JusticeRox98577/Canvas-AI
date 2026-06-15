"""Playwright fallback for embedded iframe/LTI content the API can't reach.

Optional: requires `pip install -e .[browser]` and `playwright install chromium`.
Kept lazy so the core tool runs without a browser installed.
"""

from __future__ import annotations


def extract_iframe_text(url: str, *, timeout_ms: int = 15000) -> str:
    """Load a URL in a headless browser and return its visible text."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "[browser extras not installed: pip install -e .[browser]]"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            return page.inner_text("body")
        finally:
            browser.close()
