"""Thin Canvas REST API client with pagination and gentle rate limiting."""

from __future__ import annotations

import time
from typing import Any, Iterator

import httpx

from canvas_ai.config import Config


class CanvasError(RuntimeError):
    """Raised when the Canvas API returns an error."""


class CanvasClient:
    """Minimal wrapper around the Canvas REST API.

    Handles auth, Link-header pagination, and backs off when Canvas signals
    that we're approaching its rate limit (the ``X-Rate-Limit-Remaining`` header).
    """

    def __init__(self, config: Config, *, timeout: float = 30.0):
        self._base = f"{config.canvas_base_url}/api/v1"
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {config.canvas_token}"},
            timeout=timeout,
        )

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CanvasClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- core requests ---------------------------------------------------
    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = path if path.startswith("http") else f"{self._base}{path}"
        resp = self._client.request(method, url, **kwargs)
        self._respect_rate_limit(resp)
        if resp.status_code >= 400:
            raise CanvasError(f"{method} {url} -> {resp.status_code}: {resp.text[:500]}")
        return resp

    @staticmethod
    def _respect_rate_limit(resp: httpx.Response) -> None:
        remaining = resp.headers.get("X-Rate-Limit-Remaining")
        if remaining is not None:
            try:
                if float(remaining) < 50:
                    time.sleep(1.0)
            except ValueError:
                pass

    # -- public verbs ----------------------------------------------------
    def get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params=params or None).json()

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs).json()

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs).json()

    def paginate(self, path: str, **params: Any) -> Iterator[dict]:
        """Yield every item across all pages of a list endpoint."""
        params.setdefault("per_page", 100)
        url: str | None = path
        first = True
        while url:
            resp = self._request("GET", url, params=params if first else None)
            first = False
            data = resp.json()
            if isinstance(data, list):
                yield from data
            else:  # some endpoints wrap results
                yield data
            url = self._next_link(resp)

    @staticmethod
    def _next_link(resp: httpx.Response) -> str | None:
        link = resp.headers.get("Link", "")
        for part in link.split(","):
            section = part.split(";")
            if len(section) < 2:
                continue
            if 'rel="next"' in section[1]:
                return section[0].strip().strip("<>")
        return None
