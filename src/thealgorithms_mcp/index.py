"""Fetch, parse, and cache TheAlgorithms/Python DIRECTORY.md.

Hybrid model: the index is small (~1,160 entries) so we cache it whole, validated by
ETag with a 24h TTL fallback. File *contents* are fetched on demand (see fetch.py).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx
from platformdirs import user_cache_dir

REPO = "TheAlgorithms/Python"
BRANCH = "master"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
DIRECTORY_URL = RAW_BASE + "DIRECTORY.md"
TTL_SECONDS = 24 * 3600
DRIFT_THRESHOLD = 0.95  # keep prior cache if a refresh matches fewer than this fraction of links

CACHE_DIR = Path(user_cache_dir("thealgorithms-mcp"))
INDEX_FILE = CACHE_DIR / "directory.json"

ENTRY_RE = re.compile(r"^\s*\* \[(?P<name>.+?)\]\((?P<path>.+?\.py)\)\s*$")
LINK_RE = re.compile(r"^\s*\* \[.+?\]\(.+?\)\s*$")

# Process-lifetime memo so repeated tool calls don't re-read disk.
_memo: dict | None = None


def github_url(path: str) -> str:
    """Human-facing blob URL for a repo-relative path."""
    return f"https://github.com/{REPO}/blob/{BRANCH}/{path}"


def _parse(text: str) -> tuple[list[dict], float]:
    """Parse DIRECTORY.md into entries; return (entries, match_rate vs all link lines)."""
    link_lines = 0
    entries: list[dict] = []
    for line in text.splitlines():
        if LINK_RE.match(line):
            link_lines += 1
        m = ENTRY_RE.match(line)
        if m:
            path = m.group("path")
            entries.append(
                {"name": m.group("name"), "path": path, "category": path.split("/")[0]}
            )
    match_rate = (len(entries) / link_lines) if link_lines else 1.0
    return entries, match_rate


def _read_cache() -> dict | None:
    if not INDEX_FILE.exists():
        return None
    try:
        return json.loads(INDEX_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(data))


def load_index(force: bool = False) -> list[dict]:
    """Return the parsed index, refreshing from GitHub when stale.

    Order of operations:
      1. Serve the process memo if present and fresh (and not forced).
      2. Serve the disk cache if fresh.
      3. Conditional GET (If-None-Match). 304 -> reuse cached entries, bump timestamp.
         200 -> parse, apply drift guard, persist.
      4. Any network failure -> fall back to cached entries (offline degradation).
    """
    global _memo
    now = time.time()
    cache = _read_cache()

    if not force and _memo and (now - _memo["fetched_at"] < TTL_SECONDS):
        return _memo["entries"]
    if not force and cache and (now - cache.get("fetched_at", 0) < TTL_SECONDS):
        _memo = cache
        return cache["entries"]

    headers = {"User-Agent": "thealgorithms-mcp"}
    if cache and cache.get("etag"):
        headers["If-None-Match"] = cache["etag"]

    try:
        resp = httpx.get(DIRECTORY_URL, headers=headers, timeout=30, follow_redirects=True)
    except httpx.HTTPError:
        if cache:
            _memo = cache
            return cache["entries"]  # offline: stale is better than dead
        raise

    if resp.status_code == 304 and cache:
        cache["fetched_at"] = now
        _write_cache(cache)
        _memo = cache
        return cache["entries"]

    resp.raise_for_status()
    entries, match_rate = _parse(resp.text)

    # Drift guard: a sudden drop in match rate means the format changed under us.
    if match_rate < DRIFT_THRESHOLD and cache and cache.get("entries"):
        # Keep the known-good index rather than silently shipping a broken one.
        cache["fetched_at"] = now
        _write_cache(cache)
        _memo = cache
        return cache["entries"]

    data = {
        "entries": entries,
        "etag": resp.headers.get("ETag"),
        "fetched_at": now,
        "match_rate": match_rate,
    }
    _write_cache(data)
    _memo = data
    return entries


def list_categories(entries: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    return [{"category": c, "count": n} for c, n in sorted(counts.items())]


def category_entries(entries: list[dict], category: str) -> list[dict]:
    return [
        {"name": e["name"], "path": e["path"]}
        for e in entries
        if e["category"] == category
    ]
