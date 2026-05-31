"""Prefix autocomplete via a Trie — modeled on TheAlgorithms/Python data_structures/trie/trie.py.

A fitting bit of recursion: the server that indexes TheAlgorithms is itself powered by one of
its algorithms. Each algorithm name (and each of its words) is inserted so a prefix matches either
the start of the name ("dij" -> Dijkstra) or the start of any word ("search" -> Binary Search).
Lookup is O(prefix length); tries are built once per language and memoized.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")


class _Node:
    __slots__ = ("children", "indices")

    def __init__(self) -> None:
        self.children: dict[str, _Node] = {}
        self.indices: set[int] = set()  # entry indices for any key passing through this node


class Trie:
    """Prefix tree mapping name/word prefixes to entry indices."""

    def __init__(self) -> None:
        self.root = _Node()

    def insert(self, key: str, index: int) -> None:
        node = self.root
        for ch in key:
            node = node.children.setdefault(ch, _Node())
            node.indices.add(index)

    def prefix(self, prefix: str) -> set[int]:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return set()
        return node.indices


# language -> built Trie (entries are memoized upstream, so this is stable per process)
_tries: dict[str, Trie] = {}


def _build(entries: list[dict]) -> Trie:
    trie = Trie()
    for i, e in enumerate(entries):
        name = e["name"].lower()
        trie.insert(name, i)               # whole-name prefix: "dij" -> Dijkstra
        for w in _WORD.findall(name):      # per-word prefix: "search" -> Binary Search
            trie.insert(w, i)
    return trie


def suggest(language: str, entries: list[dict], prefix: str, limit: int = 10) -> list[dict]:
    """Return up to `limit` {name, category, path} entries whose name/word starts with prefix."""
    p = prefix.strip().lower()
    if not p:
        return []
    if language not in _tries:
        _tries[language] = _build(entries)
    idxs = _tries[language].prefix(p)
    hits = sorted((entries[i] for i in idxs), key=lambda e: (len(e["name"]), e["name"]))
    return [{"name": e["name"], "category": e["category"], "path": e["path"]} for e in hits[:limit]]
