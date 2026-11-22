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
# Code that is not the package but still runs against the data (S5.6e): worksheets
# and the isolated Feast project. Same rules.
EXTRA_DIRS = (REPO_ROOT / "notebooks", REPO_ROOT / "featurestore")


def _sources() -> list[Path]:
    paths = list(SRC_DIR.rglob("*.py"))
    for d in EXTRA_DIRS:
        if d.exists():
            paths += [p for p in d.rglob("*.py") if ".venv" not in p.parts]
    return sorted(paths)


# Loading the test split looks like load_split("test") or similar.
# features_for_split(lf, "test", b) builds the test window's features (S7.2).
LOADER_NAMES = {"load_split", "read_split", "get_split", "features_for_split"}
TEST_SPLIT_LITERALS = {"test"}

# Files permitted to load the test split, with the reason. Anything not listed
# fails the guard.
ALLOWLIST: dict[str, str] = {
    "src/graphguard/evaluation/final_report.py": (
        "the single place the test set is opened, at the very end of the project"
    ),
}


# The lakehouse keeps the test window in the Iceberg namespace "sealed" (S5.6a).
# Naming that namespace is how code would read it, so outside the files that
# create and write it, merely naming it counts as touching the test set.
SEALED_NAMESPACE = "sealed"
SEALED_ALLOWLIST: dict[str, str] = {
    "src/graphguard/lakehouse/catalog.py": "creates the namespace",
    "src/graphguard/lakehouse/tables.py": "writes the test window into it; never reads it",
    "src/graphguard/lakehouse/governance.py": (
        "the access policy: names it only to deny it to trainer and reader (S5.6d)"
    ),
}


# The raw files hold EVERY window, the test window included (S7.2). Reading one is allowed
# where the reader then keeps train/validation only (frozen boundaries) -- and only in the
# files listed here, each with its reason. New code (the screens, the API, the agent) reads
# the lakehouse or the demo database instead, so it can never touch the test window.
RAW_NAMES = {"TRANSACTIONS_FILE", "PATTERNS_FILE"}
_SPLIT = "filters to train/validation by the frozen boundaries"
RAW_ALLOWLIST: dict[str, str] = {
    "src/graphguard/config.py": "defines the raw file paths, reads nothing",
    "src/graphguard/lakehouse/build.py": (
        "the builder: CSV -> bronze/silver/sealed, rings -> gold/sealed"
    ),
    "src/graphguard/evaluation/dataset.py": f"load_split: {_SPLIT}; 'test' is counted above",
    "src/graphguard/evaluation/freeze_split.py": "computes the frozen boundaries once (Phase 2)",
    "src/graphguard/data/summary.py": "dataset summary counts (Phase 0), no model input",
    "src/graphguard/analysis/cold_accounts.py": f"FINDING-014 measurement; {_SPLIT}",
    "src/graphguard/models/train_tabular.py": f"Phase 3 training; {_SPLIT}",
    "src/graphguard/models/tune_tabular.py": f"Phase 3 tuning on validation; {_SPLIT}",
    "src/graphguard/graph/run_gnn.py": f"Phase 4 GNN; {_SPLIT}",
    "src/graphguard/graph/tune_gnn.py": f"Phase 4 GNN tuning on validation; {_SPLIT}",
    "src/graphguard/serving/measure_staleness.py": f"FINDING-008 measurement; {_SPLIT}",
    "src/graphguard/serving/measure_latency.py": "latency sample rows (no labels used)",
    "src/graphguard/serving/perf_k8s.py": "load-test request rows (no labels used)",
    "src/graphguard/stream/e2e.py": f"offline scores to check the stream; {_SPLIT}",
    "src/graphguard/stream/chaos.py": f"offline scores to check chaos runs; {_SPLIT}",
    "src/graphguard/stream/proof.py": f"S6.3 full-replay proof; {_SPLIT}",
    "src/graphguard/stream/rules.py": f"rule thresholds from train only; {_SPLIT}",
    "src/graphguard/stream/labels.py": f"late-label simulation on validation; {_SPLIT}",
    "src/graphguard/stream/shadow.py": f"challenger training on train only; {_SPLIT}",
}


def find_raw_refs(rel: str, source: str) -> list[str]:
    """Any use of a raw-file name: an import of it or a reference to it."""
    hits: list[str] = []
    for node in ast.walk(ast.parse(source, filename=rel)):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.alias):
            name = node.name
        if name in RAW_NAMES:
            hits.append(f"{rel}:{getattr(node, 'lineno', '?')}: reads a raw file ({name})")
    return hits


def find_sealed_refs(rel: str, source: str) -> list[str]:
    """Any string literal naming the sealed namespace ("sealed" or "sealed.x")."""
    hits: list[str] = []
    for node in ast.walk(ast.parse(source, filename=rel)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if v == SEALED_NAMESPACE or v.startswith(SEALED_NAMESPACE + "."):
                hits.append(f"{rel}:{node.lineno}: names the sealed (test-window) namespace")
    return hits


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

    for path in _sources():
        rel = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text()
        hits = find_test_loads(rel, source)
        if hits:
            if rel in ALLOWLIST:
                allowed_hits += len(hits)
            else:
                violations.extend(hits)
        sealed = find_sealed_refs(rel, source)
        if sealed and rel not in SEALED_ALLOWLIST:
            violations.extend(sealed)
        raw = find_raw_refs(rel, source)
        if raw and rel not in RAW_ALLOWLIST:
            violations.extend(raw)

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
