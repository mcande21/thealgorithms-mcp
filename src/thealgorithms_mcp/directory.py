"""Parse a TheAlgorithms DIRECTORY.md into algorithm entries — for ANY language repo.

The org's repos use several DIRECTORY.md dialects, all handled here:
  - repo-relative paths           (Python:  audio_filters/butterworth_filter.py)
  - relative with a ./ prefix      (PHP:     ./Ciphers/AtbashCipher.php)
  - absolute GitHub blob URLs      (Rust/C++: https://github.com/.../blob/HEAD/src/...)
  - non-'*' bullets / emoji icons  (Java:    - 📄 [EMAFilter](src/main/java/.../EMAFilter.java))
  - URL-encoded paths              (MATLAB:  .../Activation%20Functions/...)

Category is the file's immediate parent directory — uniform across languages and robust to
boilerplate nesting (Java's src/main/java/com/thealgorithms/<category>/, Rust's src/<category>/).
Test files are dropped so they don't pollute search.
"""
from __future__ import annotations

import re
from urllib.parse import unquote

# [Name](target) anywhere on a list line, regardless of bullet style (*, -, emoji prefix).
_LINK = re.compile(r"\[(?P<name>[^\]]+)\]\((?P<target>[^)]+)\)")
_BLOB = re.compile(r"https?://github\.com/[^/]+/[^/]+/blob/[^/]+/(?P<path>.+)$", re.I)

# Extensions that are never algorithm source — used to find the real source files.
_DOC_EXT = {
    ".md", ".png", ".gif", ".svg", ".jpg", ".jpeg", ".txt", ".json", ".lock", ".toml",
    ".yml", ".yaml", ".cfg", ".ini", ".ipynb", ".html", ".css", ".csv", ".xml", "",
}

_TEST_DIRS = {"test", "tests", "__tests__", "spec", "specs"}
_TEST_FILE = re.compile(r"(^test_|_test\.|\.test\.|\.spec\.|tests?\.[a-z0-9]+$|test\.[a-z0-9]+$)", re.I)


def _ext(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    return "." + base.rsplit(".", 1)[1].lower() if "." in base else ""


def _normalize(target: str) -> str | None:
    """Reduce a link target to a repo-relative path, or None if it can't be localized."""
    t = target.strip()
    m = _BLOB.match(t)
    if m:
        t = m.group("path")
    if t.startswith("./"):
        t = t[2:]
    if t.startswith("http"):  # a foreign absolute URL (not a blob we can localize)
        return None
    return unquote(t)


def _is_test(path: str) -> bool:
    comps = path.split("/")
    if any(c.lower() in _TEST_DIRS for c in comps[:-1]):
        return True
    base = comps[-1]
    return bool(_TEST_FILE.search(base)) or base[:-len(_ext(path)) or None].endswith("Test")


def _category(path: str) -> str:
    comps = path.split("/")
    return comps[-2] if len(comps) >= 2 else "root"


def parse_directory(text: str) -> list[dict]:
    """Parse DIRECTORY.md text into [{name, path, category, ext}], test files removed."""
    entries: list[dict] = []
    seen: set[str] = set()
    for line in text.splitlines():
        for m in _LINK.finditer(line):
            path = _normalize(m.group("target"))
            if not path or _ext(path) in _DOC_EXT or _is_test(path):
                continue
            if path in seen:
                continue
            seen.add(path)
            entries.append(
                {
                    "name": m.group("name").strip(),
                    "path": path,
                    "category": _category(path),
                    "ext": _ext(path),
                }
            )
    return entries


def dominant_extension(entries: list[dict]) -> str:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["ext"]] = counts.get(e["ext"], 0) + 1
    return max(counts, key=counts.get) if counts else ""
