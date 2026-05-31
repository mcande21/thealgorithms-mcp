"""TheAlgorithms MCP — query TheAlgorithms across languages for implementations + examples."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("thealgorithms-mcp")
except PackageNotFoundError:  # not installed (e.g. running from a raw checkout)
    __version__ = "0+unknown"
