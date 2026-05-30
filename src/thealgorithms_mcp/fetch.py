"""On-demand fetch of a single algorithm file's source, cached by path + ETag."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from .index import CACHE_DIR, RAW_BASE

FILE_CACHE_DIR = CACHE_DIR / "files"


def _cache_paths(path: str) -> tuple[Path, Path]:
    safe = path.replace("/", "__")
    return FILE_CACHE_DIR / safe, FILE_CACHE_DIR / (safe + ".meta")


def get_file(path: str) -> str:
    """Return raw source for a repo-relative path.

    Conditional GET via ETag; 304 reuses the cached body. Network failures fall back to
    cache when present, else raise. Raises FileNotFoundError on a 404 (bad path).
    """
    body_file, meta_file = _cache_paths(path)
    etag = None
    cached_body = None
    if body_file.exists():
        cached_body = body_file.read_text()
        if meta_file.exists():
            try:
                etag = json.loads(meta_file.read_text()).get("etag")
            except (json.JSONDecodeError, OSError):
                etag = None

    headers = {"User-Agent": "thealgorithms-mcp"}
    if etag:
        headers["If-None-Match"] = etag

    try:
        resp = httpx.get(RAW_BASE + path, headers=headers, timeout=30, follow_redirects=True)
    except httpx.HTTPError:
        if cached_body is not None:
            return cached_body
        raise

    if resp.status_code == 304 and cached_body is not None:
        return cached_body
    if resp.status_code == 404:
        raise FileNotFoundError(path)
    resp.raise_for_status()

    FILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    body_file.write_text(resp.text)
    meta_file.write_text(json.dumps({"etag": resp.headers.get("ETag")}))
    return resp.text
