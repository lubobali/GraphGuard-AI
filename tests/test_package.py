"""The package must be importable and declare its version.

Trivial on purpose: it proves the src layout, the build backend, and the
editable install all work before anything depends on them.
"""

import pytest


@pytest.mark.unit
def test_package_imports():
    import graphguard

    assert graphguard.__version__


@pytest.mark.unit
def test_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    import graphguard

    pyproject = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())
    assert graphguard.__version__ == pyproject["project"]["version"]
