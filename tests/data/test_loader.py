"""The loader must survive the raw file's quirks, not assume them away.

The transactions CSV ships two columns both literally named "Account" -- the
sender and the receiver. Loading naively drops one of them silently, which
would quietly destroy the graph. These tests pin the behaviour.
"""

import polars as pl
import pytest

from graphguard.data.loader import CANONICAL_COLUMNS, load_transactions, summarise

RAW_HEADER = (
    "Timestamp,From Bank,Account,To Bank,Account,Amount Received,"
    "Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering"
)


def _write(tmp_path, rows):
    path = tmp_path / "trans.csv"
    path.write_text(RAW_HEADER + "\n" + "\n".join(rows) + "\n")
    return path


ROW_CLEAN = (
    "2022/09/01 00:20,010,8000EBD30,011,8000F5340,100.00,US Dollar,100.00,US Dollar,Cheque,0"
)
ROW_DIRTY = "2022/09/02 13:05,012,8000AAA10,013,8000BBB20,250.50,Euro,250.50,Euro,ACH,1"


@pytest.mark.unit
def test_both_account_columns_survive(tmp_path):
    """The duplicate 'Account' header must become two distinct columns."""
    lf = load_transactions(_write(tmp_path, [ROW_CLEAN]))
    df = lf.collect()
    assert "from_account" in df.columns
    assert "to_account" in df.columns
    assert df["from_account"][0] == "8000EBD30"
    assert df["to_account"][0] == "8000F5340"


@pytest.mark.unit
def test_all_columns_are_renamed(tmp_path):
    df = load_transactions(_write(tmp_path, [ROW_CLEAN])).collect()
    assert df.columns == list(CANONICAL_COLUMNS)


@pytest.mark.unit
def test_timestamp_is_parsed_as_datetime(tmp_path):
    df = load_transactions(_write(tmp_path, [ROW_CLEAN])).collect()
    assert df["timestamp"].dtype == pl.Datetime


@pytest.mark.unit
def test_account_ids_stay_strings(tmp_path):
    """Account IDs are hex-ish and must not be coerced to numbers."""
    df = load_transactions(_write(tmp_path, [ROW_CLEAN])).collect()
    assert df["from_account"].dtype == pl.String
    assert df["from_bank"].dtype == pl.String


@pytest.mark.unit
def test_summarise_reports_shape_dates_and_balance(tmp_path):
    lf = load_transactions(_write(tmp_path, [ROW_CLEAN, ROW_DIRTY]))
    s = summarise(lf)
    assert s["n_transactions"] == 2
    assert s["n_laundering"] == 1
    assert s["laundering_rate"] == pytest.approx(0.5)
    assert s["date_min"].day == 1
    assert s["date_max"].day == 2


@pytest.mark.unit
def test_summarise_counts_distinct_accounts_across_both_sides(tmp_path):
    """An account appearing only as a receiver still counts."""
    lf = load_transactions(_write(tmp_path, [ROW_CLEAN, ROW_DIRTY]))
    assert summarise(lf)["n_accounts"] == 4


@pytest.mark.unit
def test_laundering_rate_is_zero_when_no_positives(tmp_path):
    lf = load_transactions(_write(tmp_path, [ROW_CLEAN]))
    assert summarise(lf)["laundering_rate"] == 0.0
