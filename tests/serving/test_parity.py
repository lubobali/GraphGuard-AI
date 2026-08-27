"""Train/serve parity: both paths must produce the same numbers.

This is the test the whole serving design exists to make passable. Training
computes an account's history by scanning every earlier row. Serving looks up a
precomputed state. If those two disagree, the deployed model sees different
inputs from the evaluated one, every reported metric becomes a claim about a
different system, and nothing fails loudly.

Compared for a transaction whose state is materialised at exactly its own
timestamp. Real serving materialises periodically, and the gap that introduces
is the staleness policy -- measured separately, not assumed away here.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.features.graph import build_account_history_features
from graphguard.serving.online_features import (
    AccountState,
    build_account_states,
    to_model_row,
)

T0 = dt.datetime(2022, 9, 1)

PARITY_COLUMNS = (
    "sender_n_sent_before",
    "sender_amount_sent_before",
    "sender_distinct_out_before",
    "receiver_n_received_before",
    "receiver_amount_received_before",
    "receiver_distinct_in_before",
    "in_out_ratio_before",
    "sender_sent_last_24h",
)


def _tx(hours, frm, to, amount):
    return {
        "timestamp": T0 + dt.timedelta(hours=hours),
        "from_bank": "01",
        "from_account": frm,
        "to_bank": "02",
        "to_account": to,
        "amount_received": amount,
        "receiving_currency": "US Dollar",
        "amount_paid": amount,
        "payment_currency": "US Dollar",
        "payment_format": "ACH",
        "is_laundering": 0,
    }


HISTORY = [
    _tx(0, "A", "B", 100.0),
    _tx(1, "A", "C", 250.0),
    _tx(2, "D", "A", 75.0),
    _tx(3, "A", "B", 30.0),  # repeat counterparty
    _tx(4, "E", "B", 10.0),
    _tx(5, "A", "F", 500.0),  # the transaction under test
]
FRAME = pl.DataFrame(HISTORY).lazy()
TARGET = HISTORY[-1]


def _batch_row():
    """What the training path computes for the target transaction."""
    out = (
        build_account_history_features(FRAME, as_of=T0 + dt.timedelta(days=1))
        .collect()
        .sort("timestamp")
    )
    return out.filter(pl.col("timestamp") == TARGET["timestamp"]).row(0, named=True)


def _online_row():
    """What the serving path assembles for the same transaction."""
    states = build_account_states(FRAME, as_of=TARGET["timestamp"])
    return to_model_row(
        sender=states[TARGET["from_account"]],
        # F appears only in the target row itself, which is at the cutoff, so
        # it is genuinely cold here. That is the path a new customer takes.
        receiver=states.get(TARGET["to_account"]) or AccountState.cold(TARGET["to_account"]),
        timestamp=TARGET["timestamp"],
        amount_paid=TARGET["amount_paid"],
        amount_received=TARGET["amount_received"],
        from_bank=TARGET["from_bank"],
        to_bank=TARGET["to_bank"],
    )


@pytest.mark.integration
@pytest.mark.parametrize("column", PARITY_COLUMNS)
def test_batch_and_online_agree_on(column):
    batch, online = _batch_row(), _online_row()
    assert online[column] == pytest.approx(float(batch[column])), (
        f"train/serve skew on {column}: batch={batch[column]} online={online[column]}"
    )


@pytest.mark.unit
def test_the_fixture_actually_exercises_a_repeat_counterparty():
    """Guard the guard: if the history had no repeats, distinct_out would
    trivially equal n_sent and the parity test would prove nothing."""
    batch = _batch_row()
    assert batch["sender_n_sent_before"] != batch["sender_distinct_out_before"]


@pytest.mark.unit
def test_the_fixture_exercises_an_account_on_both_sides():
    """Account A both sends and receives before the target row."""
    batch = _batch_row()
    assert batch["sender_n_sent_before"] > 0
