"""Assemble features for one split, with the correct history window.

The subtlety this module exists for: a validation row's history legitimately
includes the training window. That is its past, and a bank scoring it in
production would have exactly that history available. What it must never
include is anything at or after the row itself.

So `as_of` is the *end of the split being built*, not the start. Features are
computed over everything before that instant, and then only the rows belonging
to the requested split are returned.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from graphguard.evaluation.split import assign_split
from graphguard.features.basic import build_basic_features
from graphguard.features.graph import build_account_history_features

_SPLIT_END = {"train": 0, "validation": 1}


def features_for_split(
    transactions: pl.LazyFrame,
    split: str,
    boundaries: tuple[dt.datetime, dt.datetime],
    *,
    test_end: dt.datetime | None = None,
) -> pl.DataFrame:
    """Return the feature frame for one split, history-correct.

    `test_end` bounds the test split; it defaults to just past the last row.
    """
    if split not in ("train", "validation", "test"):
        raise ValueError(f"unknown split: {split}")

    train_end, val_end = boundaries

    if split == "train":
        as_of = train_end
    elif split == "validation":
        as_of = val_end
    else:
        as_of = test_end or (
            transactions.select(pl.col("timestamp").max()).collect().item()
            + dt.timedelta(seconds=1)
        )

    with_basic = build_basic_features(transactions)
    with_history = build_account_history_features(with_basic, as_of=as_of)

    return (
        assign_split(with_history, boundaries)
        .filter(pl.col("split") == split)
        .sort("timestamp")
        .collect()
    )
