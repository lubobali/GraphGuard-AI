"""Fail the commit if the test set is loaded from more places than allowed.

Rule 4 of the leakage contract: the test window is opened once. Every tuning
decision is made on validation. A test set consulted repeatedly stops being a
test set -- each peek leaks a little information through the choices it
influences, and the final number drifts optimistic with no way to detect it.

This guard cannot know intent, so it counts instead: how many places in the
source load the test split. That count is compared against an explicit
allowlist. Adding a new call site is not forbidden, it requires editing this
file, which makes it a decision rather than an accident.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src" / "graphguard"

# Loading the test split looks like load_split("test") or similar.
LOADER_NAMES = {"load_split", "read_split", "get_split"}
TEST_SPLIT_LITERALS = {"test"}

# Files permitted to load the test split, with the reason. Anything not listed
# fails the guard.
ALLOWLIST: dict[str, str] = {
    "src/graphguard/evaluation/final_report.py": (
        "the single place the test set is opened, at the very end of the project"
    ),
}


def find_test_loads(rel: str, source: str) -> list[str]:
    """Pure check over one file's source. Kept free of I/O so it is testable."""
    hits: list[str] = []
    tree = ast.parse(source, filename=rel)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name not in LOADER_NAMES:
            continue
        literals = [
            a.value
            for a in (*node.args, *(k.value for k in node.keywords))
            if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
        if any(lit in TEST_SPLIT_LITERALS for lit in literals):
            hits.append(f"{rel}:{node.lineno}: loads the test split")

    return hits


def main() -> int:
    if not SRC_DIR.exists():
        print("test_set_touch_check: no source yet, nothing to check")
        return 0

    violations: list[str] = []
    allowed_hits = 0

    for path in sorted(SRC_DIR.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        hits = find_test_loads(rel, path.read_text())
        if not hits:
            continue
        if rel in ALLOWLIST:
            allowed_hits += len(hits)
        else:
            violations.extend(hits)

    if violations:
        print("TEST SET TOUCH CHECK FAILED\n")
        for v in violations:
            print(f"  {v}")
        print(
            "\nThis is leakage contract rule 4: the test window is opened once.\n"
            "Tune on validation. If this call site is genuinely the final\n"
            "evaluation, add it to ALLOWLIST in\n"
            "scripts/guards/test_set_touch_check.py with a reason."
        )
        return 1

    print(f"test_set_touch_check: {allowed_hits} allowed test-set load(s), 0 unapproved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
