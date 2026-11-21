"""The S6.2 proof on the REAL data: the train_end snapshot equals training, every account.

For every account active in validation, its first validation send (and first receive) is
scored by training with full history; the snapshot taken at `train_end` plus
`to_model_row` must give exactly the same features (==, no tolerance), and the recent send
times must give the same 24 h count. Train + validation rows only (`< val_end`): the test
window is never read. Slow (~2 min, ~1.5 GB); needs the dataset on disk.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.config import TRANSACTIONS_FILE
from graphguard.evaluation.dataset import frozen_boundaries
from graphguard.features.graph import build_account_history_features
from graphguard.serving.online_features import (
    AccountState,
    account_states_frame,
    recent_sends_frame,
    states_from_frame,
    to_model_row,
)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not TRANSACTIONS_FILE.exists(), reason="dataset not downloaded"),
]

SEND_COLS = (
    "sender_n_sent_before",
    "sender_amount_sent_before",
    "sender_distinct_out_before",
    "sender_seconds_since_last_send",
)
RECV_COLS = (
    "receiver_n_received_before",
    "receiver_amount_received_before",
    "receiver_distinct_in_before",
)


def _row(sender, receiver, r):
    return to_model_row(
        sender=sender,
        receiver=receiver,
        timestamp=r["timestamp"],
        amount_paid=r["amount_paid"],
        amount_received=r["amount_received"],
        from_bank="1",
        to_bank="2",
    )


def _same(a, b):
    nan = lambda v: v is None or v != v  # noqa: E731
    return (nan(a) and nan(b)) or a == b


@pytest.fixture(scope="module")
def data():
    from graphguard.data.loader import load_transactions

    train_end, val_end = frozen_boundaries()
    lf = load_transactions(TRANSACTIONS_FILE)
    lf = lf.lazy() if isinstance(lf, pl.DataFrame) else lf
    lf = lf.with_row_index("src").filter(pl.col("timestamp") < val_end)  # never the test window
    training = build_account_history_features(lf, as_of=val_end).collect()
    after = training.filter(pl.col("timestamp") >= train_end).sort(["timestamp", "src"])
    frame = account_states_frame(lf, train_end)
    return {
        "states": states_from_frame(frame, train_end),
        "recent": recent_sends_frame(lf, train_end),
        "first_send": after.unique("from_account", keep="first", maintain_order=True),
        "first_recv": after.unique("to_account", keep="first", maintain_order=True),
    }


def test_every_senders_first_validation_send_matches_training(data):
    states, cold = data["states"], AccountState.cold("x")
    windows = dict(data["recent"].group_by("account").agg("timestamp").iter_rows())
    bad, n = [], 0
    for r in data["first_send"].iter_rows(named=True):
        acct = r["from_account"]
        online = _row(states.get(acct) or AccountState.cold(acct), cold, r)
        for c in SEND_COLS:
            if not _same(online[c], r[c]):
                bad.append((acct, c, online[c], r[c]))
        cutoff = r["timestamp"] - dt.timedelta(hours=24)
        window = sum(1 for t in windows.get(acct, []) if t > cutoff)
        if window != r["sender_sent_last_24h"]:
            bad.append((acct, "sent_last_24h", window, r["sender_sent_last_24h"]))
        n += 1
    assert n > 100_000
    assert bad == [], f"{len(bad)} mismatches of {n} senders; first: {bad[:5]}"


def test_every_receivers_first_validation_receive_matches_training(data):
    states, cold = data["states"], AccountState.cold("x")
    bad, n = [], 0
    for r in data["first_recv"].iter_rows(named=True):
        acct = r["to_account"]
        online = _row(cold, states.get(acct) or AccountState.cold(acct), r)
        bad += [(acct, c, online[c], r[c]) for c in RECV_COLS if not _same(online[c], r[c])]
        n += 1
    assert n > 100_000
    assert bad == [], f"{len(bad)} mismatches of {n} receivers; first: {bad[:5]}"
