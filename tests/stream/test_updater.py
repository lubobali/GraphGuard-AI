"""Live features (S6.3): each event returns both accounts' state BEFORE it, then applies it.

The reference is training itself (`features.graph`): replaying a history through the
updater in micro-batches must give exactly (==) the features training computes for every
row. Then the hard cases: repeats, a crash between Redis and Postgres, late events, ties
arriving shuffled, and the 24 h edge. Memory store here; the Redis store is proven equal to
it in test_updater_redis_live.py.
"""

import datetime as dt
import random

import polars as pl
import pytest

from graphguard.features.graph import build_account_history_features
from graphguard.serving.online_features import (
    account_states_frame,
    recent_sends_frame,
    to_model_row,
)
from graphguard.stream import updater as up

pytestmark = pytest.mark.unit

T0 = dt.datetime(2022, 9, 1)
SEED_AT = T0 + dt.timedelta(days=2)
END = T0 + dt.timedelta(days=4)
COLS = (
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


def _history(n=20_000, seed=3) -> pl.DataFrame:
    rng = random.Random(seed)
    accts = [f"A{i}" for i in range(300)]
    minutes = int((END - T0).total_seconds() // 60)
    rows = []
    for _ in range(n):
        f = rng.choice(accts[:4]) if rng.random() < 0.3 else rng.choice(accts)
        t = f if rng.random() < 0.01 else rng.choice(accts)  # some self-transfers
        ts = T0 + dt.timedelta(minutes=rng.randrange(0, minutes, 5))
        rows.append((ts, f, t, rng.choice([round(rng.uniform(0, 1e4), 2), 1e12, 0.1])))
    rows.append((SEED_AT + dt.timedelta(hours=1), "A1", "A2", 0.3))
    rows.append((SEED_AT - dt.timedelta(hours=23), "A1", "A2", 0.3))  # leaves the window at +1h
    df = pl.DataFrame(rows, schema=["timestamp", "from_account", "to_account", "amount_paid"],
                      orient="row")  # fmt: skip
    return df.with_columns(pl.col("timestamp").cast(pl.Datetime("us"))).with_row_index("source_row")


HISTORY = _history()


def _events(df: pl.DataFrame) -> list[up.Event]:
    return [up.Event(r["source_row"], r["timestamp"], r["from_account"], r["to_account"],
                     r["amount_paid"]) for r in df.iter_rows(named=True)]  # fmt: skip


def _seeded_store() -> up.MemoryStore:
    past = HISTORY.lazy()
    store = up.MemoryStore()
    up.seed(
        store,
        account_states_frame(past.drop("source_row"), SEED_AT),
        recent_sends_frame(past.drop("source_row"), SEED_AT),
        up.edges_frame(past.drop("source_row"), SEED_AT),
        SEED_AT,
    )
    return store


def _stream_part() -> pl.DataFrame:
    return HISTORY.filter(pl.col("timestamp") >= SEED_AT).sort("timestamp", "source_row")


def _features(before: up.Before, e: up.Event) -> dict:
    return to_model_row(sender=before.sender, receiver=before.receiver, timestamp=e.timestamp,
                        amount_paid=e.amount_paid, amount_received=e.amount_paid,
                        from_bank="1", to_bank="2")  # fmt: skip


def _training_rows() -> dict[int, dict]:
    t = build_account_history_features(HISTORY.lazy(), as_of=END).collect()
    return {r["source_row"]: r for r in t.iter_rows(named=True)}


TRAINING = _training_rows()


def _mismatches(results: list[tuple[up.Event, up.Before]]) -> list:
    bad = []
    for e, before in results:
        got, want = _features(before, e), TRAINING[e.source_row]
        for c in COLS:
            a, b = got[c], want[c]
            if not ((a != a and (b is None or b != b)) or a == b):
                bad.append((e.source_row, c, a, b))
    return bad


def _run(store, events, batch=97):
    out = []
    for i in range(0, len(events), batch):
        chunk = events[i : i + batch]
        out += list(zip(sorted(chunk, key=up.order), store.apply(chunk), strict=True))
    return out


# --- the proof, in miniature (the full one runs on the real validation window) -------
def test_replaying_the_stream_gives_trainings_features_on_every_row():
    store = _seeded_store()
    results = _run(store, _events(_stream_part()))
    assert all(b.status == "applied" for _, b in results)
    assert len(results) > 9_000
    bad = _mismatches(results)
    assert bad == [], f"{len(bad)} mismatches; first {bad[:3]}"


@pytest.mark.parametrize("batch", [1, 7, 500, 100_000])
def test_batch_size_does_not_change_any_feature(batch):
    store = _seeded_store()
    assert _mismatches(_run(store, _events(_stream_part()), batch)) == []


# --- repeats, crashes, late events ---------------------------------------------------
def test_an_event_delivered_twice_applies_once_and_returns_the_same_features():
    store = _seeded_store()
    events = _events(_stream_part())[:300]
    first = store.apply(events)
    again = store.apply(events[100:200])
    assert [b.status for b in again] == ["replayed"] * 100
    assert [(b.sender, b.receiver) for b in again] == [
        (b.sender, b.receiver) for b in first[100:200]
    ]
    rest = _run(store, _events(_stream_part())[300:])
    assert _mismatches(rest) == []  # nothing was counted twice


def test_a_duplicate_inside_one_batch_is_replayed_not_applied():
    store = _seeded_store()
    e = _events(_stream_part())[:5]
    out = store.apply([*e, e[2]])
    assert [b.status for b in out].count("replayed") == 1
    assert _mismatches(_run(store, _events(_stream_part())[5:])) == []


def test_crash_after_redis_before_postgres_gives_back_the_same_features():
    store = _seeded_store()
    events = _events(_stream_part())[:50]
    first = store.apply(events)  # Redis applied; then the consumer died before Postgres
    after_restart = store.apply(events)  # Kafka redelivers from the last stored offset
    assert all(b.status == "replayed" for b in after_restart)
    assert [_features(b, e) for b, e in zip(after_restart, events, strict=True)] == [
        _features(b, e) for b, e in zip(first, events, strict=True)
    ]


def test_acked_events_are_forgotten_but_still_never_applied_twice():
    store = _seeded_store()
    events = _events(_stream_part())[:50]
    store.apply(events)
    store.ack([e.source_row for e in events])  # decisions stored: pending records go
    again = store.apply(events)
    assert all(b.status == "late" for b in again)  # older than the watermark: refused
    assert _mismatches(_run(store, _events(_stream_part())[50:])) == []


def test_a_late_event_is_refused_and_changes_nothing():
    store = _seeded_store()
    events = _events(_stream_part())
    store.apply(events[:200])
    late = events[150]
    late = up.Event(10**9, late.timestamp, late.from_account, late.to_account, late.amount_paid)
    (b,) = store.apply([late])
    assert b.status == "late"
    assert _mismatches(_run(store, events[200:])) == []


# --- ties and the 24 h edge ----------------------------------------------------------
def test_same_minute_events_arriving_shuffled_are_applied_in_source_order():
    store = _seeded_store()
    events = _events(_stream_part())
    batch = events[:400]
    shuffled = batch[:]
    random.Random(1).shuffle(shuffled)
    out = store.apply(shuffled)
    assert _mismatches(list(zip(sorted(shuffled, key=up.order), out, strict=True))) == []


NO_EDGES = pl.DataFrame(schema={"from_account": pl.String, "to_account": pl.String})


def test_a_send_exactly_24h_earlier_is_out_of_the_window():
    store = up.MemoryStore()
    t = SEED_AT
    up.seed(store, account_states_frame(pl.LazyFrame(schema=HISTORY.drop("source_row").schema), t),
            pl.DataFrame({"account": ["X"], "timestamp": [t - dt.timedelta(hours=24)]}),
            NO_EDGES, t)  # fmt: skip
    (b,) = store.apply([up.Event(1, t, "X", "Y", 1.0)])
    assert b.sender.sent_last_24h == 0
    store2 = up.MemoryStore()
    up.seed(store2, account_states_frame(pl.LazyFrame(schema=HISTORY.drop("source_row").schema), t),
            pl.DataFrame({"account": ["X"], "timestamp": [t - dt.timedelta(hours=23, minutes=59)]}),
            NO_EDGES, t)  # fmt: skip
    (b2,) = store2.apply([up.Event(1, t, "X", "Y", 1.0)])
    assert b2.sender.sent_last_24h == 1


def test_new_accounts_come_back_cold_then_warm():
    store = _seeded_store()
    a, b = store.apply([up.Event(10**9, END, "NEW1", "NEW2", 5.0),
                        up.Event(10**9 + 1, END, "NEW1", "NEW3", 5.0)])  # fmt: skip
    assert a.sender.is_cold and a.receiver.is_cold
    assert not b.sender.is_cold and b.receiver.is_cold
    assert b.sender.n_sent == 1 and b.sender.distinct_out == 1


# --- the store keeps what the scorer reads -------------------------------------------
def test_after_a_batch_the_scorer_sees_the_updated_state():
    store = _seeded_store()
    events = _events(_stream_part())[:1000]
    store.apply(events)
    last = events[-1]
    st = store.account(last.from_account)
    assert st is not None and st.materialised_at == last.timestamp
