"""Unit tests for language-dispatched example extraction (no network)."""
from thealgorithms_mcp.parse import parse_source

PY = '''"""Module summary."""


def square(x):
    """
    >>> square(2)
    4
    >>> square(3)
    9
    """
    return x * x
'''

RUST = """//! Adds two numbers.

/// Returns the sum.
/// ```
/// assert_eq!(add(2, 2), 4);
/// ```
fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""


def test_python_doctests_from_function():
    r = parse_source(PY, "python")
    codes = {e["code"].strip() for e in r["examples"]}
    assert "square(2)" in codes and "square(3)" in codes
    assert r["description"] == "Module summary."
    assert r["line_count"] > 0


def test_rust_rustdoc_examples():
    r = parse_source(RUST, "rust")
    assert any("assert_eq!(add(2, 2), 4)" in e["code"] for e in r["examples"])


def test_unknown_language_degrades_gracefully():
    r = parse_source("contract Foo { }", "solidity")
    assert r["examples"] == []
    assert "note" in r and "solidity" in r["note"]
