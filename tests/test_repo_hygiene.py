"""No source file may be silently invisible to git or to lint.

Twice a bare folder name hid real code: `.gitignore`'s `lakehouse/` kept
src/graphguard/lakehouse out of git for a whole story (S5.6a-c), and a ruff
`extend-exclude = ["lakehouse"]` would have skipped it from lint (S5.6d). Both
match a folder at any depth. These tests make that a build failure.
"""

import shutil
import subprocess
import sys

import pytest

from graphguard.config import REPO_ROOT

pytestmark = pytest.mark.unit

SOURCES = sorted(
    p.relative_to(REPO_ROOT).as_posix()
    for d in ("src", "tests", "scripts")
    for p in (REPO_ROOT / d).rglob("*.py")
    if "__pycache__" not in p.parts
)


def test_there_are_sources_to_check():
    assert any(s.startswith("src/graphguard/lakehouse/") for s in SOURCES)


@pytest.mark.skipif(
    not (REPO_ROOT / ".git").exists() or shutil.which("git") is None,
    reason="not a git checkout (an exported copy): nothing for .gitignore to hide",
)
def test_no_source_file_is_gitignored():
    out = subprocess.run(
        ["git", "check-ignore", "--no-index", *SOURCES],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert out.stdout.split() == [], f"gitignored source files: {out.stdout.split()}"


def test_ruff_lints_every_source_file():
    out = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--show-files", "src", "tests", "scripts"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    seen = {line.strip().removeprefix(str(REPO_ROOT) + "/") for line in out.stdout.splitlines()}
    missing = [s for s in SOURCES if s not in seen]
    assert not missing, f"ruff skips: {missing}"
