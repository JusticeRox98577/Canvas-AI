"""Parse Canvas page HTML into clean text + a list of embedded resources."""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup


@dataclass
class Embedded:
    kind: str  # "iframe" | "file" | "link"
    url: str
    title: str = ""


@dataclass
class ParsedPage:
    text: str
    embedded: list[Embedded] = field(default_factory=list)


def parse_page_html(html: str) -> ParsedPage:
    """Extract visible text and discover embedded/linked resources."""
    soup = BeautifulSoup(html or "", "html.parser")

    embedded: list[Embedded] = []
    for frame in soup.find_all("iframe"):
        src = frame.get("src")
        if src:
            embedded.append(Embedded("iframe", src, frame.get("title", "")))

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Canvas file links and external resources worth following.
        if "/files/" in href or href.startswith("http"):
            embedded.append(Embedded("file" if "/files/" in href else "link", href, a.get_text(strip=True)))

    text = soup.get_text(separator="\n", strip=True)
    return ParsedPage(text=text, embedded=embedded)
