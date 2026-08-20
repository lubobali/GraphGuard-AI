"""Fail the commit if feature code can see the future.

Rule 3 of the leakage contract: no feature may use information that did not
exist at decision time. In practice that mistake looks like ordinary code --
an aggregate computed over a whole dataframe rather than over the rows before
the moment being scored. It cannot be caught by reading, because it looks
correct. So it is checked mechanically.

Two checks, over files under src/graphguard/features/:

1. Any function whose name starts with `build_` or `compute_` must take a
   time-cutoff argument. Without one it has no way to exclude the future.
2. No file may reference a column on the forbidden list -- fields that are
   only knowable after the fact.

Exceptions go in ALLOWLIST, with a reason, and are reviewed like code.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURE_DIR = REPO_ROOT / "src" / "graphguard" / "features"

# A feature builder must accept one of these, so it can exclude later rows.
CUTOFF_PARAMS = {"as_of", "cutoff", "as_of_ts", "cutoff_ts"}

# Prefixes that mark a function as building features from data.
BUILDER_PREFIXES = ("build_", "compute_")

# Columns knowable only after the fact. Using them to score a transaction is
# using the answer to compute the question.
FORBIDDEN_COLUMNS = (
    "is_laundering",
    "laundering_type",
    "pattern_id",
    "label",
)

# Deliberate, reviewed exceptions. Two forms:
#
#   "path"                 -- skip the whole file. Use sparingly: every future
#                             function added to that file escapes the guard too.
#   "path::function_name"  -- skip one function. Preferred, because the rest of
#                             the file stays guarded.
#
# Every entry needs a reason that says why the function cannot see the future.
ALLOWLIST: dict[str, str] = {
    "src/graphguard/features/basic.py::build_basic_features": (
        "row-level only: every value is derived from the transaction being "
        "scored, with no aggregation over history, so there is no future to "
        "see. Verified by reading the function: no group_by, no cum_*, no "
        "join, no window."
    ),
}


def _has_cutoff(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    args = fn.args
    names = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
    return bool(names & CUTOFF_PARAMS)


def check_source(rel: str, source: str) -> list[str]:
    """Pure check over one file's source. Kept free of I/O so it is testable."""
    if rel in ALLOWLIST:
        return []

    problems: list[str] = []
    tree = ast.parse(source, filename=rel)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if (
                node.name.startswith(BUILDER_PREFIXES)
                and not _has_cutoff(node)
                and f"{rel}::{node.name}" not in ALLOWLIST
            ):
                problems.append(
                    f"{rel}:{node.lineno}: {node.name}() builds features but takes no "
                    f"time cutoff (one of: {', '.join(sorted(CUTOFF_PARAMS))}). "
                    f"Without it, the function can see the future."
                )
        # Any literal mention of a label column inside feature code.
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in FORBIDDEN_COLUMNS:
                problems.append(
                    f"{rel}:{node.lineno}: references forbidden column "
                    f"{node.value!r}. Label columns are knowable only after the "
                    f"fact and must not reach feature code."
                )

    return problems


def check_file(path: Path) -> list[str]:
    return check_source(path.relative_to(REPO_ROOT).as_posix(), path.read_text())


def main(argv: list[str]) -> int:
    if not FEATURE_DIR.exists():
        # Nothing to guard yet. The guard exists first on purpose, so the rule
        # is in place before the code that could break it.
        print("leakage_guard: no feature code yet, nothing to check")
        return 0

    targets = [Path(a) for a in argv[1:]] or sorted(FEATURE_DIR.rglob("*.py"))
    targets = [p for p in targets if p.suffix == ".py" and FEATURE_DIR in p.resolve().parents]

    problems: list[str] = []
    for path in targets:
        problems.extend(check_file(path))

    if problems:
        print("LEAKAGE GUARD FAILED\n")
        for p in problems:
            print(f"  {p}")
        print(
            "\nThis is leakage contract rule 3. Fix the feature, or add a "
            "reviewed entry to ALLOWLIST in scripts/guards/leakage_guard.py."
        )
        return 1

    print(f"leakage_guard: {len(targets)} file(s) clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
