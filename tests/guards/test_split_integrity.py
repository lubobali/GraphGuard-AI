"""The split guard must notice when the frozen split changes."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "guards"))

from split_integrity_check import sha256_of, verify  # noqa: E402


@pytest.mark.unit
def test_unchanged_split_passes():
    digest = sha256_of(b'{"train": 1}')
    assert verify(digest, digest) == []


@pytest.mark.unit
def test_changed_split_fails():
    problems = verify(sha256_of(b'{"train": 1}'), sha256_of(b'{"train": 2}'))
    assert problems
    assert "THE FROZEN SPLIT CHANGED." in problems[0]


@pytest.mark.unit
def test_missing_checksum_fails():
    problems = verify(sha256_of(b"anything"), None)
    assert problems
    assert "never recorded" in problems[0]


@pytest.mark.unit
def test_checksum_is_stable_for_identical_bytes():
    assert sha256_of(b"same") == sha256_of(b"same")
