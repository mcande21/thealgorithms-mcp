# TheAlgorithms MCP — Design Spec

**Status:** reviewed + concepts validated — ready to build · **Date:** 2026-05-30 · **Owner:** mcande21

An MCP server that lets an LLM efficiently query [TheAlgorithms/Python](https://github.com/TheAlgorithms/Python)
for algorithm implementations and their built-in usage examples (doctests).

---

## 1. Goal & scope

- **Goal:** "query the system → get the implementation + examples" cheaply, mid-task, without the
  model burning tokens browsing GitHub.
- **Scope (v1):** Python repo only (**1,160 algorithms, 44 categories** — measured, not estimated;
  richest doctests in the org).
- **Storage model:** **Hybrid** — cache the small `DIRECTORY.md` index locally for instant fuzzy
  search; fetch file *contents* on-demand from raw GitHub. Tiny footprint, near-zero staleness.
- **Out of scope (v1):** other languages, semantic/embedding search, write access, running code.

## 2. Why this maps cleanly

- `DIRECTORY.md` is a free, pre-built index: `## Category` headers + `* [Name](path)` rows.
- Subcategory hierarchy lives in the path (`data_structures/binary_tree/avl_tree.py`) — **derive
  category from `path.split('/')[0]`**; ignore header depth. One regex parses the whole file.
- Every file is self-contained with a module docstring and **doctests (`>>>`)** — the usage
  examples ship *inside the source*, so we never synthesize examples.

## 3. Data sources

| What | URL |
|------|-----|
| Index | `https://raw.githubusercontent.com/TheAlgorithms/Python/master/DIRECTORY.md` |
| File  | `https://raw.githubusercontent.com/TheAlgorithms/Python/master/<path>` |

- Branch: `master`. Anonymous `raw.githubusercontent.com` (no token, no API rate limit).
- Responses carry an **ETag** → conditional `If-None-Match` GET returns `304` when unchanged.
  Cache validation costs ~0 bytes. **Verified empirically** (probe got a real ETag + a `304` on
  revalidation) — this overrides the review's claim that raw GitHub omits ETags. If GitHub ever
  drops the header, `fetch.py` falls back to the TTL timer (already specified), so we're safe either way.

## 4. Tools (the MCP surface)

The token-efficiency core: **search returns only paths + one-liners (cheap); full source is pulled
only on demand, and `get_algorithm` has a `mode` so the model can grab just the examples.**

### `list_categories() -> [{category, count}]`
Top-level categories with entry counts. Served from cached index.

### `search_algorithms(query: str, category?: str, limit: int = 10) -> [{name, category, path, score}]`
Fuzzy lexical rank over `name + category + path` tokens (rapidfuzz). No file fetches — index only.
Returns paths the model feeds to `get_algorithm`.

### `get_algorithm(path: str, include_source: bool = True) -> {...}`
On-demand fetch of one file (cached by path). Always returns the docstring + doctests together —
that's the common case (search → read implementation + its examples in one call). The review flagged
the original 3-mode enum as wrong-altitude: the model can't know whether a file has doctests before
fetching, so forcing an upfront `mode` choice causes wasted round-trips. Dropped.
- Returns `{path, github_url, docstring, doctests[], line_count, source?}`.
- `include_source=False` is the only knob — a cheap peek (docstring + examples, no body) for
  "is this the right file" disambiguation. Defaults to full.

### `get_category(category: str) -> [{name, path}]`  *(core, phase 1)*
All entries in one category — for "show me every sort." One-liner over the cached index
(`filter path.split('/')[0] == category`). Promoted from optional: without it the model can only
enumerate a category via a search query, which is awkward for "list everything in X."

## 5. Internals

```
src/thealgorithms_mcp/
  server.py   # FastMCP app, tool registration, stdio transport
  index.py    # fetch + parse + cache DIRECTORY.md  (ETag, TTL)
  fetch.py    # raw file fetch, cached by path (+commit/etag)
  search.py   # rapidfuzz ranking over the parsed index
  parse.py    # extract module docstring + doctest blocks from source
```

- **Index parse:** regex `^\s*\* \[(?P<name>.+?)\]\((?P<path>.+?\.py)\)$`; `category = path.split('/')[0]`.
  Measured **100% match rate** on the live file (1,160/1,160 lines, all `.py`, zero root-level paths).
  **Drift guard:** count matched vs. total `* [..](..)` lines; if match rate < 95% on a refresh, log
  loudly and keep the prior cached index rather than silently dropping entries.
- **Index cache:** `~/.cache/thealgorithms-mcp/directory.json` = `{entries, etag, fetched_at}`.
  Refresh on TTL miss (default 24h) via conditional GET; `304` → bump `fetched_at`, keep entries.
- **File cache:** `~/.cache/thealgorithms-mcp/files/<path>` keyed by path; revalidate via ETag.
- **Doctest extraction:** scan the **whole source** for `>>>` / `...` continuation lines + following
  expected-output lines, grouped into blocks. Verified this catches *every* doctest regardless of
  whether it lives in the module, a class, or a function docstring (probe found all 3 blocks in
  `merge_sort.py` via a flat source scan). This is simpler and more complete than walking the AST for
  per-node docstrings, which would miss nothing extra. Separately use `ast.get_docstring(module)` for
  the human-readable **description** field. (Review flagged module-only extraction as a bug — the
  whole-source scan is the fix, and it's less machinery than the AST-walk alternative proposed.)
- **Offline:** any fetch failure falls back to cache; tools degrade, never hard-crash.
- **Errors:** unknown `path` → error that suggests calling `search_algorithms` first.

## 6. Dependencies & runtime

- `mcp` (FastMCP), `httpx`, `rapidfuzz`, `platformdirs`. Stdlib `ast`/`re` for parsing.
- Python 3.11+. **stdio** transport (local).
- Register in `~/.normandy-generic/mcp.json`:
  ```json
  { "thealgorithms": { "command": "uvx", "args": ["thealgorithms-mcp"] } }
  ```

## 7. Build phases

1. **Index + search** — `index.py` (fetch/parse/cache + drift guard) + `search.py` +
   `list_categories` / `search_algorithms` / `get_category`. Verify ranking on real queries.
2. **Retrieval** — `fetch.py` + `parse.py` + `get_algorithm` (`include_source` toggle). Verify
   whole-source doctest extraction on a function-heavy file (not just `merge_sort`).
3. **Polish** — ETag revalidation (TTL fallback), offline degradation, README, `pyproject.toml`
   `uvx` entry point.

## 8. Open questions / future

- **v2 multi-language:** parameterize repo (`Python`→`Java`/`Rust`/…); add `compare(name)` for
  same-algorithm-across-languages. Index key becomes `(lang, path)`.
- **Semantic search:** only if lexical fuzzy proves insufficient (would shift toward the "full local
  clone + embeddings" model we deferred).
- **Normandy packaging:** could also wrap as a `/biking`-style skill instead of/alongside the MCP if
  we want it inside the framework's skill surface — decide after v1.

---

## Appendix A — Concept validation (probe, 2026-05-30)

Stdlib-only probe (`urllib` + `ast` + `difflib`) against the live repo. difflib stands in for
production rapidfuzz; urllib for httpx. All four load-bearing concepts passed:

| Concept | Result |
|---------|--------|
| **Parse `DIRECTORY.md`** | 200 OK, **1,160 entries / 44 categories** in 0.1s. 100% regex match, all `.py`, zero root-level paths. |
| **ETag conditional GET** | Real ETag returned; revalidation → **`304`**. Cache validation is free. |
| **Fetch + extract** | `sorts/merge_sort.py`: docstring present, 3 doctest blocks found via flat source scan. |
| **Fuzzy ranking** | Correct top hit for all of: binary search, dijkstra, knapsack, merge sort, lru cache. |

## Appendix B — Review dispositions (adversarial pass)

| # | Finding | Disposition |
|---|---------|-------------|
| 1 | "raw GitHub omits ETags; conditional GET is fiction" | **Rejected** — probe proves ETag + `304` work. TTL fallback kept as belt-and-suspenders. |
| 2 | DIRECTORY.md format edge cases (non-`.py`, root-level, nested parens) | **Downgraded** — none exist in live file (100% match). Kept the drift guard as cheap insurance. |
| 3 | `mode` enum is wrong-altitude for an LLM | **Accepted** — replaced with `include_source: bool`. |
| 4 | Doctest extraction misses function/class docstrings | **Accepted (simplified)** — whole-source `>>>` scan; proven complete. |
| 5 | `get_category` shouldn't be optional | **Accepted** — promoted to phase-1 core tool. |

---

## v0.2.0 — Multi-language (2026-05-30)

Expanded from Python-only to **every TheAlgorithms repo with a parseable `DIRECTORY.md`** —
**24 languages auto-discovered** (4,513 entries), not a hardcoded list.

### How the language set is discovered
`discovery.py` enumerates the org via the GitHub API (cached 7d; optional `GITHUB_TOKEN`), then
INCLUDES a repo iff its `DIRECTORY.md` parses to ≥10 source entries with a dominant code extension.
Everything else is recorded in `excluded` with a reason (no `DIRECTORY.md`: Go/C#/Lua/Solidity;
too few entries: Jupyter; not a code repo: website/Algorithms-Explanation). `list_languages`
surfaces both — **no silent gaps**.

### The format problem (recon finding)
A 25-repo parallel recon revealed the `DIRECTORY.md` dialect is **not** uniform — only Python/JS/PHP
use repo-relative paths. `directory.py` normalizes all dialects:
- absolute blob URLs (`https://github.com/.../blob/{ref}/<path>`) → `<path>` (Rust, C++, TS, …)
- `./` prefixes (PHP); URL-encoded paths (MATLAB); non-`*` bullets + emoji icons (Java)
- **category = the file's immediate parent directory** — uniform across languages, robust to
  boilerplate nesting (Java's `src/main/java/com/thealgorithms/<cat>/`, Rust's `src/<cat>/`);
  test files are dropped.

### Tools
All five original tools take a `language` param (default `python`, accepts aliases `cpp`/`c++`/`js`),
plus `list_languages()` and cross-language `compare(name)`.

### Examples (graceful degradation)
`parse.py` dispatches by language: Python doctests, Rust rustdoc doctests; every other language
returns source + an explicit note. Extensible registry.

### Verification
`verify_stdio.py` asserts the multi-language contract over stdio (binary search fetched across ≥8
languages, `compare()` across ≥3). `verify_language.py` checks one language end-to-end. A 24-agent
adversarial sweep + completeness critic confirmed 22/24 clean; the two flags were a verifier
artifact (Swift space-encoding) and an upstream `DIRECTORY.md` typo (Fortran) — neither a product
bug. One real fix shipped: `github_url`/fetch now percent-encode paths (`encode_path`) so URLs with
spaces/leading-slashes are browser-safe.

### Known limitations
- Categories for SPM-structured repos (Swift) include some source-dir noise — cosmetic.
- We faithfully parse upstream `DIRECTORY.md`; a broken upstream link (e.g. one Fortran entry) 404s
  on fetch by design rather than being silently dropped.

---

## v0.3.0 — Self-improvement via dogfooding (2026-05-30)

Two changes found by *using* the tool to query TheAlgorithms for ways to improve itself:

- **`compare()` precision.** Dogfooding `compare("dijkstra")` returned a row for all 24 languages —
  including 11 that don't implement it (scored ~50 noise). Now filtered to `score >= min_score`
  (default 90); real matches go in `matches`/`found_in`, languages without one in `missing_in`.
  `compare("dijkstra")` → found in 11, missing in 13.
- **`suggest()` autocomplete.** New Trie-backed typeahead (`autocomplete.py`), modeled on the repo's
  own `data_structures/trie/trie.py` — the MCP that indexes TheAlgorithms is now powered by one of
  its algorithms. Indexes each name + its words; O(prefix-length) lookup; built once per language.
</content>
</invoke>
