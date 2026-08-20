"""Point-in-time features from the transaction row itself.

These are the safe ones: every value comes from the row being scored, so
nothing from the future can leak in. They are still tested, because a wrong
hour-of-day or a silently-null currency degrades the model without failing
anything.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.features.basic import build_basic_features


def _row(**over):
    base = {
        "timestamp": dt.datetime(2022, 9, 1, 14, 30),
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
    base.update(over)
    return base


def _frame(rows):
    return pl.DataFrame(rows).lazy()


@pytest.mark.unit
def test_hour_and_weekday_are_extracted():
    out = build_basic_features(_frame([_row()])).collect()
    assert out["hour"][0] == 14
    assert out["weekday"][0] == 4  # 2022-09-01 was a Thursday


@pytest.mark.unit
def test_log_amount_compresses_the_range():
    """Amounts span 0.01 to billions; the raw scale swamps a tree's splits."""
    out = build_basic_features(_frame([_row(amount_paid=1000.0)])).collect()
    assert out["log_amount"][0] == pytest.approx(pl.Series([1000.0]).log1p()[0])


@pytest.mark.unit
def test_zero_amount_does_not_produce_nan():
    """0.01 amounts exist in this data; log(0) would poison the column."""
    out = build_basic_features(_frame([_row(amount_paid=0.0)])).collect()
    assert out["log_amount"][0] == 0.0
    assert not out["log_amount"].is_nan().any()


@pytest.mark.unit
def test_cross_currency_is_flagged():
    same = build_basic_features(_frame([_row()])).collect()
    diff = build_basic_features(
        _frame([_row(receiving_currency="Euro", payment_currency="US Dollar")])
    ).collect()
    assert same["is_cross_currency"][0] == 0
    assert diff["is_cross_currency"][0] == 1


@pytest.mark.unit
def test_self_transfer_is_flagged():
    """Reinvestment rows send an account to itself and are very common here."""
    out = build_basic_features(_frame([_row(to_account="A")])).collect()
    assert out["is_self_transfer"][0] == 1


@pytest.mark.unit
def test_same_bank_is_flagged():
    out = build_basic_features(_frame([_row(to_bank="010")])).collect()
    assert out["is_same_bank"][0] == 1


@pytest.mark.unit
def test_amount_mismatch_captures_fx_gap():
    out = build_basic_features(_frame([_row(amount_paid=100.0, amount_received=90.0)])).collect()
    assert out["amount_ratio"][0] == pytest.approx(0.9)


@pytest.mark.unit
def test_original_columns_survive():
    out = build_basic_features(_frame([_row()])).collect()
    for col in ("timestamp", "from_account", "to_account", "is_laundering"):
        assert col in out.columns
