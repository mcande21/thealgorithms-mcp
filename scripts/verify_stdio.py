"""End-to-end verification: spawn the server over stdio, call every tool, assert correctness
against the LIVE TheAlgorithms/Python repo. Exits non-zero on any failure.

Run with:  uv run python scripts/verify_stdio.py
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{PASS if cond else FAIL}] {name}" + (f"  — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def payload(res):
    """Extract a tool's return value.

    FastMCP puts the structured value in `structuredContent`, wrapping list/scalar returns
    as {"result": ...}. Fall back to concatenating JSON text blocks.
    """
    sc = res.structuredContent
    if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
        return sc["result"]
    if sc is not None:
        return sc
    texts = [c.text for c in res.content if getattr(c, "type", None) == "text"]
    if len(texts) == 1:
        return json.loads(texts[0])
    return [json.loads(t) for t in texts]


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "thealgorithms_mcp.server"]
    )
    print("Spawning server over stdio...")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Server initialized over stdio.\n")

            # --- tool discovery ---
            tools = {t.name for t in (await session.list_tools()).tools}
            expected = {"list_categories", "search_algorithms", "get_category", "get_algorithm"}
            check("4 tools registered", tools == expected, f"{sorted(tools)}")

            # --- list_categories ---
            cats = payload(await session.call_tool("list_categories", {}))
            names = {c["category"] for c in cats}
            check("list_categories returns categories", len(cats) >= 40, f"{len(cats)} categories")
            check("categories include sorts/graphs/maths", {"sorts", "graphs", "maths"} <= names)

            # --- search_algorithms: top hit must be the canonical file ---
            cases = {
                "binary search": "searches/binary_search.py",
                "dijkstra": "graphs/dijkstra.py",
                "merge sort": "sorts/merge_sort.py",
                "knapsack": "dynamic_programming/knapsack.py",
            }
            for q, want in cases.items():
                res = payload(await session.call_tool("search_algorithms", {"query": q}))
                top = res[0]["path"] if res else "<none>"
                check(f"search {q!r} -> {want}", top == want, f"got {top}")

            # category-constrained search
            res = payload(
                await session.call_tool(
                    "search_algorithms", {"query": "quick", "category": "sorts"}
                )
            )
            check("scoped search stays in category", all(r["category"] == "sorts" for r in res))

            # --- get_category ---
            sorts = payload(await session.call_tool("get_category", {"category": "sorts"}))
            sort_paths = {e["path"] for e in sorts}
            check("get_category('sorts') lists sorts", "sorts/merge_sort.py" in sort_paths,
                  f"{len(sorts)} entries")

            # --- get_algorithm: source + doctests on a simple file ---
            ms = payload(await session.call_tool("get_algorithm", {"path": "sorts/merge_sort.py"}))
            check("get_algorithm returns source", "def merge_sort" in ms.get("source", ""))
            check("get_algorithm returns doctests", len(ms.get("doctests", [])) >= 1,
                  f"{len(ms.get('doctests', []))} examples")
            check("get_algorithm returns description", bool(ms.get("description")))
            check("get_algorithm has github_url", ms.get("github_url", "").startswith("https://github.com/"))

            # --- doctest extraction on a FUNCTION-HEAVY file (the flagged risk) ---
            bs = payload(await session.call_tool("get_algorithm", {"path": "searches/binary_search.py"}))
            check("function-level doctests extracted", len(bs.get("doctests", [])) >= 3,
                  f"{len(bs.get('doctests', []))} examples across functions")

            # --- include_source=False peek ---
            peek = payload(await session.call_tool(
                "get_algorithm", {"path": "sorts/merge_sort.py", "include_source": False}))
            check("peek omits source but keeps examples",
                  "source" not in peek and len(peek.get("doctests", [])) >= 1)

            # --- bad path is handled gracefully ---
            bad = payload(await session.call_tool("get_algorithm", {"path": "nope/not_real.py"}))
            check("bad path returns guidance, not crash", "error" in bad)

    print()
    if failures:
        print(f"\033[31m{len(failures)} FAILED:\033[0m {failures}")
        return 1
    print("\033[32mALL CHECKS PASSED\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
