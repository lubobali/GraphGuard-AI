"""Training is the truth (S6.2): the snapshot that seeds the stream equals it bit for bit.

A plain-Python reference walks a random history in (timestamp, source order) and computes
each feature the slow, obvious way. Three things must agree EXACTLY (==, never approx):

1. the training path (`features.graph`) with the reference -- so we know what training is
2. the snapshot (`account_states_frame`) + `to_model_row` with training, for each account's
   first transaction after the snapshot -- the stream starts from there
3. the recent send times with the 24 h count

The history is built to hurt: timestamps out of source order, many same-minute ties, hub
accounts, amounts with decimals and huge/small mixes (float addition is not associative),
and sends exactly 24 h before the cutoff. Measured on the real data first (S6.2 story).
"""

import datetime as dt
import math
import random

import polars as pl
import pytest

from graphguard.features.graph import build_account_history_features
from graphguard.serving.online_features import (
    AccountState,
    account_states_frame,
    recent_sends_frame,
    states_from_frame,
    to_model_row,
)

pytestmark = pytest.mark.unit

T0 = dt.datetime(2022, 9, 1)
AS_OF = T0 + dt.timedelta(days=3)
END = T0 + dt.timedelta(days=4)
HISTORY_COLS = (
    "sender_n_sent_before",
    "sender_amount_sent_before",
    "sender_distinct_out_before",
    "sender_sent_last_24h",
    "sender_seconds_since_last_send",
    "receiver_n_received_before",
    "receiver_amount_received_before",
    "receiver_distinct_in_before",
    "in_out_ratio_before",
)


