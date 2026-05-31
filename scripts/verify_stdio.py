"""End-to-end verification: spawn the server over stdio, exercise every tool against the LIVE
TheAlgorithms org. Asserts the multi-language contract. Exits non-zero on any failure.

  uv run python scripts/verify_stdio.py
  uv run python scripts/verify_stdio.py uvx --from thealgorithms-mcp thealgorithms-mcp
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PASS, FAIL = "\033[32mPASS\033[0m", "\033[31mFAIL\033[0m"
failures: list[str] = []

# Languages we expect to carry a binary search (representative spread of formats/structures).
BINSEARCH_LANGS = [
    "python", "java", "cpp", "javascript", "rust", "c", "typescript", "php",
    "ruby", "swift", "kotlin", "scala", "julia", "haskell", "dart", "r",
]


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{PASS if cond else FAIL}] {name}" + (f"  — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def payload(res):
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
    if len(sys.argv) > 1:
        command, args = sys.argv[1], sys.argv[2:]
    else:
        command, args = sys.executable, ["-m", "thealgorithms_mcp.server"]
    params = StdioServerParameters(command=command, args=args)
    print(f"Spawning server over stdio: {command} {' '.join(args)}\n")

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def call(tool, **kw):
                return payload(await session.call_tool(tool, kw))

            # --- tool discovery ---
            tools = {t.name for t in (await session.list_tools()).tools}
            expected = {"list_languages", "list_categories", "search_algorithms",
                        "get_category", "get_algorithm", "compare", "suggest"}
            check("7 tools registered", tools == expected, f"{sorted(tools)}")

            # --- list_languages: auto-discovered set + explicit exclusions ---
            langs_info = await call("list_languages")
            keys = {l["language"] for l in langs_info["languages"]}
            check("list_languages discovers >= 15 languages", len(keys) >= 15, f"{len(keys)} langs")
            check("excluded repos reported with reasons", len(langs_info["excluded"]) > 0,
                  f"{len(langs_info['excluded'])} excluded")
            go = [e for e in langs_info["excluded"] if e["repo"] == "Go"]
            check("Go excluded explicitly (no silent gap)", bool(go and go[0].get("reason")),
                  go[0]["reason"] if go else "Go not in excluded")

            # --- binary search: found + fetched with real source across many languages ---
            ok_langs = []
            for lang in BINSEARCH_LANGS:
                if lang not in keys:
                    continue
                hits = await call("search_algorithms", query="binary search", language=lang, limit=3)
                hit = next((h for h in hits if "binary" in h["path"].lower()), hits[0] if hits else None)
                if not hit:
                    continue
                algo = await call("get_algorithm", path=hit["path"], language=lang)
                src = algo.get("source", "")
                if len(src) > 80 and algo.get("github_url", "").startswith("https://github.com/"):
                    ok_langs.append(lang)
            check("binary search fetched with real source across >= 8 languages",
                  len(ok_langs) >= 8, f"{len(ok_langs)}: {ok_langs}")

            # symbol + acronym search guards (regressions the 0.2.0 rewrite had dropped)
            astar = await call("search_algorithms", query="A*", language="python", limit=1)
            check("search 'A*' -> a_star (symbol handling)",
                  bool(astar) and "a_star" in astar[0]["path"], astar[0]["path"] if astar else "none")
            gcd = await call("search_algorithms", query="gcd", language="python", limit=1)
            check("search 'gcd' -> greatest_common_divisor (acronym)",
                  bool(gcd) and "greatest_common_divisor" in gcd[0]["path"],
                  gcd[0]["path"] if gcd else "none")

            # --- Python doctests extracted ---
            py = await call("get_algorithm", path="sorts/merge_sort.py", language="python")
            check("python extracts doctests", len(py.get("examples", [])) >= 1,
                  f"{len(py.get('examples', []))} examples")

            # --- graceful degradation: a non-extractor language returns note + real source ---
            if "java" in keys:
                jhits = await call("search_algorithms", query="binary search", language="java", limit=3)
                jhit = next((h for h in jhits if "binary" in h["path"].lower()), jhits[0])
                jalgo = await call("get_algorithm", path=jhit["path"], language="java")
                check("non-extractor language degrades gracefully (note + source)",
                      jalgo.get("note") and jalgo.get("examples") == [] and len(jalgo.get("source", "")) > 80,
                      f"note={'y' if jalgo.get('note') else 'n'}")

            # --- Rust doc-test extraction (the second extractor) ---
            if "rust" in keys:
                found_rust_ex = False
                for q in ["hamming distance", "binary shifts", "binary coded decimal", "two sum"]:
                    rh = await call("search_algorithms", query=q, language="rust", limit=1)
                    if rh:
                        ra = await call("get_algorithm", path=rh[0]["path"], language="rust")
                        if len(ra.get("examples", [])) >= 1:
                            found_rust_ex = True
                            break
                check("rust extracts doc-test examples", found_rust_ex)

            # --- cross-language compare (precision: only real matches) ---
            cmp = await call("compare", name="binary search")
            check("compare() finds binary search in >= 8 languages",
                  len(cmp["found_in"]) >= 8, f"found_in={len(cmp['found_in'])}")
            check("compare() matches all clear the score threshold",
                  all(mt["score"] >= cmp["min_score"] for mt in cmp["matches"]))
            # an algorithm many languages lack -> missing_in must be populated (the precision fix)
            dij = await call("compare", name="dijkstra")
            check("compare() reports missing_in for sparse algorithms",
                  len(dij["missing_in"]) > 0 and len(dij["found_in"]) >= 8,
                  f"found={len(dij['found_in'])} missing={len(dij['missing_in'])}")
            # coverage damping: a generic 'Tree' must NOT count as a 'red black tree' match
            rbt = await call("compare", name="red black tree")
            check("compare() coverage-damps generic names (no 'Tree' as red-black-tree)",
                  "python" in rbt["found_in"] and "cpp" not in rbt["found_in"] and "swift" not in rbt["found_in"],
                  f"found_in={rbt['found_in']}")

            # --- Trie autocomplete ---
            sug = await call("suggest", prefix="dij", language="python")
            check("suggest('dij') returns Dijkstra", any("dijkstra" in s["name"].lower() for s in sug),
                  f"{[s['name'] for s in sug][:4]}")
            sug2 = await call("suggest", prefix="merge", language="python")

            def _matches_prefix(name: str, pfx: str) -> bool:
                return name.lower().startswith(pfx) or any(w.startswith(pfx) for w in name.lower().split())

            check("suggest results actually start with the prefix",
                  bool(sug2) and all(_matches_prefix(s["name"], "merge") for s in sug2))
            sug3 = await call("suggest", prefix="dij", language="rust")
            check("suggest works for a non-python language (rust)",
                  any("dijkstra" in s["name"].lower() for s in sug3))

            # --- per-language tools + ergonomics ---
            cats = await call("list_categories", language="cpp")
            check("list_categories works for a non-python language (cpp)", len(cats) >= 5,
                  f"{len(cats)} categories")
            alias = await call("search_algorithms", query="dijkstra", language="c++")
            check("language aliases resolve (c++ -> cpp)", isinstance(alias, list) and len(alias) >= 1)
            sortcat = await call("get_category", category="sorts", language="python")
            check("get_category('sorts', python)", any("merge_sort" in e["path"] for e in sortcat))
            bad = await call("get_algorithm", path="nope/x.py", language="python")
            check("bad path returns guidance", "error" in bad)
            badlang = await call("search_algorithms", query="x", language="cobol")
            check("unknown language returns guidance", isinstance(badlang, dict) and "error" in badlang)

    print()
    if failures:
        print(f"\033[31m{len(failures)} FAILED:\033[0m {failures}")
        return 1
    print("\033[32mALL CHECKS PASSED\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
