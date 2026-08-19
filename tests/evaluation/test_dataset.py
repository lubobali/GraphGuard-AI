"""Loading a split must use the frozen boundaries, not recompute them."""

import datetime as dt

import polars as pl
import pytest

from graphguard.evaluation.dataset import attach_pattern_ids, frozen_boundaries


@pytest.mark.unit
def test_frozen_boundaries_come_from_the_split_file():
    train_end, val_end = frozen_boundaries()
    assert isinstance(train_end, dt.datetime)
    assert train_end < val_end


@pytest.mark.unit
def test_attach_pattern_ids_matches_on_the_full_key():
    trans = pl.DataFrame(
        {
            "timestamp": [dt.datetime(2022, 9, 1, 0, 6), dt.datetime(2022, 9, 1, 0, 7)],
            "from_account": ["A", "B"],
            "to_account": ["C", "D"],
            "amount_paid": [100.0, 200.0],
        }
    ).lazy()
    patterns = pl.DataFrame(
        {
            "timestamp": [dt.datetime(2022, 9, 1, 0, 6)],
            "from_account": ["A"],
            "to_account": ["C"],
            "amount_paid": [100.0],
            "pattern_id": [7],
        }
    )
    out = attach_pattern_ids(trans, patterns).collect().sort("from_account")
    assert out["pattern_id"].to_list() == [7, -1]


@pytest.mark.unit
def test_rows_in_no_pattern_get_the_sentinel():
    trans = pl.DataFrame(
        {
            "timestamp": [dt.datetime(2022, 9, 1)],
            "from_account": ["X"],
            "to_account": ["Y"],
            "amount_paid": [1.0],
        }
    ).lazy()
    patterns = pl.DataFrame(
        {
            "timestamp": [dt.datetime(2022, 9, 2)],
            "from_account": ["A"],
            "to_account": ["C"],
            "amount_paid": [100.0],
            "pattern_id": [7],
        }
    )
    assert attach_pattern_ids(trans, patterns).collect()["pattern_id"].to_list() == [-1]
