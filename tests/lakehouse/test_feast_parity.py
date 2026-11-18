"""The Feast-vs-ours comparison (S5.6e) must catch every kind of difference."""

import datetime as dt

import pytest

from graphguard.lakehouse.feast_parity import compare
from graphguard.serving.online_features import AccountState

pytestmark = pytest.mark.unit

T = dt.datetime(2022, 9, 6, 13, 33)


def _state(**kw):
    base = dict(
        account="A",
        n_sent=3,
        n_received=1,
        amount_sent=1234.56,
        amount_received=10.0,
        distinct_out=2,
        distinct_in=1,
        sent_last_24h=1,
        last_seen=T,
        last_sent=T,
        materialised_at=T,
    )
    return AccountState(**{**base, **kw})


def _row(**kw):
    s = _state()
    row = {
        c: getattr(s, c)
        for c in (
            "account",
            "n_sent",
            "n_received",
            "amount_sent",
            "amount_received",
            "distinct_out",
            "distinct_in",
            "sent_last_24h",
            "last_seen",
            "last_sent",
        )
    }
    row["last_seen"] = row["last_sent"] = T.replace(tzinfo=dt.UTC)  # Feast returns UTC
    return {**row, **kw}


def test_identical_values_are_identical_even_across_timezones():
    assert compare([_row()], {"A": _state()}).identical


def test_a_count_difference_is_caught():
    p = compare([_row(n_sent=4)], {"A": _state()})
    assert not p.identical and p.differences["n_sent"] == 1


def test_money_must_match_bit_for_bit():
    p = compare([_row(amount_sent=1234.56 + 2e-13)], {"A": _state()})
    assert p.differences["amount_sent"] == 1


def test_a_timestamp_one_minute_off_is_caught():
    p = compare(
        [_row(last_seen=(T + dt.timedelta(minutes=1)).replace(tzinfo=dt.UTC))], {"A": _state()}
    )
    assert p.differences["last_seen"] == 1


def test_missing_accounts_on_either_side_are_counted():
    gone = {
        c: None
        for c in (
            "n_sent",
            "n_received",
            "amount_sent",
            "amount_received",
            "distinct_out",
            "distinct_in",
            "sent_last_24h",
        )
    }
    p = compare([_row(account="B"), _row(**gone)], {"A": _state()})
    assert (p.missing_in_ours, p.missing_in_feast) == (1, 1) and not p.identical
