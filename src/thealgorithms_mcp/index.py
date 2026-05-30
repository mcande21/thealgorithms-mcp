"""Per-language algorithm index: load + cache a repo's parsed DIRECTORY.md on demand."""
from __future__ import annotations

from urllib.parse import quote

from . import directory, discovery
from .http import cached_get

ORG = discovery.ORG

# Process-lifetime memo of parsed indexes, keyed by language.
_entries_memo: dict[str, list[dict]] = {}


def encode_path(path: str) -> str:
    """Strip a leading slash and percent-encode so URLs are browser/curl-safe.

    Paths in the index are stored decoded (see directory.py), so spaces/unicode must be
    re-encoded here; safe='/' keeps separators. Plain ASCII paths are unchanged.
    """
    return quote(path.lstrip("/"), safe="/")


def github_url(language: str, path: str) -> str:
    info = discovery.discover()["languages"][language]
    return f"https://github.com/{ORG}/{info['repo']}/blob/{info['branch']}/{encode_path(path)}"


def load_index(language: str) -> list[dict]:
    """Return the parsed entries for one language. Raises KeyError for unknown languages."""
    if language in _entries_memo:
        return _entries_memo[language]
    info = discovery.discover()["languages"][language]
    code, text = cached_get(info["raw_base"] + "DIRECTORY.md")
    if code != 200 or not text:
        raise RuntimeError(f"Could not fetch DIRECTORY.md for {language} ({info['repo']})")
    entries = directory.parse_directory(text)
    _entries_memo[language] = entries
    return entries


def list_categories(entries: list[dict]) -> list[dict]:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    return [{"category": c, "count": n} for c, n in sorted(counts.items())]


def category_entries(entries: list[dict], category: str) -> list[dict]:
    cl = category.lower()
    return [
        {"name": e["name"], "path": e["path"]}
        for e in entries
        if e["category"].lower() == cl
    ]