def _history(n=30_000, seed=7) -> pl.DataFrame:
    rng = random.Random(seed)
    accounts = [f"A{i}" for i in range(400)]
    hubs = accounts[:5]
    minutes = int((END - T0).total_seconds() // 60)
    rows = []
    for _ in range(n):
        frm = rng.choice(hubs) if rng.random() < 0.3 else rng.choice(accounts)
        to = rng.choice(hubs) if rng.random() < 0.2 else rng.choice(accounts)
        # few distinct minutes -> heavy ties; source order is random w.r.t. time
        ts = T0 + dt.timedelta(minutes=rng.randrange(0, minutes, 7))
        amount = rng.choice([round(rng.uniform(0, 1e4), 2), round(rng.uniform(0, 1), 6), 1e12])
        rows.append((ts, frm, to, amount))
    # sends exactly 24 h before the cutoff, and exactly at it
    rows += [(AS_OF - dt.timedelta(hours=24), "A1", "A2", 0.1), (AS_OF, "A1", "A3", 0.2)]
    df = pl.DataFrame(
        rows, schema=["timestamp", "from_account", "to_account", "amount_paid"], orient="row"
    )
    return df.with_columns(pl.col("timestamp").cast(pl.Datetime("us")))


HISTORY = _history()


def _reference(df: pl.DataFrame) -> dict[int, dict]:
    """Every feature, the slow obvious way, keyed by source position."""
    order = sorted(range(df.height), key=lambda i: (df["timestamp"][i], i))
    sent_n, sent_amt, outs, sends = {}, {}, {}, {}
    recv_n, recv_amt, ins = {}, {}, {}
    out = {}
    ts_col, f_col, t_col, a_col = (
        df[c].to_list() for c in ("timestamp", "from_account", "to_account", "amount_paid")
    )
    for i in order:
        t, f, r, a = ts_col[i], f_col[i], t_col[i], a_col[i]
        s = sent_amt.get(f, 0.0)
        rv = recv_amt.get(r, 0.0)
        prev = sends.get(f, [])
        out[i] = {
            "sender_n_sent_before": sent_n.get(f, 0),
            "sender_amount_sent_before": (s + a) - a,
            "sender_distinct_out_before": len(outs.get(f, ())),
            "sender_sent_last_24h": sum(1 for p in prev if p > t - dt.timedelta(hours=24)),
            "sender_seconds_since_last_send": (t - prev[-1]).total_seconds() if prev else None,
            "receiver_n_received_before": recv_n.get(r, 0),
            "receiver_amount_received_before": (rv + a) - a,
            "receiver_distinct_in_before": len(ins.get(r, ())),
            "in_out_ratio_before": (recv_n.get(r, 0) + 1) / (sent_n.get(f, 0) + 1),
        }
        sent_n[f] = sent_n.get(f, 0) + 1
        sent_amt[f] = s + a
        outs.setdefault(f, set()).add(r)
        sends.setdefault(f, []).append(t)
        recv_n[r] = recv_n.get(r, 0) + 1
        recv_amt[r] = rv + a
        ins.setdefault(r, set()).add(f)
    return out


def _training(df: pl.DataFrame, as_of: dt.datetime) -> pl.DataFrame:
    return build_account_history_features(df.lazy().with_row_index("src"), as_of=as_of).collect()


def _same(a, b) -> bool:
    if a is None or (isinstance(a, float) and math.isnan(a)):
        return b is None or (isinstance(b, float) and math.isnan(b))
    return a == b


# --- 1. what training is ---------------------------------------------------------------
def test_training_equals_the_reference_exactly_on_every_row():
    ref = _reference(HISTORY.filter(pl.col("timestamp") < END))
    got = _training(HISTORY, END)
    bad = [
        (row["src"], c, row[c], ref[row["src"]][c])
        for row in got.iter_rows(named=True)
        for c in HISTORY_COLS
        if not _same(row[c], ref[row["src"]][c])
    ]
    assert bad == [], f"{len(bad)} mismatches, first: {bad[:3]}"


def test_the_history_really_has_ties_out_of_order_rows_and_a_float_trap():
    assert HISTORY.group_by("timestamp").len()["len"].max() > 1
    assert not HISTORY["timestamp"].is_sorted()
    hub = HISTORY.filter(pl.col("from_account") == "A0")["amount_paid"]
    seq = 0.0
    for a in hub:
        seq += a
    assert seq != hub.sum()  # Polars' compensated sum() is not the sequential one


# --- 2. the snapshot seeds exactly what training would have seen -----------------------
def _snapshot():
    frame = account_states_frame(HISTORY.lazy(), AS_OF)
    return frame, states_from_frame(frame, AS_OF)


def test_snapshot_plus_model_row_equals_training_at_each_accounts_next_transaction():
    frame, states = _snapshot()
    recent = recent_sends_frame(HISTORY.lazy(), AS_OF)
    training = _training(HISTORY, END)
    after = training.filter(pl.col("timestamp") >= AS_OF).sort(["timestamp", "src"])
    # first send after the cutoff per sender, first receive per receiver
    first_send = after.unique("from_account", keep="first", maintain_order=True)
    first_recv = after.unique("to_account", keep="first", maintain_order=True)
    checked = 0
    for row in first_send.iter_rows(named=True):
        st = states.get(row["from_account"]) or AccountState.cold(row["from_account"])
        online = to_model_row(
            sender=st,
            receiver=AccountState.cold("x"),
            timestamp=row["timestamp"],
            amount_paid=row["amount_paid"],
            amount_received=row["amount_paid"],
            from_bank="1",
            to_bank="2",
        )
        times = recent.filter(pl.col("account") == row["from_account"])["timestamp"]
        window = int((times > row["timestamp"] - dt.timedelta(hours=24)).sum())
        for c in (
            "sender_n_sent_before",
            "sender_amount_sent_before",
            "sender_distinct_out_before",
            "sender_seconds_since_last_send",
        ):
            assert _same(online[c], row[c]), (row["from_account"], c, online[c], row[c])
        assert window == row["sender_sent_last_24h"], (row["from_account"], window)
        checked += 1
    for row in first_recv.iter_rows(named=True):
        st = states.get(row["to_account"]) or AccountState.cold(row["to_account"])
        online = to_model_row(
            sender=AccountState.cold("x"),
            receiver=st,
            timestamp=row["timestamp"],
            amount_paid=row["amount_paid"],
            amount_received=row["amount_paid"],
            from_bank="1",
            to_bank="2",
        )
        for c in (
            "receiver_n_received_before",
            "receiver_amount_received_before",
            "receiver_distinct_in_before",
        ):
            assert _same(online[c], row[c]), (row["to_account"], c, online[c], row[c])
        checked += 1
    assert checked > 100  # guard the guard: the test really compared something


def test_snapshot_totals_are_the_sequential_running_total_not_sum():
    frame, _ = _snapshot()
    past = HISTORY.with_row_index("src").filter(pl.col("timestamp") < AS_OF)
    past = past.sort(["timestamp", "src"])
    for acct in ("A0", "A1", "A2"):
        seq = 0.0
        for a in past.filter(pl.col("from_account") == acct)["amount_paid"]:
            seq += a
        got = frame.filter(pl.col("account") == acct)["amount_sent"].item()
        assert got == seq


def test_a_send_exactly_24h_before_the_cutoff_is_outside_the_window():
    frame, _ = _snapshot()
    recent = recent_sends_frame(HISTORY.lazy(), AS_OF)
    edge = AS_OF - dt.timedelta(hours=24)
    assert edge not in recent.filter(pl.col("account") == "A1")["timestamp"].to_list()
    past = HISTORY.filter((pl.col("from_account") == "A1") & (pl.col("timestamp") < AS_OF))
    expected = int((past["timestamp"] > edge).sum())
    assert frame.filter(pl.col("account") == "A1")["sent_last_24h"].item() == expected


def test_recent_send_times_count_equals_the_snapshot_window_for_every_sender():
    frame, _ = _snapshot()
    counts = recent_sends_frame(HISTORY.lazy(), AS_OF).group_by("account").len()
    joined = frame.join(counts, on="account", how="left").with_columns(pl.col("len").fill_null(0))
    assert (joined["len"] == joined["sent_last_24h"]).all()


def test_a_send_at_the_cutoff_is_not_in_the_snapshot():
    frame, _ = _snapshot()
    recent = recent_sends_frame(HISTORY.lazy(), AS_OF)
    assert AS_OF not in recent["timestamp"].to_list()
    assert frame["last_sent"].max() < AS_OF


# --- the model row's "before" arithmetic -----------------------------------------------
def test_model_row_amount_before_repeats_trainings_arithmetic():
    s, a = 0.30000000000000004, 1e16  # (s + a) - a != s
    assert (s + a) - a != s
    st = AccountState(
        account="A",
        n_sent=1,
        n_received=1,
        amount_sent=s,
        amount_received=s,
        distinct_out=1,
        distinct_in=1,
        last_seen=T0,
        last_sent=T0,
    )
    row = to_model_row(
        sender=st,
        receiver=st,
        timestamp=T0 + dt.timedelta(hours=1),
        amount_paid=a,
        amount_received=a,
        from_bank="1",
        to_bank="2",
    )
    assert row["sender_amount_sent_before"] == (s + a) - a
    assert row["receiver_amount_received_before"] == (s + a) - a


def test_cold_account_amount_before_is_exactly_zero():
    cold = AccountState.cold("Z")
    row = to_model_row(
        sender=cold,
        receiver=cold,
        timestamp=T0,
        amount_paid=0.1,
        amount_received=0.1,
        from_bank="1",
        to_bank="2",
    )
    assert row["sender_amount_sent_before"] == 0.0 == row["receiver_amount_received_before"]
