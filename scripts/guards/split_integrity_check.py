"""Fail the commit if the frozen train/validation/test split changed.

Rule 1 of the leakage contract: the split is computed once, by time, and
frozen. Every number the project reports is measured against that split. If it
is silently re-rolled, every previous result becomes incomparable and nothing
would reveal it -- the tests still pass, the metrics still print.

So the split file's checksum is committed alongside it. This guard recomputes
the checksum and fails on any mismatch.

Re-rolling the split is occasionally legitimate. It is not forbidden, it is
made loud: update the recorded checksum in the same commit, and say why in the
commit message.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPLIT_FILE = REPO_ROOT / "data" / "splits" / "frozen_split.json"
CHECKSUM_FILE = REPO_ROOT / "data" / "splits" / "frozen_split.sha256"


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(actual: str, recorded: str | None) -> list[str]:
    """Pure comparison, kept free of I/O so it is testable."""
    if recorded is None:
        return [
            "the frozen split exists but its checksum was never recorded. "
            f"Write the checksum to {CHECKSUM_FILE.name} in this commit."
        ]
    if actual != recorded:
        return [
            "THE FROZEN SPLIT CHANGED.",
            f"  recorded: {recorded}",
            f"  actual:   {actual}",
            "",
            "Every result measured so far used the recorded split and is now "
            "incomparable. If this change is deliberate, update the recorded "
            "checksum in this same commit and say why in the message.",
        ]
    return []


def main() -> int:
    if not SPLIT_FILE.exists():
        # Phase 2 creates it. The guard exists first so the rule is in place
        # before the file it protects.
        print("split_integrity_check: no frozen split yet, nothing to check")
        return 0

    actual = sha256_of(SPLIT_FILE.read_bytes())
    recorded = CHECKSUM_FILE.read_text().split()[0] if CHECKSUM_FILE.exists() else None

    problems = verify(actual, recorded)
    if problems:
        print("SPLIT INTEGRITY CHECK FAILED\n")
        for line in problems:
            print(f"  {line}")
        return 1

    print(f"split_integrity_check: split unchanged ({actual[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
