"""Resolve a discovered embedded resource into text.

Routing:
  - Canvas file  -> download + document extraction
  - iframe/link  -> browser fallback (YouTube/Docs/LTI tools)
"""

from __future__ import annotations

from canvas_ai.canvas.client import CanvasClient
from canvas_ai.canvas import files as files_api
from canvas_ai.extract import documents
from canvas_ai.extract.browser import extract_iframe_text
from canvas_ai.extract.html import Embedded


def resolve(client: CanvasClient, item: Embedded) -> str:
    if item.kind == "file" and "/files/" in item.url:
        file_id = item.url.rstrip("/").split("/files/")[-1].split("/")[0].split("?")[0]
        try:
            meta = client.get(f"/files/{file_id}")
            local = files_api.download(client, meta)
            return documents.extract_text(local)
        except Exception as exc:  # noqa: BLE001 - best-effort extraction
            return f"[could not extract file {file_id}: {exc}]"
    # iframe / external link
    return extract_iframe_text(item.url)
