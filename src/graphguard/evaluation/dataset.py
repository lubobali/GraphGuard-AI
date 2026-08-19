"""Load a frozen split, ready to score.

The boundaries are read from `data/splits/frozen_split.json` rather than
recomputed, so a change to the splitting code cannot silently move the
boundaries out from under results already measured. The file's checksum is
guarded on every commit.
"""

from __future__ import annotations

import datetime as dt
import json

import polars as pl

from graphguard.analysis.patterns import parse_patterns
from graphguard.config import PATTERNS_FILE, SPLITS_DIR, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.evaluate import NO_PATTERN
from graphguard.evaluation.split import assign_split, truncate_tail

SPLIT_FILE = SPLITS_DIR / "frozen_split.json"

# The composite key that identifies a transaction across the two files.
_MATCH_KEY = ["timestamp", "from_account", "to_account", "amount_paid"]


def frozen_boundaries() -> tuple[dt.datetime, dt.datetime]:
    """Read the boundaries that were frozen, rather than computing new ones."""
    payload = json.loads(SPLIT_FILE.read_text())
    b = payload["boundaries"]
    return (
        dt.datetime.fromisoformat(b["train_end"]),
        dt.datetime.fromisoformat(b["val_end"]),
    )


def attach_pattern_ids(transactions: pl.LazyFrame, patterns: pl.DataFrame) -> pl.LazyFrame:
    """Tag each transaction with its laundering ring, or NO_PATTERN.

    Matched on the full key: two transfers between the same pair on the same
    day for different amounts are different transactions.
    """
    lookup = patterns.select([*_MATCH_KEY, "pattern_id"]).unique(subset=_MATCH_KEY, keep="first")

    return transactions.join(lookup.lazy(), on=_MATCH_KEY, how="left").with_columns(
        pl.col("pattern_id").fill_null(NO_PATTERN).cast(pl.Int32)
    )


def load_split(name: str) -> pl.DataFrame:
    """Load one split of the frozen data, with pattern ids attached.

    `name` is "train", "validation" or "test". Loading "test" is counted by
    scripts/guards/test_set_touch_check.py -- contract rule 4, the test window
    is opened once.
    """
    if name not in ("train", "validation", "test"):
        raise ValueError(f"unknown split: {name}")

    lf = truncate_tail(load_transactions(TRANSACTIONS_FILE))
    lf = assign_split(lf, frozen_boundaries()).filter(pl.col("split") == name)
    lf = attach_pattern_ids(lf, parse_patterns(PATTERNS_FILE))

    return lf.collect()
