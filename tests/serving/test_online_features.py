"""What the online store holds, and what a scoring request needs.

The whole point of this module is that the online path and the training path
compute the same numbers. If they drift, the deployed model behaves differently
from the one that was evaluated, and nothing fails -- the scores just quietly
become wrong.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.serving.online_features import (
    ACCOUNT_FEATURES,
    AccountState,
    build_account_states,
    to_model_row,
)

T0 = dt.datetime(2022, 9, 1)


def _tx(hours, frm, to, amount=100.0):
    return {
        "timestamp": T0 + dt.timedelta(hours=hours),
        "from_account": frm,
        "to_account": to,
        "amount_paid": amount,
        "is_laundering": 0,
    }


FRAME = pl.DataFrame([_tx(0, "A", "B"), _tx(1, "A", "C"), _tx(2, "D", "A", 50.0)]).lazy()


@pytest.mark.unit
def test_one_state_per_account_seen():
    states = build_account_states(FRAME, as_of=T0 + dt.timedelta(days=1))
    assert set(states) == {"A", "B", "C", "D"}


@pytest.mark.unit
def test_state_counts_what_the_account_sent():
    states = build_account_states(FRAME, as_of=T0 + dt.timedelta(days=1))
    assert states["A"].n_sent == 2
    assert states["A"].amount_sent == pytest.approx(200.0)


@pytest.mark.unit
def test_state_counts_what_the_account_received():
    states = build_account_states(FRAME, as_of=T0 + dt.timedelta(days=1))
    assert states["A"].n_received == 1
    assert states["A"].amount_received == pytest.approx(50.0)


@pytest.mark.unit
def test_distinct_counterparties_not_raw_count():
    frame = pl.DataFrame([_tx(0, "A", "B"), _tx(1, "A", "B")]).lazy()
    states = build_account_states(frame, as_of=T0 + dt.timedelta(days=1))
    assert states["A"].n_sent == 2
    assert states["A"].distinct_out == 1


@pytest.mark.unit
def test_state_respects_the_cutoff():
    """Nothing at or after as_of may be in the stored state."""
    states = build_account_states(FRAME, as_of=T0 + dt.timedelta(hours=1))
    assert states["A"].n_sent == 1  # the hour-1 send is excluded


@pytest.mark.unit
def test_unknown_account_yields_an_empty_state():
    """A brand new customer. Not an error -- a cold state, all zeros."""
    cold = AccountState.cold("NEVER_SEEN")
    assert cold.n_sent == 0
    assert cold.distinct_out == 0
    assert cold.is_cold is True


@pytest.mark.unit
def test_model_row_has_exactly_the_expected_columns():
    states = build_account_states(FRAME, as_of=T0 + dt.timedelta(days=1))
    row = to_model_row(
        sender=states["A"],
        receiver=states["B"],
        timestamp=T0 + dt.timedelta(days=1),
        amount_paid=500.0,
        amount_received=500.0,
        from_bank="01",
        to_bank="02",
    )
    for col in ACCOUNT_FEATURES:
        assert col in row


@pytest.mark.unit
def test_model_row_uses_sender_and_receiver_correctly():
    """Swapping the two accounts must change the row, or the graph is ignored."""
    states = build_account_states(FRAME, as_of=T0 + dt.timedelta(days=1))
    kwargs = dict(
        timestamp=T0 + dt.timedelta(days=1),
        amount_paid=500.0,
        amount_received=500.0,
        from_bank="01",
        to_bank="02",
    )
    forward = to_model_row(sender=states["A"], receiver=states["D"], **kwargs)
    backward = to_model_row(sender=states["D"], receiver=states["A"], **kwargs)
    assert forward["sender_n_sent_before"] != backward["sender_n_sent_before"]


@pytest.mark.unit
def test_cold_account_produces_a_scoreable_row():
    """A new customer must still be scoreable, not crash the service."""
    row = to_model_row(
        sender=AccountState.cold("NEW"),
        receiver=AccountState.cold("ALSO_NEW"),
        timestamp=T0,
        amount_paid=1.0,
        amount_received=1.0,
        from_bank="01",
        to_bank="01",
    )
    assert all(v is not None for v in row.values())
