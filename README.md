# thealgorithms-mcp

mcp-name: io.github.mcande21/thealgorithms-mcp

An [MCP](https://modelcontextprotocol.io) server for querying
[TheAlgorithms/Python](https://github.com/TheAlgorithms/Python) — search ~1,160 algorithm
implementations and fetch any one with its **doctests as usage examples**.

Hybrid design: the small `DIRECTORY.md` index is cached locally (ETag + 24h TTL) for instant
fuzzy search; file contents are fetched on demand from `raw.githubusercontent.com`. No API token,
no rate limits, tiny footprint. See [`DESIGN.md`](DESIGN.md).

## Tools

| Tool | Purpose |
|------|---------|
| `list_categories()` | Categories (sorts, graphs, dynamic_programming, …) with counts |
| `search_algorithms(query, category?, limit=10)` | Ranked `{name, category, path, score}` |
| `get_category(category)` | Every algorithm in a category |
| `get_algorithm(path, include_source=True)` | Source + extracted doctests for one file |

Typical flow: `search_algorithms("dijkstra")` → `get_algorithm("graphs/dijkstra.py")`.

## Install

**From PyPI (recommended):**

```json
{ "thealgorithms": { "command": "uvx", "args": ["thealgorithms-mcp"] } }
```

**From GitHub (no PyPI needed):**

```json
{ "thealgorithms": {
    "command": "uvx",
    "args": ["--from", "git+https://github.com/mcande21/thealgorithms-mcp", "thealgorithms-mcp"] } }
```

**From a local checkout (development):**

```bash
uv sync
uv run thealgorithms-mcp          # serves over stdio
```

```json
{ "thealgorithms": {
    "command": "uv",
    "args": ["run", "--directory", "/path/to/thealgorithms-mcp", "thealgorithms-mcp"] } }
```

Add any of the above to `~/.normandy-generic/mcp.json` (or your MCP client config).

## Verify

```bash
uv run python scripts/verify_stdio.py
```

Spawns the server over stdio and asserts every tool against the live repo.
