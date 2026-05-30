"""Deterministic end-to-end check for ONE language. Prints a JSON verdict.
Usage: uv run python scripts/verify_language.py <language-key>
Checks: index loads, a sample algorithm fetches real source, its github_url resolves (HTTP 200),
search returns results, categories are non-trivial.
"""
from __future__ import annotations

import json
import sys
import urllib.request

from thealgorithms_mcp import fetch
from thealgorithms_mcp import index as idx
from thealgorithms_mcp import search


def head(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "verify"})
    try:
        return urllib.request.urlopen(req, timeout=25).getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return -1


def run(lang: str) -> dict:
    out: dict = {"language": lang, "verdict_pass": False, "anomalies": []}
    ents = idx.load_index(lang)
    out["entries"] = len(ents)
    cats = sorted({e["category"] for e in ents})
    out["categories"] = len(cats)
    out["sample_categories"] = cats[:8]

    # sample three spread-out entries; fetch + url-check each
    picks = [ents[0], ents[len(ents) // 2], ents[-1]] if len(ents) >= 3 else ents
    src_ok = 0
    url_ok = 0
    for e in picks:
        try:
            src = fetch.get_file(lang, e["path"])
            if len(src) > 40:
                src_ok += 1
            else:
                out["anomalies"].append(f"thin source for {e['path']} ({len(src)}B)")
        except Exception as ex:
            out["anomalies"].append(f"fetch failed {e['path']}: {ex}")
        code = head(idx.github_url(lang, e["path"]))
        if code == 200:
            url_ok += 1
        else:
            out["anomalies"].append(f"github_url HTTP {code} for {e['path']}")
    out["source_ok"] = f"{src_ok}/{len(picks)}"
    out["url_ok"] = f"{url_ok}/{len(picks)}"

    res = search.search(ents, "sort", limit=3)
    out["search_returns"] = len(res)
    out["sample_github_url"] = idx.github_url(lang, picks[0]["path"])

    out["verdict_pass"] = (
        out["entries"] >= 10
        and out["categories"] >= 1
        and src_ok == len(picks)
        and url_ok == len(picks)
        and len(res) >= 1
    )
    return out


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1])))
