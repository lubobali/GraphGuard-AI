"""Measure end-to-end scoring latency against the real store and real model.

The Phase 5 budget is **p99 under 50ms**, and the plan is explicit that it is
measured rather than assumed. Measured here means the whole path a request
takes: Redis round trip, feature assembly, and model inference. Timing only the
model would be measuring the easy part.

Reported at p50, p95 and p99 because a mean hides exactly the tail the budget
is about.
"""

from __future__ import annotations

import argparse
import statistics
import time

import polars as pl

from graphguard.config import REPO_ROOT, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.dataset import frozen_boundaries
from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.service import ScoringRequest, ScoringService
from graphguard.serving.store import RedisFeatureStore

BUNDLE_DIR = REPO_ROOT / "models" / "production"
BUDGET_MS = 50.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=2000)
    ap.add_argument("--warmup", type=int, default=100)
    args = ap.parse_args()

    train_end, val_end = frozen_boundaries()

    # Real validation transactions, so the account mix is realistic: mostly
    # small accounts, a few hubs, and some the store has never seen.
    sample = (
        load_transactions(TRANSACTIONS_FILE)
        .filter((pl.col("timestamp") >= train_end) & (pl.col("timestamp") < val_end))
        .head(args.requests + args.warmup)
        .collect()
    )

    service = ScoringService(bundle=ModelBundle.load(BUNDLE_DIR), store=RedisFeatureStore())

    requests = [
        ScoringRequest(
            from_account=r["from_account"],
            to_account=r["to_account"],
            amount_paid=r["amount_paid"],
            amount_received=r["amount_received"],
            from_bank=r["from_bank"],
            to_bank=r["to_bank"],
            payment_currency=r["payment_currency"],
            timestamp=r["timestamp"],
        )
        for r in sample.iter_rows(named=True)
    ]

    for request in requests[: args.warmup]:
        service.score(request)

    timings_ms: list[float] = []
    cold = 0
    for request in requests[args.warmup :]:
        started = time.perf_counter()
        response = service.score(request)
        timings_ms.append((time.perf_counter() - started) * 1000)
        cold += int(response.sender_cold or response.receiver_cold)

    timings_ms.sort()
    p50 = statistics.median(timings_ms)
    p95 = timings_ms[int(len(timings_ms) * 0.95)]
    p99 = timings_ms[int(len(timings_ms) * 0.99)]

    print(f"requests      {len(timings_ms):,}  ({cold:,} involved a cold account)")
    print(f"p50           {p50:7.2f} ms")
    print(f"p95           {p95:7.2f} ms")
    print(f"p99           {p99:7.2f} ms   budget {BUDGET_MS:.0f} ms")
    print(f"max           {timings_ms[-1]:7.2f} ms")
    print()
    if p99 <= BUDGET_MS:
        print(f"PASS: p99 {p99:.2f} ms is within the {BUDGET_MS:.0f} ms budget")
        return 0
    print(f"FAIL: p99 {p99:.2f} ms exceeds the {BUDGET_MS:.0f} ms budget")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
