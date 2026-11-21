"""The S6.3 proof: replay the whole validation window through the updater, compare with
training row by row (==), and measure speed and memory.

    python -m graphguard.stream.proof                     # memory store
    python -m graphguard.stream.proof --redis URL         # a throwaway Redis (never the live one)

Train + validation rows only (`< val_end`); the test window is never read. The seed is the
`train_end` snapshot (states, recent sends, seen pairs), built by the same functions as gold.
"""

from __future__ import annotations

import argparse
import sys
import time

import polars as pl

from graphguard.serving.online_features import (
    account_states_frame,
    recent_sends_frame,
    to_model_row,
)
from graphguard.stream import updater as up

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


def _same(a, b) -> bool:
    nan = lambda v: v is None or v != v  # noqa: E731
    return (nan(a) and nan(b)) or a == b


def load():
    """Training's features for every validation row, the seed, and the events in order."""
    from graphguard.config import TRANSACTIONS_FILE
    from graphguard.data.loader import load_transactions
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.features.graph import build_account_history_features

    train_end, val_end = frozen_boundaries()
    lf = load_transactions(TRANSACTIONS_FILE)
    lf = (lf.lazy() if isinstance(lf, pl.DataFrame) else lf).with_row_index("source_row")
    lf = lf.filter(pl.col("timestamp") < val_end)  # never the test window
    training = (
        build_account_history_features(lf, as_of=val_end)
        .filter(pl.col("timestamp") >= train_end)
        .select("source_row", "timestamp", "from_account", "to_account", "amount_paid", *COLS)
        .sort("timestamp", "source_row")
        .collect()
    )
    past = lf.drop("source_row")
    seed = (
        account_states_frame(past, train_end),
        recent_sends_frame(past, train_end),
        up.edges_frame(past, train_end),
        train_end,
    )
    return training, seed


def replay(store, training: pl.DataFrame, batch: int = 500) -> dict:
    rows = training.to_dicts()
    bad, t0, statuses = [], time.perf_counter(), {}
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        events = [up.Event(r["source_row"], r["timestamp"], r["from_account"], r["to_account"],
                           r["amount_paid"]) for r in chunk]  # fmt: skip
        befores = store.apply(events)  # chunk is already in (timestamp, source_row) order
        for r, b in zip(chunk, befores, strict=True):
            statuses[b.status] = statuses.get(b.status, 0) + 1
            got = to_model_row(sender=b.sender, receiver=b.receiver, timestamp=r["timestamp"],
                               amount_paid=r["amount_paid"], amount_received=r["amount_paid"],
                               from_bank="1", to_bank="2")  # fmt: skip
            bad += [(r["source_row"], c, got[c], r[c]) for c in COLS if not _same(got[c], r[c])]
        store.ack([e.source_row for e in events])  # as the consumer will, once Postgres has it
    took = time.perf_counter() - t0
    return {"events": len(rows), "mismatches": len(bad), "first": bad[:5],
            "statuses": statuses, "seconds": round(took, 1),
            "events_per_s": round(len(rows) / took)}  # fmt: skip


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--redis", help="URL of a THROWAWAY Redis (namespace gg)")
    ap.add_argument("--batch", type=int, default=500)
    args = ap.parse_args(argv[1:])
    training, seed = load()
    if args.redis:
        import redis

        store = up.RedisStore(redis.Redis.from_url(args.redis))
    else:
        store = up.MemoryStore()
    t0 = time.perf_counter()
    counts = up.seed(store, *seed)
    print(f"seeded {counts} in {time.perf_counter() - t0:.1f}s", flush=True)
    result = replay(store, training, args.batch)
    print(result)
    return 0 if result["mismatches"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
