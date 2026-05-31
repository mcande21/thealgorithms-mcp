"""TheAlgorithms MCP server — multi-language.

Tools (all language-aware; `language` accepts names or aliases like 'cpp', 'js', 'c++'):
  list_languages()                                  -> indexed languages + excluded repos w/ reasons
  list_categories(language)                         -> categories + counts for one language
  search_algorithms(query, language, category?, limit) -> ranked file paths
  get_category(category, language)                  -> all entries in a category
  get_algorithm(path, language, include_source)     -> source + extracted examples
  compare(name, languages?, limit_per_language)     -> the same algorithm across languages
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import autocomplete, discovery
from . import fetch
from . import index as idx
from . import parse, search

mcp = FastMCP("thealgorithms")

DEFAULT_LANGUAGE = "python"


def _resolve(language: str) -> tuple[str | None, dict | None]:
    """Return (key, None) or (None, error-dict) for an unknown language."""
    key = discovery.resolve_language(language)
    if key is None:
        avail = sorted(discovery.discover()["languages"])
        return None, {
            "error": f"Unknown language '{language}'. Call list_languages for options.",
            "available": avail,
        }
    return key, None


@mcp.tool()
def list_languages() -> dict:
    """List indexed languages (auto-discovered from the TheAlgorithms org) and excluded repos.

    Returns {languages: [{language, repo, count, aliases}], excluded: [{repo, reason}]}.
    Use a returned `language` (or any alias) with the other tools.
    """
    m = discovery.discover()
    langs = [
        {"language": k, "repo": v["repo"], "count": v["count"], "aliases": v["aliases"]}
        for k, v in sorted(m["languages"].items())
    ]
    return {"languages": langs, "count": len(langs), "excluded": m["excluded"]}


@mcp.tool()
def list_categories(language: str = DEFAULT_LANGUAGE) -> list[dict] | dict:
    """List the algorithm categories with entry counts for a language (default: python)."""
    key, err = _resolve(language)
    if err:
        return err
    return idx.list_categories(idx.load_index(key))


@mcp.tool()
def search_algorithms(
    query: str, language: str = DEFAULT_LANGUAGE, category: str | None = None, limit: int = 10
) -> list[dict] | dict:
    """Search one language's algorithms by name/topic. Returns ranked {name, category, path, score}.

    Feed a returned `path` (with the same `language`) to get_algorithm. `language` defaults to
    python and accepts aliases (cpp, js, ts, c++, ...). See list_languages.
    """
    key, err = _resolve(language)
    if err:
        return err
    return search.search(idx.load_index(key), query, category=category, limit=limit)


@mcp.tool()
def get_category(category: str, language: str = DEFAULT_LANGUAGE) -> list[dict] | dict:
    """List every algorithm in one category (for a language) as {name, path}."""
    key, err = _resolve(language)
    if err:
        return err
    return idx.category_entries(idx.load_index(key), category)


@mcp.tool()
def get_algorithm(
    path: str, language: str = DEFAULT_LANGUAGE, include_source: bool = True
) -> dict:
    """Fetch one algorithm by language + repo-relative path (e.g. path='sorts/merge_sort.py').

    Returns {language, path, github_url, description, examples, line_count, source?}. Examples are
    extracted where the language has an in-file convention (Python doctests, Rust doc-tests),
    otherwise empty with a `note`. Set include_source=False for a cheap peek.
    """
    key, err = _resolve(language)
    if err:
        return err
    try:
        source = fetch.get_file(key, path)
    except FileNotFoundError:
        return {
            "error": f"No file at '{path}' in {key}. Call search_algorithms first.",
            "language": key,
            "path": path,
        }
    parsed = parse.parse_source(source, key)
    result = {
        "language": key,
        "path": path,
        "github_url": idx.github_url(key, path),
        "description": parsed.get("description", ""),
        "examples": parsed.get("examples", []),
        "line_count": parsed["line_count"],
    }
    if "note" in parsed:
        result["note"] = parsed["note"]
    if include_source:
        result["source"] = source
    return result


@mcp.tool()
def compare(
    name: str,
    languages: list[str] | None = None,
    min_score: float = 90.0,
    limit_per_language: int = 1,
) -> dict:
    """Find the same algorithm across languages — returns only REAL matches.

    A per-language search scores 100-200 for a genuine match and well below for "nearest unrelated
    thing", so results are filtered to score >= `min_score` (default 90). Languages with no real
    match are listed in `missing_in`, so you can see at a glance which languages implement an
    algorithm and which don't. `languages` defaults to all indexed; pass a subset to narrow.
    """
    m = discovery.discover()
    if languages:
        keys = [k for lang in languages if (k := discovery.resolve_language(lang))]
        if not keys:
            return {"error": "None of the requested languages are indexed.", "requested": languages}
    else:
        keys = sorted(m["languages"])

    matches: list[dict] = []
    missing_in: list[str] = []
    for key in keys:
        hits = search.search(idx.load_index(key), name, limit=max(1, limit_per_language))
        kept = [h for h in hits[:limit_per_language] if h["score"] >= min_score]
        if not kept:
            missing_in.append(key)
            continue
        for h in kept:
            matches.append(
                {
                    "language": key,
                    "name": h["name"],
                    "category": h["category"],
                    "path": h["path"],
                    "github_url": idx.github_url(key, h["path"]),
                    "score": h["score"],
                }
            )
    return {
        "query": name,
        "min_score": min_score,
        "languages_searched": len(keys),
        "found_in": sorted({mt["language"] for mt in matches}),
        "missing_in": missing_in,
        "matches": matches,
    }


@mcp.tool()
def suggest(prefix: str, language: str = DEFAULT_LANGUAGE, limit: int = 10) -> list[dict] | dict:
    """Autocomplete algorithm names by prefix (Trie-backed typeahead).

    Matches the start of the name or any word: 'dij' -> Dijkstra, 'search' -> Binary Search.
    Returns up to `limit` {name, category, path}. Fast O(prefix-length) lookup.
    """
    key, err = _resolve(language)
    if err:
        return err
    return autocomplete.suggest(key, idx.load_index(key), prefix, limit)


def main() -> None:
    """Console-script entry point. Runs over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
