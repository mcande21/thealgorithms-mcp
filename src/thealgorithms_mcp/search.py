"""Fuzzy lexical ranking over the cached index. No network — index only."""
from __future__ import annotations

import re

from rapidfuzz import fuzz

# Drop everything that isn't a letter or digit. '*' is mapped to "star" first so that
# "A*" -> "a star" matches "A Star"; without this it collapses to a useless bare "a".
_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    """Lowercase, expand '*'->star, and reduce all other punctuation/separators to spaces."""
    return _NORM_RE.sub(" ", s.lower().replace("*", " star ")).strip()


def _initialism(name_n: str) -> str:
    """First letter of each word of a normalized name: 'breadth first search' -> 'bfs'."""
    return "".join(w[0] for w in name_n.split(" ") if w)


def search(entries: list[dict], query: str, category: str | None = None, limit: int = 10) -> list[dict]:
    """Rank entries by fuzzy match against name (primary) and path (fallback).

    Scoring rewards *tight* matches so exact intent wins over a superset:
      - exact normalized name match dominates ("merge sort" -> "Merge Sort", not "Iterative Merge Sort")
      - a substring hit is scaled by how much of the name it covers (tighter = higher)
      - a short single-token query that equals an entry's initialism ("bfs" -> "Breadth First Search")
        gets a strong boost — the lexical scorer can't bridge acronyms on its own. Restricted to
        3-5 char queries because 2-letter initialisms collide across dozens of entries.
      - path matches count at half weight, so a name match always outranks an incidental path hit
    Returns [{name, category, path, score}] sorted desc.
    """
    qn = _norm(query)
    is_acronym = qn.isalpha() and 3 <= len(qn) <= 5
    q_tokens = [t for t in qn.split(" ") if t]
    pool = entries if category is None else [e for e in entries if e["category"] == category]

    scored: list[tuple[float, dict]] = []
    for e in pool:
        name_n = _norm(e["name"])
        path_n = _norm(e["path"][:-3] if e["path"].endswith(".py") else e["path"])

        base = fuzz.WRatio(qn, name_n)
        path_score = fuzz.partial_ratio(qn, path_n) * 0.5

        # Coverage damping: for a multi-word query, a name that contains *less than half* of the
        # query's words is a weak match riding on token/partial overlap (e.g. "Tree" vs "red black
        # tree" = 1 of 3). Damp it. The < 0.5 cutoff is deliberate: a 2-word query matched by a
        # 1-word abbreviation ("Bubble" for "bubble sort" = 1 of 2) is a legitimate hit, so it is
        # NOT penalized. Coverage is checked against the name with separators removed, so a
        # CamelCase concatenation ("BubbleSort" covers "bubble sort") also scores full coverage.
        fuzzy = max(base, path_score)
        if len(q_tokens) > 1:
            compact = name_n.replace(" ", "")
            coverage = sum(1 for t in q_tokens if t in compact) / len(q_tokens)
            if coverage < 0.5:
                fuzzy *= 0.4 + 0.6 * coverage  # 1-of-3 -> ~0.6; 1-of-4 -> 0.55; 0 -> 0.4

        bonus = 0.0
        if qn and qn == name_n:
            bonus = 100.0
        elif qn and qn in name_n:
            bonus = 30.0 * len(qn) / len(name_n)  # covers more of the name -> bigger bonus
        if is_acronym and _initialism(name_n) == qn:
            bonus = max(bonus, 90.0)  # acronym hit, but never beats an exact full-name match

        score = fuzzy + bonus
        scored.append((score, e))

    scored.sort(key=lambda x: -x[0])
    return [
        {"name": e["name"], "category": e["category"], "path": e["path"], "score": round(s, 1)}
        for s, e in scored[:limit]
    ]
