"""Data contracts must fail loudly on bad data, not pass it through.

A column that silently changes type, or a null rate that jumps, degrades the
model without failing anything. These tests check the schemas actually reject
the failures they exist to catch -- a schema that accepts everything is worse
than no schema, because it looks like protection.
"""

import datetime as dt

import polars as pl
import pytest
from pandera.errors import SchemaError

from graphguard.features.schemas import (
    validate_features,
    validate_raw_transactions,
)

T0 = dt.datetime(2022, 9, 1)


def _raw(**over):
    row = {
        "timestamp": T0,
        "from_bank": "010",
        "from_account": "A",
        "to_bank": "011",
        "to_account": "B",
        "amount_received": 100.0,
        "receiving_currency": "US Dollar",
        "amount_paid": 100.0,
        "payment_currency": "US Dollar",
        "payment_format": "Cheque",
        "is_laundering": 0,
    }
    row.update(over)
    return pl.DataFrame([row])


@pytest.mark.unit
def test_valid_raw_data_passes():
    assert validate_raw_transactions(_raw()).height == 1


@pytest.mark.unit
def test_account_id_coerced_to_a_number_is_rejected():
    """Account IDs have leading zeros; as integers, distinct accounts merge.

    "0123" and "123" are different accounts in this data. Cast to Int64 they
    become the same number, and the graph silently gains a wrong edge.
    """
    numeric_looking = _raw(from_account="0123")
    with pytest.raises(SchemaError):
        validate_raw_transactions(
            numeric_looking.with_columns(pl.col("from_account").cast(pl.Int64))
        )


@pytest.mark.unit
def test_negative_amount_is_rejected():
    with pytest.raises(SchemaError):
        validate_raw_transactions(_raw(amount_paid=-1.0))


@pytest.mark.unit
def test_label_outside_zero_one_is_rejected():
    with pytest.raises(SchemaError):
        validate_raw_transactions(_raw(is_laundering=2))


@pytest.mark.unit
def test_null_account_is_rejected():
    with pytest.raises(SchemaError):
        validate_raw_transactions(_raw(from_account=None))


def _features(**over):
    row = {
        "hour": 12,
        "weekday": 4,
        "log_amount": 4.6,
        "amount_ratio": 1.0,
        "is_cross_currency": 0,
        "is_self_transfer": 0,
        "is_same_bank": 0,
        "sender_n_sent_before": 0,
        "sender_amount_sent_before": 0.0,
        "sender_distinct_out_before": 0,
        "sender_sent_last_24h": 0,
        "receiver_n_received_before": 0,
        "receiver_amount_received_before": 0.0,
        "receiver_distinct_in_before": 0,
        "in_out_ratio_before": 1.0,
        "is_laundering": 0,
    }
    row.update(over)
    return pl.DataFrame([row])


@pytest.mark.unit
def test_valid_features_pass():
    assert validate_features(_features()).height == 1


@pytest.mark.unit
def test_negative_history_count_is_rejected():
    """The classic off-by-one: cum_count minus one, done wrong, goes to -1."""
    with pytest.raises(SchemaError):
        validate_features(_features(sender_n_sent_before=-1))


@pytest.mark.unit
def test_impossible_hour_is_rejected():
    with pytest.raises(SchemaError):
        validate_features(_features(hour=25))


@pytest.mark.unit
def test_nan_in_a_feature_is_rejected():
    """log(0) and 0/0 both produce NaN, and a tree will happily train on it."""
    with pytest.raises(SchemaError):
        validate_features(_features(in_out_ratio_before=float("nan")))
