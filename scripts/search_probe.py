"""Edge-case battery for search ranking. Prints top-3 per query so we can see failures.
Run: uv run python scripts/search_probe.py
"""
from thealgorithms_mcp import index as idx
from thealgorithms_mcp.search import search

entries = idx.load_index("python")

# (query, expected substring in the IDEAL top path) — expected is best-guess, may be None if unsure
CASES = [
    ("A*", "a_star"),
    ("A* pathfinding", "a_star"),
    ("a star", "a_star"),
    ("astar", "astar"),
    ("BFS", "breadth_first_search"),
    ("DFS", "depth_first_search"),
    ("breadth first search", "breadth_first_search"),
    ("quicksort", "quick_sort"),
    ("quick sort", "quick_sort"),
    ("mergesort", "merge_sort"),
    ("n-queens", "n_queens"),
    ("n queens", "n_queens"),
    ("k-means", "k_means"),
    ("knn", "k_nearest"),
    ("k nearest neighbours", "k_nearest"),
    ("fibonacci", "fibonacci"),
    ("FFT", "fast_fourier"),
    ("fast fourier transform", "fast_fourier"),
    ("sha256", "sha256"),
    ("dijkstra's algorithm", "dijkstra"),
    ("lru cache", "lru_cache"),
    ("binary search", "binary_search"),
    ("topological sort", "topological"),
    ("rsa", "rsa"),
    ("gcd", "greatest_common_divisor"),
    ("levenshtein", "levenshtein"),
    ("sieve of eratosthenes", "sieve"),
    ("C++", None),
]

print(f"index: {len(entries)} entries\n")
print(f"{'QUERY':28} {'OK':3} TOP-3 PATHS")
print("-" * 100)
fails = []
for q, exp in CASES:
    res = search(entries, q, limit=3)
    top = res[0]["path"] if res else "<none>"
    ok = exp is None or (exp in top)
    if not ok:
        fails.append((q, exp, top))
    paths = "  |  ".join(f"{r['path']}({r['score']})" for r in res)
    print(f"{q:28} {'ok ' if ok else 'XX '} {paths}")

print("\n" + "=" * 100)
print(f"FAILURES ({len(fails)}):")
for q, exp, top in fails:
    print(f"  {q!r:30} expected ~{exp!r}, got {top!r}")
