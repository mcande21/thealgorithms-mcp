"""TheAlgorithms MCP server.

Four tools over stdio:
  list_categories()                      -> categories + counts (index only)
  search_algorithms(query, category?, limit) -> ranked file paths (index only)
  get_category(category)                 -> all entries in a category (index only)
  get_algorithm(path, include_source)    -> source + extracted doctests (on-demand fetch)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import index as idx
from . import fetch, parse, search

mcp = FastMCP("thealgorithms")


@mcp.tool()
def list_categories() -> list[dict]:
    """List the algorithm categories (e.g. sorts, graphs, dynamic_programming) with entry counts."""
    return idx.list_categories(idx.load_index())


@mcp.tool()
def search_algorithms(query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    """Search TheAlgorithms/Python by name/topic. Returns ranked {name, category, path, score}.

    Feed a returned `path` to get_algorithm to read the implementation. Optionally constrain
    to a `category` (see list_categories).
    """
    return search.search(idx.load_index(), query, category=category, limit=limit)


@mcp.tool()
def get_category(category: str) -> list[dict]:
    """List every algorithm in one category as {name, path}. Use for 'show me every sort'."""
    return idx.category_entries(idx.load_index(), category)


@mcp.tool()
def get_algorithm(path: str, include_source: bool = True) -> dict:
    """Fetch one algorithm by repo-relative path (e.g. 'sorts/merge_sort.py').

    Always returns the module description and extracted doctests (the usage examples).
    Set include_source=False for a cheap peek (description + examples, no body).
    Returns {path, github_url, description, doctests, line_count, source?}.
    """
    try:
        source = fetch.get_file(path)
    except FileNotFoundError:
        return {
            "error": f"No file at '{path}'. Call search_algorithms first to find the right path.",
            "path": path,
        }
    parsed = parse.parse_source(source)
    result = {
        "path": path,
        "github_url": idx.github_url(path),
        "description": parsed["description"],
        "doctests": parsed["doctests"],
        "line_count": parsed["line_count"],
    }
    if include_source:
        result["source"] = source
    return result


def main() -> None:
    """Console-script entry point. Runs over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
