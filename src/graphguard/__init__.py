"""GraphGuard-AI — money laundering detection on a transaction graph.

The version is read from installed package metadata rather than hardcoded here,
so `pyproject.toml` stays the single source of truth and the two cannot drift.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("graphguard")
except PackageNotFoundError:  # pragma: no cover - only when not installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
