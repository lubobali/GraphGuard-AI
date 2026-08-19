"""The temporal split must be temporal, exhaustive and non-overlapping.

Leakage contract rule 1: split by time, never randomly. Earliest window
trains, middle validates, latest tests. These tests pin that a row's split is
decided purely by its timestamp, that every row lands in exactly one split,
and that the three windows do not overlap in time.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.evaluation.split import (
    TAIL_CUTOFF,
    assign_split,
    compute_boundaries,
    truncate_tail,
)


def _frame(n=100, start=dt.datetime(2022, 9, 1)):
    return pl.DataFrame(
        {
            "timestamp": [start + dt.timedelta(hours=i) for i in range(n)],
            "is_laundering": [0] * n,
        }
    ).lazy()


@pytest.mark.unit
def test_boundaries_are_ordered():
    train_end, val_end = compute_boundaries(_frame())
    assert train_end < val_end


@pytest.mark.unit
def test_split_proportions_are_roughly_as_asked():
    lf = _frame(1000)
    b = compute_boundaries(lf, fractions=(0.6, 0.2))
    counts = assign_split(lf, b).collect()["split"].value_counts().sort("split")
    got = dict(zip(counts["split"], counts["count"], strict=True))
    assert got["train"] == pytest.approx(600, abs=5)
    assert got["validation"] == pytest.approx(200, abs=5)
    assert got["test"] == pytest.approx(200, abs=5)


@pytest.mark.unit
def test_every_row_gets_exactly_one_split():
    lf = _frame(250)
    out = assign_split(lf, compute_boundaries(lf)).collect()
    assert out.height == 250
    assert out["split"].null_count() == 0
    assert set(out["split"].unique()) == {"train", "validation", "test"}


@pytest.mark.unit
def test_windows_do_not_overlap_in_time():
    lf = _frame(300)
    out = assign_split(lf, compute_boundaries(lf)).collect()
    tr = out.filter(pl.col("split") == "train")["timestamp"]
    va = out.filter(pl.col("split") == "validation")["timestamp"]
    te = out.filter(pl.col("split") == "test")["timestamp"]
    assert tr.max() < va.min()
    assert va.max() < te.min()


@pytest.mark.unit
def test_split_is_decided_by_time_not_row_order():
    """Shuffling the input must not change any row's split."""
    lf = _frame(200)
    b = compute_boundaries(lf)
    ordered = assign_split(lf, b).collect().sort("timestamp")
    shuffled = assign_split(lf.collect().sample(fraction=1.0, shuffle=True, seed=1).lazy(), b)
    assert shuffled.collect().sort("timestamp")["split"].to_list() == ordered["split"].to_list()


@pytest.mark.unit
def test_truncate_tail_drops_rows_at_or_after_the_cutoff():
    """FINDING-001: the post-period tail is 57-73% laundering and is removed."""
    lf = pl.DataFrame(
        {
            "timestamp": [
                dt.datetime(2022, 9, 10, 23, 59),
                TAIL_CUTOFF,
                dt.datetime(2022, 9, 18),
            ],
            "is_laundering": [0, 1, 1],
        }
    ).lazy()
    kept = truncate_tail(lf).collect()
    assert kept.height == 1
    assert kept["timestamp"][0] < TAIL_CUTOFF
