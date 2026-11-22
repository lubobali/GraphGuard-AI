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


# --- S7.2: the ring list as lakehouse rows ---------------------------------------------
def _ring_inputs():
    T = dt.datetime(2022, 9, 1, 0, 6)
    trans = pl.DataFrame(
        {
            "source_row": [0, 1, 2, 3],
            "timestamp": [T, T, T + dt.timedelta(days=1), T],
            "from_account": ["A", "B", "A", "A"],
            "to_account": ["C", "D", "C", "C"],
            "amount_paid": [100.0, 200.0, 100.0, 100.0],  # row 3 duplicates row 0's key
        }
    ).lazy()
    patterns = pl.DataFrame(
        {
            "timestamp": [T, T, T + dt.timedelta(days=1)],
            "from_account": ["A", "A", "A"],
            "to_account": ["C", "C", "C"],
            "amount_paid": [100.0, 100.0, 100.0],
            "pattern_id": [7, 9, 8],  # the same key twice: first match wins
            "pattern_type": ["FAN-OUT", "CYCLE", "FAN-OUT"],
            "pattern_detail": ["", "", ""],
            "hop": [0, 0, 1],
        }
    )
    return trans, patterns


@pytest.mark.unit
def test_ring_rows_give_exactly_the_ring_ids_the_evaluation_attaches():
    from graphguard.evaluation.dataset import ring_rows

    trans, patterns = _ring_inputs()
    rings = ring_rows(trans, patterns).collect().sort("source_row")
    attached = attach_pattern_ids(trans, patterns).collect().sort("source_row")
    in_ring = attached.filter(pl.col("pattern_id") != -1)
    assert rings["source_row"].to_list() == in_ring["source_row"].to_list() == [0, 2, 3]
    assert rings["pattern_id"].to_list() == in_ring["pattern_id"].to_list() == [7, 8, 7]
    assert rings.columns == ["source_row", "timestamp", "pattern_id", "pattern_type",
                             "pattern_detail", "hop"]  # fmt: skip
    assert rings.filter(pl.col("source_row") == 0)["pattern_type"].item() == "FAN-OUT"


@pytest.mark.unit
def test_attaching_ring_ids_keeps_the_rows_in_their_order():
    # features break same-minute ties by input order (FINDING-015), so this join must not
    # reorder rows; Polars only promises that with maintain_order (found in S7.2)
    n = 50_000
    trans = pl.DataFrame({
        "timestamp": [dt.datetime(2022, 9, 1)] * n,
        "from_account": [f"A{i}" for i in range(n)],
        "to_account": ["B"] * n,
        "amount_paid": [1.0] * n,
    }).lazy()  # fmt: skip
    patterns = pl.DataFrame(
        {
            "timestamp": [dt.datetime(2022, 9, 1)],
            "from_account": ["A7"],
            "to_account": ["B"],
            "amount_paid": [1.0],
            "pattern_id": [3],
        }
    )
    out = attach_pattern_ids(trans, patterns).collect()
    assert out["from_account"].to_list() == [f"A{i}" for i in range(n)]
