"""Fuzzy lexical ranking over the cached index. No network — index only."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

_NORM_RE = re.compile(r"[\s_/]+")


def _norm(s: str) -> str:
    """Lowercase and collapse separators so 'merge_sort'/'Merge Sort' compare equal."""
    return _NORM_RE.sub(" ", s.lower()).strip()


def search(entries: list[dict], query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    """Rank entries by fuzzy match against name (primary) and path (fallback).

    Scoring rewards *tight* matches so exact intent wins over a superset:
      - exact normalized name match dominates ("merge sort" -> "Merge Sort", not "Iterative Merge Sort")
      - a substring hit is scaled by how much of the name it covers (tighter = higher)
      - path matches count at half weight, so a name match always outranks an incidental path hit
    Returns [{name, category, path, score}] sorted desc.
    """
    qn = _norm(query)
    pool = entries if category is None else [e for e in entries if e["category"] == category]

    scored: list[tuple[float, dict]] = []
    for e in pool:
        name_n = _norm(e["name"])
        path_n = _norm(e["path"][:-3] if e["path"].endswith(".py") else e["path"])

        base = fuzz.WRatio(qn, name_n)
        path_score = fuzz.partial_ratio(qn, path_n) * 0.5

        bonus = 0.0
        if qn == name_n:
            bonus = 100.0
        elif qn and qn in name_n:
            bonus = 30.0 * len(qn) / len(name_n)  # covers more of the name -> bigger bonus

        score = max(base, path_score) + bonus
        scored.append((score, e))

    scored.sort(key=lambda x: -x[0])
    return [
        {"name": e["name"], "category": e["category"], "path": e["path"], "score": round(s, 1)}
        for s, e in scored[:limit]
    ]
