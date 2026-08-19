"""Compute the temporal split once and write it to disk, frozen.

The output is a small JSON file holding the boundary timestamps and the counts
they produce -- not the row assignments, which are derivable from the
boundaries and would be 5M lines. Its checksum is written alongside and checked
on every commit by scripts/guards/split_integrity_check.py, so the split cannot
change silently after results have been measured against it.

Deterministic by construction: no timestamps of its own, no randomness. Running
it twice on the same data produces a byte-identical file.
"""

from __future__ import annotations

import hashlib
import json

import polars as pl

from graphguard.config import SPLITS_DIR, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.split import (
    DEFAULT_FRACTIONS,
    TAIL_CUTOFF,
    assign_split,
    compute_boundaries,
    truncate_tail,
)

SPLIT_FILE = SPLITS_DIR / "frozen_split.json"
CHECKSUM_FILE = SPLITS_DIR / "frozen_split.sha256"


def build() -> dict:
    raw = load_transactions(TRANSACTIONS_FILE)
    dropped = raw.select(pl.len()).collect().item() - (
        truncate_tail(raw).select(pl.len()).collect().item()
    )

    lf = truncate_tail(raw)
    boundaries = compute_boundaries(lf, DEFAULT_FRACTIONS)

    per_split = (
        assign_split(lf, boundaries)
        .group_by("split")
        .agg(
            pl.len().alias("transactions"),
            pl.col("is_laundering").sum().alias("laundering"),
            pl.col("timestamp").min().alias("first"),
            pl.col("timestamp").max().alias("last"),
        )
        .collect()
    )

    splits = {}
    for row in per_split.iter_rows(named=True):
        splits[row["split"]] = {
            "transactions": int(row["transactions"]),
            "laundering": int(row["laundering"]),
            "laundering_rate": round(row["laundering"] / row["transactions"], 8),
            "first": row["first"].isoformat(),
            "last": row["last"].isoformat(),
        }

    return {
        "dataset": TRANSACTIONS_FILE.name,
        "method": "temporal, boundaries at row quantiles of the timestamp",
        "fractions": {"train": DEFAULT_FRACTIONS[0], "validation": DEFAULT_FRACTIONS[1]},
        "tail_cutoff": TAIL_CUTOFF.isoformat(),
        "tail_rows_dropped": int(dropped),
        "tail_reason": "FINDING-001: post-period rows are 57-73% laundering",
        "boundaries": {
            "train_end": boundaries[0].isoformat(),
            "val_end": boundaries[1].isoformat(),
        },
        "splits": {name: splits[name] for name in sorted(splits)},
    }


def main() -> int:
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(build(), indent=2, sort_keys=True) + "\n"
    SPLIT_FILE.write_text(payload)

    digest = hashlib.sha256(payload.encode()).hexdigest()
    CHECKSUM_FILE.write_text(f"{digest}  {SPLIT_FILE.name}\n")

    print(payload)
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
