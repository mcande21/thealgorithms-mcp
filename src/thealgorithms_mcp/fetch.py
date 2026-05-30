"""On-demand fetch of a single algorithm file's source, by language + repo-relative path."""
from __future__ import annotations

from . import discovery
from .http import cached_get
from .index import encode_path


def get_file(language: str, path: str) -> str:
    """Return raw source for a path in a language's repo.

    Raises KeyError for an unknown language, FileNotFoundError for a missing path.
    """
    info = discovery.discover()["languages"][language]
    code, text = cached_get(info["raw_base"] + encode_path(path))
    if code == 404:
        raise FileNotFoundError(path)
    if code != 200:
        raise RuntimeError(f"Could not fetch {path} ({language}): HTTP {code}")
    return text
