"""Unit tests for search scoring: exact, acronym, symbol, and coverage damping (no network)."""
from thealgorithms_mcp.search import search

ENTRIES = [
    {"name": "Merge Sort", "path": "sorts/merge_sort.py", "category": "sorts", "ext": ".py"},
    {"name": "Iterative Merge Sort", "path": "sorts/iterative_merge_sort.py", "category": "sorts", "ext": ".py"},
    {"name": "Bubble", "path": "sort/bubble.jule", "category": "sort", "ext": ".jule"},
    {"name": "Tree", "path": "data_structures/tree.cpp", "category": "data_structures", "ext": ".cpp"},
    {"name": "Red Black Tree", "path": "data_structures/red_black_tree.py", "category": "data_structures", "ext": ".py"},
    {"name": "A Star", "path": "graphs/a_star.py", "category": "graphs", "ext": ".py"},
    {"name": "Breadth First Search", "path": "graphs/bfs.py", "category": "graphs", "ext": ".py"},
    {"name": "Greatest Common Divisor", "path": "maths/gcd.py", "category": "maths", "ext": ".py"},
]


def top_name(query):
    res = search(ENTRIES, query, limit=1)
    return res[0]["name"] if res else None


def score_of(query, name):
    for r in search(ENTRIES, query, limit=50):
        if r["name"] == name:
            return r["score"]
    return 0.0


def test_exact_match_wins():
    assert top_name("merge sort") == "Merge Sort"


def test_acronym_initialism():
    assert top_name("bfs") == "Breadth First Search"
    assert top_name("gcd") == "Greatest Common Divisor"


def test_symbol_star_maps_to_a_star():
    assert top_name("A*") == "A Star"


def test_coverage_damps_generic_name_for_three_word_query():
    # "Tree" covers only 1 of 3 query words -> damped below the 90 compare threshold
    assert score_of("red black tree", "Tree") < 90
    assert score_of("red black tree", "Red Black Tree") >= 200


def test_two_word_abbreviation_not_penalized():
    # "Bubble" covers 1 of 2 ("bubble") -> NOT damped (legitimate abbreviation)
    assert score_of("bubble sort", "Bubble") >= 90


def test_real_superset_match_kept():
    assert score_of("merge sort", "Iterative Merge Sort") >= 90


def test_category_filter():
    res = search(ENTRIES, "sort", category="sorts", limit=10)
    assert res and all(r["category"] == "sorts" for r in res)
