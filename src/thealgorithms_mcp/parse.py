"""Extract a description + in-file usage examples from source, dispatched by language.

Examples are language-specific conventions, so extraction is a per-language registry:
  - python: doctests (>>>) from every module/class/function docstring (richest)
  - rust:   ```code``` fences inside /// doc comments (rustdoc doctests)
  - others: no in-file convention -> empty examples + an explicit note (graceful degradation)
The goal's bar is "Python doctests at minimum"; the dispatch makes adding languages trivial.
"""
from __future__ import annotations

import ast
import doctest
import re

_PY_DOC_NODES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _python(source: str) -> dict:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"description": "", "examples": []}
    description = ast.get_docstring(tree) or ""
    parser = doctest.DocTestParser()
    examples: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, _PY_DOC_NODES):
            doc = ast.get_docstring(node)
            if not doc:
                continue
            for ex in parser.get_examples(doc):
                examples.append({"code": ex.source.rstrip("\n"), "expected": ex.want.rstrip("\n")})
    return {"description": description, "examples": examples}


_RUST_DOC = re.compile(r"^\s*///\s?(.*)$")
_FENCE = re.compile(r"^```")


def _rust(source: str) -> dict:
    """Pull rustdoc doctests: fenced code blocks inside /// comments."""
    doc_lines: list[str] = []
    for line in source.splitlines():
        m = _RUST_DOC.match(line)
        if m:
            doc_lines.append(m.group(1))
    examples: list[dict] = []
    in_fence = False
    buf: list[str] = []
    for line in doc_lines:
        if _FENCE.match(line.strip()):
            if in_fence:
                code = "\n".join(b for b in buf if not b.strip().startswith("#") or b.strip() == "#")
                if code.strip():
                    examples.append({"code": code.rstrip("\n"), "expected": ""})
                buf = []
            in_fence = not in_fence
            continue
        if in_fence:
            buf.append(line)
    # description: leading // or /// summary lines before the first item
    desc: list[str] = []
    for line in source.splitlines():
        s = line.strip()
        if s.startswith("//!") or s.startswith("///"):
            desc.append(re.sub(r"^/+!?\s?", "", s))
        elif s and not s.startswith("//"):
            break
    return {"description": "\n".join(desc).strip(), "examples": examples}


# language -> extractor
_EXTRACTORS = {"python": _python, "rust": _rust}


def parse_source(source: str, language: str) -> dict:
    """Return {description, examples, line_count, note?}.

    examples: [{code, expected}] where the language has an in-file convention, else [].
    note: present (and examples empty) for languages without an extractor.
    """
    line_count = len(source.splitlines())
    extractor = _EXTRACTORS.get(language)
    if extractor is None:
        return {
            "description": "",
            "examples": [],
            "line_count": line_count,
            "note": f"In-file example extraction is not available for '{language}'; "
            "returning source only.",
        }
    result = extractor(source)
    result["line_count"] = line_count
    return result
