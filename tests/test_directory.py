"""Unit tests for the multi-dialect DIRECTORY.md parser (no network)."""
from thealgorithms_mcp.directory import dominant_extension, parse_directory

SAMPLE = """
## Sorts
  * [Merge Sort](sorts/merge_sort.py)
  * [Quick Sort](./sorts/quick_sort.py)

## Graph
    * [Dijkstra](https://github.com/TheAlgorithms/Rust/blob/master/src/graph/dijkstra.rs)

## Java
          - 📄 [BubbleSort](src/main/java/com/thealgorithms/sorts/BubbleSort.java)

## Encoded
  * [Relu](algorithms/Activation%20Functions/relu.m)

## Should be dropped
  * [Test Merge](sorts/test_merge_sort.py)
  * [Foo Spec](spec/foo_spec.rb)
  * [Readme](README.md)
"""


def _by_path(entries):
    return {e["path"]: e for e in entries}


def test_relative_and_dotslash():
    e = _by_path(parse_directory(SAMPLE))
    assert "sorts/merge_sort.py" in e
    assert "sorts/quick_sort.py" in e  # leading ./ stripped
    assert e["sorts/merge_sort.py"]["category"] == "sorts"


def test_absolute_blob_url_normalized():
    e = _by_path(parse_directory(SAMPLE))
    assert "src/graph/dijkstra.rs" in e
    assert e["src/graph/dijkstra.rs"]["category"] == "graph"


def test_emoji_bullet_and_parent_category():
    e = _by_path(parse_directory(SAMPLE))
    p = "src/main/java/com/thealgorithms/sorts/BubbleSort.java"
    assert p in e
    assert e[p]["category"] == "sorts"  # parent dir, not the boilerplate prefix


def test_url_decoding_and_category():
    e = _by_path(parse_directory(SAMPLE))
    assert "algorithms/Activation Functions/relu.m" in e
    assert e["algorithms/Activation Functions/relu.m"]["category"] == "Activation Functions"


def test_tests_and_docs_dropped():
    paths = {e["path"] for e in parse_directory(SAMPLE)}
    assert "sorts/test_merge_sort.py" not in paths
    assert "spec/foo_spec.rb" not in paths
    assert not any(p.endswith(".md") for p in paths)


def test_dominant_extension():
    entries = parse_directory(SAMPLE)
    assert dominant_extension(entries) == ".py"  # 2 .py vs 1 each of others
