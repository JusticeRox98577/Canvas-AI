"""Extract text from downloaded documents (PDF, DOCX)."""

from __future__ import annotations

from pathlib import Path


def extract_text(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf(path)
    if suffix in {".docx"}:
        return _docx(path)
    if suffix in {".txt", ".md", ".html"}:
        return path.read_text(errors="ignore")
    return f"[unsupported file type: {suffix}]"


def _pdf(path: Path) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)
