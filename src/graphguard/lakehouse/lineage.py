"""What a training run must record so its data can be rebuilt exactly (S5.6a).

The Iceberg snapshot id of every table it read, the frozen split's sha256 and
the git commit. With those three, "which rows trained this model?" has one
answer, forever: time-travel each table to its snapshot.
"""

from __future__ import annotations

import hashlib
import subprocess

from pyiceberg.catalog import Catalog

from graphguard.config import REPO_ROOT
from graphguard.evaluation.dataset import SPLIT_FILE
from graphguard.lakehouse.tables import current_snapshot_ids


def _git_sha() -> str:
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return f"{sha}-dirty" if dirty else sha


def training_lineage(catalog: Catalog) -> dict[str, str | int]:
    lineage: dict[str, str | int] = {
        f"snapshot.{name}": sid for name, sid in current_snapshot_ids(catalog).items()
    }
    lineage["frozen_split_sha256"] = hashlib.sha256(SPLIT_FILE.read_bytes()).hexdigest()
    lineage["git_sha"] = _git_sha()
    return lineage
