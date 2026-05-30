"""Shared cached HTTP layer. Conditional GET (ETag) with on-disk cache + offline fallback."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import httpx
from platformdirs import user_cache_dir

CACHE_DIR = Path(user_cache_dir("thealgorithms-mcp"))
_BLOB_DIR = CACHE_DIR / "blobs"
USER_AGENT = "thealgorithms-mcp"


def _key(url: str) -> Path:
    return _BLOB_DIR / hashlib.sha256(url.encode()).hexdigest()


def github_headers() -> dict:
    """Auth header when GITHUB_TOKEN is set — raises the anonymous 60/hr API limit."""
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def cached_get(url: str, *, headers: dict | None = None, timeout: float = 30.0) -> tuple[int, str]:
    """GET with ETag revalidation against an on-disk cache.

    Returns (status_code, text). 304 and network failures both serve the cached body when
    present. status_code is 200 when fresh content (or a validated cache hit) is returned,
    or the upstream error code with empty text when there is nothing cached to fall back to.
    """
    body_file = _key(url)
    meta_file = _key(url).with_suffix(".meta")
    cached_body = body_file.read_text() if body_file.exists() else None
    etag = None
    if meta_file.exists():
        try:
            etag = json.loads(meta_file.read_text()).get("etag")
        except (json.JSONDecodeError, OSError):
            etag = None

    h = {"User-Agent": USER_AGENT, **(headers or {})}
    if etag:
        h["If-None-Match"] = etag

    try:
        resp = httpx.get(url, headers=h, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        if cached_body is not None:
            return 200, cached_body
        return -1, ""

    if resp.status_code == 304 and cached_body is not None:
        return 200, cached_body
    if resp.status_code != 200:
        if cached_body is not None:
            return 200, cached_body
        return resp.status_code, ""

    _BLOB_DIR.mkdir(parents=True, exist_ok=True)
    body_file.write_text(resp.text)
    meta_file.write_text(json.dumps({"etag": resp.headers.get("ETag")}))
    return 200, resp.text


def read_json_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def write_json_cache(path: Path, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
