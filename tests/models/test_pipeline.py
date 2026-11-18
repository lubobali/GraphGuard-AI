"""Building features for a later split must use earlier data as history.

A validation row's history legitimately includes training-window activity --
that is its past. What it must never include is anything at or after itself.
Getting this wrong in either direction is a bug: excluding the training window
cripples the model, including the future inflates it.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.models.pipeline import features_for_split


def _tx(day, frm, to):
    return {
        "timestamp": dt.datetime(2022, 9, day),
        "from_bank": "01",
        "from_account": frm,
        "to_bank": "02",
        "to_account": to,
        "amount_received": 100.0,
        "receiving_currency": "US Dollar",
        "amount_paid": 100.0,
        "payment_currency": "US Dollar",
        "payment_format": "ACH",
        "is_laundering": 0,
        "pattern_id": -1,
    }


# A sends on day 1 (train), day 5 (validation), day 9 (test)
FRAME = pl.DataFrame([_tx(1, "A", "B"), _tx(5, "A", "C"), _tx(9, "A", "D")]).lazy()
TRAIN_END = dt.datetime(2022, 9, 4)
VAL_END = dt.datetime(2022, 9, 8)
BOUNDARIES = (TRAIN_END, VAL_END)


@pytest.mark.unit
def test_train_split_sees_only_its_own_window():
    out = features_for_split(FRAME, "train", BOUNDARIES)
    assert out.height == 1
    assert out["sender_n_sent_before"][0] == 0


@pytest.mark.unit
def test_validation_history_includes_the_training_window():
    """The day-1 send is the day-5 row's genuine past and must count."""
    out = features_for_split(FRAME, "validation", BOUNDARIES)
    assert out.height == 1
    assert out["sender_n_sent_before"][0] == 1


@pytest.mark.unit
def test_validation_never_sees_the_test_window():
    out = features_for_split(FRAME, "validation", BOUNDARIES)
    assert out["sender_n_sent_before"][0] == 1  # not 2


@pytest.mark.unit
def test_only_rows_of_the_requested_split_are_returned():
    out = features_for_split(FRAME, "validation", BOUNDARIES)
    assert out["timestamp"].to_list() == [dt.datetime(2022, 9, 5)]


@pytest.mark.unit
def test_unknown_split_is_rejected():
    with pytest.raises(ValueError):
        features_for_split(FRAME, "holdout", BOUNDARIES)
