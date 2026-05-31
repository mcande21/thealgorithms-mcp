# thealgorithms-mcp

mcp-name: io.github.mcande21/thealgorithms-mcp

An [MCP](https://modelcontextprotocol.io) server for querying the
[TheAlgorithms](https://github.com/TheAlgorithms) org across **every language repo** — search
algorithm implementations and fetch any one with its in-file examples.

Languages are **auto-discovered** from the org (not a hardcoded list): a repo is indexed when it
publishes a parseable `DIRECTORY.md` — currently **24 languages** (Python, Java, C++, JavaScript,
Rust, C, TypeScript, PHP, Dart, Kotlin, Ruby, R, Scala, Swift, Julia, Haskell, MATLAB, Zig,
Fortran, Nim, Clojure, F#, Jule, aarch64-assembly). Repos without a `DIRECTORY.md` (Go, C#, Lua,
Solidity, …) are reported by `list_languages` with their exclusion reason — no silent gaps.

Hybrid design: each repo's `DIRECTORY.md` index is cached locally (ETag + TTL); file contents are
fetched on demand from `raw.githubusercontent.com`. The org/language manifest is auto-discovered via
the GitHub API and cached 7 days. No token required (set `GITHUB_TOKEN` to raise the rate limit).
See [`DESIGN.md`](DESIGN.md).

## Tools

| Tool | Purpose |
|------|---------|
| `list_languages()` | Indexed languages (+ counts, aliases) and excluded repos with reasons |
| `list_categories(language='python')` | Categories with entry counts for a language |
| `search_algorithms(query, language='python', category?, limit=10)` | Ranked `{name, category, path, score}` |
| `get_category(category, language='python')` | Every algorithm in a category |
| `get_algorithm(path, language='python', include_source=True)` | Source + extracted examples |
| `compare(name, languages?, min_score=90, limit_per_language=1)` | Real matches across languages + `missing_in` |
| `suggest(prefix, language='python', limit=10)` | Trie-backed name autocomplete (`dij` → Dijkstra) |

`language` accepts names or aliases (`cpp`/`c++`, `js`, `ts`, …). Typical flow:
`search_algorithms("dijkstra", language="rust")` → `get_algorithm("src/graph/dijkstra.rs", language="rust")`.
Examples are extracted where the language has an in-file convention (Python doctests, Rust
doc-tests); other languages return source plus a note.

## Install

**From PyPI (recommended):**

```json
{ "thealgorithms": { "command": "uvx", "args": ["thealgorithms-mcp"] } }
```

**From GitHub:**

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

Add any of the above to `~/.normandy-generic/mcp.json` (or your MCP client config).

## Verify

```bash
uv run python scripts/verify_stdio.py                 # multi-language contract over stdio
uv run python scripts/verify_language.py rust         # one language, end-to-end
```

The harness spawns the server over stdio and asserts every tool against the live org, including
binary-search fetch across ≥8 languages and cross-language `compare()`.
