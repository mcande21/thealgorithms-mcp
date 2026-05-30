"""Auto-discover which TheAlgorithms repos are indexable language repos.

The language SET is never hardcoded: we enumerate the org via the GitHub API, then INCLUDE a
repo iff it publishes a DIRECTORY.md that parses to a healthy number of source entries with a
dominant code extension. Everything else is excluded with a recorded reason (no DIRECTORY.md,
too few parseable entries, not a code repo). The manifest is cached 7 days.
"""
from __future__ import annotations

import time

from . import directory
from .http import (
    CACHE_DIR,
    cached_get,
    github_headers,
    read_json_cache,
    write_json_cache,
)

ORG = "TheAlgorithms"
ORG_REPOS_URL = f"https://api.github.com/orgs/{ORG}/repos?per_page=100&type=sources"
MANIFEST_FILE = CACHE_DIR / "manifest.json"
TTL_SECONDS = 7 * 24 * 3600
MIN_ENTRIES = 10  # below this a DIRECTORY.md isn't a real algorithm index (filters Jupyter et al.)

# Friendly aliases only — NOT the source of truth for which repos exist (that's discovery).
_ALIASES = {
    "c-plus-plus": ("cpp", ["c++", "cplusplus", "cpp"]),
    "c-sharp": ("csharp", ["c#", "csharp"]),
    "matlab-octave": ("matlab", ["octave", "matlab"]),
    "javascript": ("javascript", ["js"]),
    "typescript": ("typescript", ["ts"]),
}

_memo: dict | None = None


def lang_key(repo: str) -> str:
    low = repo.lower()
    return _ALIASES[low][0] if low in _ALIASES else low


def _aliases(repo: str) -> list[str]:
    low = repo.lower()
    al = {lang_key(repo), low}
    if low in _ALIASES:
        al.update(_ALIASES[low][1])
    return sorted(al)


def raw_base(repo: str, branch: str) -> str:
    return f"https://raw.githubusercontent.com/{ORG}/{repo}/{branch}/"


def _list_org_repos() -> list[dict]:
    """[{name, default_branch}] across all pages, or [] if the API is unreachable."""
    repos: list[dict] = []
    url = ORG_REPOS_URL
    for _ in range(10):  # page cap
        code, text = cached_get(url, headers={**github_headers(), "Accept": "application/vnd.github+json"})
        if code != 200 or not text:
            break
        import json
        try:
            page = json.loads(text)
        except json.JSONDecodeError:
            break
        for r in page:
            if not r.get("archived") and not r.get("fork"):
                repos.append({"name": r["name"], "branch": r.get("default_branch", "master")})
        if len(page) < 100:
            break
        url = ORG_REPOS_URL + f"&page={len(repos) // 100 + 1}"
    return repos


def _classify(repo: str, branch: str) -> dict:
    """Decide include/exclude for one repo by fetching + parsing its DIRECTORY.md."""
    code, text = cached_get(raw_base(repo, branch) + "DIRECTORY.md")
    if code != 200 or not text:
        return {"include": False, "reason": f"no DIRECTORY.md published (HTTP {code})"}
    entries = directory.parse_directory(text)
    if len(entries) < MIN_ENTRIES:
        return {"include": False, "reason": f"DIRECTORY.md parses to only {len(entries)} source entries"}
    ext = directory.dominant_extension(entries)
    if not ext:
        return {"include": False, "reason": "no dominant source extension in DIRECTORY.md"}
    return {"include": True, "extension": ext, "count": len(entries)}


def discover(force: bool = False) -> dict:
    """Return the language manifest, refreshing from the org when stale.

    manifest = {
      "languages": {key: {repo, branch, extension, count, aliases, raw_base}},
      "excluded": [{repo, reason}],
      "fetched_at": float,
    }
    """
    global _memo
    now = time.time()
    cache = read_json_cache(MANIFEST_FILE)

    if not force and _memo and now - _memo["fetched_at"] < TTL_SECONDS:
        return _memo
    if not force and cache and now - cache.get("fetched_at", 0) < TTL_SECONDS:
        _memo = cache
        return cache

    repos = _list_org_repos()
    if not repos:  # API unavailable
        if cache:
            _memo = cache
            return cache
        raise RuntimeError(
            "Cannot reach the GitHub API to discover repos and no cached manifest exists. "
            "Retry, or set GITHUB_TOKEN to avoid anonymous rate limits."
        )

    languages: dict[str, dict] = {}
    excluded: list[dict] = []
    for r in sorted(repos, key=lambda x: x["name"]):
        verdict = _classify(r["name"], r["branch"])
        if verdict["include"]:
            languages[lang_key(r["name"])] = {
                "repo": r["name"],
                "branch": r["branch"],
                "extension": verdict["extension"],
                "count": verdict["count"],
                "aliases": _aliases(r["name"]),
                "raw_base": raw_base(r["name"], r["branch"]),
            }
        else:
            excluded.append({"repo": r["name"], "reason": verdict["reason"]})

    manifest = {"languages": languages, "excluded": excluded, "fetched_at": now}
    write_json_cache(MANIFEST_FILE, manifest)
    _memo = manifest
    return manifest


def resolve_language(name: str) -> str | None:
    """Map a user-supplied language name/alias to a manifest key, or None if unknown."""
    manifest = discover()
    q = name.strip().lower()
    if q in manifest["languages"]:
        return q
    for key, info in manifest["languages"].items():
        if q == key or q in info.get("aliases", []):
            return key
    return None
