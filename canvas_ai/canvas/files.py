"""Canvas file upload (the 3-step upload flow) and download."""

from __future__ import annotations

from pathlib import Path

import httpx

from canvas_ai.canvas.client import CanvasClient


def download(client: CanvasClient, file_obj: dict, dest_dir: str = "downloads") -> Path:
    """Download a Canvas file object (must contain a 'url') to disk."""
    url = file_obj["url"]
    name = file_obj.get("display_name") or file_obj.get("filename") or "file"
    out = Path(dest_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    with httpx.stream("GET", url) as resp:
        resp.raise_for_status()
        with open(path, "wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    return path


def upload_to_course(client: CanvasClient, course_id: int, local_path: str) -> dict:
    """Upload a local file into a course's Files area via Canvas's 3-step flow.

    Used for media/document uploads referenced by submissions or pages.
    """
    path = Path(local_path)
    # Step 1: tell Canvas about the upload, get a target + signed params.
    init = client.post(
        f"/courses/{course_id}/files",
        data={"name": path.name, "size": path.stat().st_size},
    )
    # Step 2: POST the bytes to the returned upload URL (no auth header).
    with open(path, "rb") as fh:
        files = {"file": (path.name, fh)}
        resp = httpx.post(init["upload_url"], data=init.get("upload_params", {}), files=files)
        resp.raise_for_status()
    # Step 3: confirm (Canvas returns 201 + Location, or the file json directly).
    if resp.status_code in (301, 302) and "Location" in resp.headers:
        return client.get(resp.headers["Location"])
    return resp.json()
