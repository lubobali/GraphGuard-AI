"""The temporal split, computed once and frozen.

Leakage contract rule 1: split by time, never randomly. The earliest window
trains, the middle validates, the latest tests. A random split would let a
model train on a transaction that happens after the one it is scoring, which
is information nobody has at decision time.

Two decisions are baked in here, both deliberate:

**The tail is truncated.** HI-Small is documented as Sep 1-10 but runs to Sep
18, and those extra 8 days are 57-73% laundering against 0.1% in the documented
period (FINDING-001). They are 1,108 rows holding 12.6% of all positives. Left
in, they would land in the test window and produce a majority-positive test set
whose precision@k means nothing. They are dropped, and the loss is stated.

**Boundaries are chosen by time quantile, not by calendar.** Daily volume in
this data swings from 1.1M to 207K, so equal calendar windows would be wildly
unbalanced. The boundaries are timestamps, so the split is still strictly
temporal; they are just picked so the row proportions come out near 60/20/20.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

# FINDING-001. Rows at or after this instant are dropped before splitting.
TAIL_CUTOFF = dt.datetime(2022, 9, 11)

DEFAULT_FRACTIONS = (0.6, 0.2)  # train, validation; test takes the remainder

SPLIT_NAMES = ("train", "validation", "test")


def truncate_tail(lf: pl.LazyFrame, cutoff: dt.datetime = TAIL_CUTOFF) -> pl.LazyFrame:
    """Drop the post-period tail described in FINDING-001."""
    return lf.filter(pl.col("timestamp") < cutoff)


def compute_boundaries(
    lf: pl.LazyFrame, fractions: tuple[float, float] = DEFAULT_FRACTIONS
) -> tuple[dt.datetime, dt.datetime]:
    """Return (train_end, val_end) as timestamps.

    Rows strictly before train_end train; before val_end validate; the rest
    test.
    """
    train_frac, val_frac = fractions
    q = lf.select(
        pl.col("timestamp").quantile(train_frac).alias("train_end"),
        pl.col("timestamp").quantile(train_frac + val_frac).alias("val_end"),
    ).collect()

    return q["train_end"][0], q["val_end"][0]


def assign_split(lf: pl.LazyFrame, boundaries: tuple[dt.datetime, dt.datetime]) -> pl.LazyFrame:
    """Label every row train / validation / test purely from its timestamp."""
    train_end, val_end = boundaries

    return lf.with_columns(
        pl.when(pl.col("timestamp") < train_end)
        .then(pl.lit("train"))
        .when(pl.col("timestamp") < val_end)
        .then(pl.lit("validation"))
        .otherwise(pl.lit("test"))
        .alias("split")
    )
