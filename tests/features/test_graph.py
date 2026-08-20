"""Account history features must only ever look backwards.

Leakage contract rule 3. Every one of these is an aggregate over an account's
past, and the whole risk is that "past" quietly becomes "all of it". The
frames below are tiny and hand-checked so a wrong answer is obvious.

The key case is `test_current_row_is_excluded`: an account's first transfer
must see a history of zero, not one. Off-by-one here means every row can see
itself, which is leakage that would look like a strong feature.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.features.graph import build_account_history_features

T0 = dt.datetime(2022, 9, 1, 0, 0)


def _tx(hours, frm, to, amount=100.0):
    return {
        "timestamp": T0 + dt.timedelta(hours=hours),
        "from_account": frm,
        "to_account": to,
        "amount_paid": amount,
        "is_laundering": 0,
    }


def _frame(rows):
    return pl.DataFrame(rows).lazy()


CUTOFF = T0 + dt.timedelta(days=30)


def _build(rows, as_of=CUTOFF):
    return build_account_history_features(_frame(rows), as_of=as_of).collect().sort("timestamp")


@pytest.mark.unit
def test_current_row_is_excluded_from_its_own_history():
    """An account's first transfer has seen nothing before it."""
    out = _build([_tx(0, "A", "B")])
    assert out["sender_n_sent_before"][0] == 0
    assert out["sender_amount_sent_before"][0] == 0.0


@pytest.mark.unit
def test_history_accumulates_in_time_order():
    out = _build([_tx(0, "A", "B"), _tx(1, "A", "C"), _tx(2, "A", "D")])
    assert out["sender_n_sent_before"].to_list() == [0, 1, 2]


@pytest.mark.unit
def test_history_is_per_account_not_global():
    out = _build([_tx(0, "A", "X"), _tx(1, "B", "X"), _tx(2, "A", "Y")])
    # rows: A(first)=0, B(first)=0, A(second)=1
    assert out["sender_n_sent_before"].to_list() == [0, 0, 1]


@pytest.mark.unit
def test_future_rows_never_contribute():
    """The whole point. Row 1 must not see row 2, whatever the order in."""
    forward = _build([_tx(0, "A", "B"), _tx(5, "A", "C")])
    assert forward["sender_n_sent_before"].to_list() == [0, 1]


@pytest.mark.unit
def test_as_of_drops_everything_at_or_after_the_cutoff():
    rows = [_tx(0, "A", "B"), _tx(48, "A", "C")]
    out = _build(rows, as_of=T0 + dt.timedelta(hours=24))
    assert out.height == 1


@pytest.mark.unit
def test_distinct_counterparties_counts_uniques_only():
    out = _build([_tx(0, "A", "B"), _tx(1, "A", "B"), _tx(2, "A", "C")])
    # before each row: {}, {B}, {B}
    assert out["sender_distinct_out_before"].to_list() == [0, 1, 1]


@pytest.mark.unit
def test_amount_sent_before_sums_the_past_only():
    out = _build([_tx(0, "A", "B", 10.0), _tx(1, "A", "C", 25.0)])
    assert out["sender_amount_sent_before"].to_list() == [0.0, 10.0]


@pytest.mark.unit
def test_receiver_history_is_tracked_too():
    out = _build([_tx(0, "X", "A"), _tx(1, "Y", "A")])
    assert out["receiver_n_received_before"].to_list() == [0, 1]


@pytest.mark.unit
def test_velocity_window_only_counts_recent_activity():
    """Two sends 100 hours apart are not a burst."""
    out = _build([_tx(0, "A", "B"), _tx(1, "A", "C"), _tx(100, "A", "D")])
    assert out["sender_sent_last_24h"].to_list() == [0, 1, 0]


@pytest.mark.unit
def test_seconds_since_previous_send_is_null_on_the_first():
    out = _build([_tx(0, "A", "B"), _tx(2, "A", "C")])
    assert out["sender_seconds_since_last_send"][0] is None
    assert out["sender_seconds_since_last_send"][1] == pytest.approx(7200)


@pytest.mark.unit
def test_row_order_in_the_input_does_not_change_the_answer():
    rows = [_tx(0, "A", "B"), _tx(1, "A", "C"), _tx(2, "A", "D")]
    forward = _build(rows)["sender_n_sent_before"].to_list()
    backward = _build(list(reversed(rows)))["sender_n_sent_before"].to_list()
    assert forward == backward
