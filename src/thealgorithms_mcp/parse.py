"""Extract the module description and all doctest examples from a source file.

Doctests in this repo live in module, class, AND function docstrings — often several
per file. We walk the full AST and run stdlib ``doctest.DocTestParser`` over every
docstring, so nothing is missed regardless of where the example sits.
"""
from __future__ import annotations

import ast
import doctest

_DOC_NODES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def parse_source(source: str) -> dict:
    """Return {description, doctests, line_count}.

    description: module-level docstring (the human-readable summary), or "".
    doctests: list of {"code", "expected"} drawn from every docstring in the file.
    """
    line_count = len(source.splitlines())
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Non-parseable (rare); still useful to return raw line count.
        return {"description": "", "doctests": [], "line_count": line_count}

    description = ast.get_docstring(tree) or ""
    parser = doctest.DocTestParser()
    doctests: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, _DOC_NODES):
            doc = ast.get_docstring(node)
            if not doc:
                continue
            for ex in parser.get_examples(doc):
                doctests.append(
                    {"code": ex.source.rstrip("\n"), "expected": ex.want.rstrip("\n")}
                )
    return {"description": description, "doctests": doctests, "line_count": line_count}
