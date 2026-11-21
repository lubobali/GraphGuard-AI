"""End to end: replay -> Kafka -> consumer -> Postgres, then check every decision (S6.6+).

    python -m graphguard.stream.e2e --n 20000 [--faults chaos] [--consumer local|pod]

1. Reset the stream: empty the topics, the decision tables, and reload Redis from gold
   (`store-load`, which also resets the stream's seed).
2. Replay the first N validation transactions (optionally with seeded faults).
3. Let the consumer work: in this process (`local`), or wait for the k3s pod (`pod`).
4. Check, with the test window never read:
   - every transaction decided **exactly once** (rows = distinct event ids = N)
   - dead letters = exactly the malformed records the replayer planned; **no `late`**
   - every score **equals the offline evaluation score** of the same transaction
     (`features_for_split` -> `build_matrix` -> the model), the number `evaluate()` used
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

import polars as pl

from graphguard.config import REPO_ROOT
from graphguard.stream import db
from graphguard.stream import kafka_admin as ka
from graphguard.stream import replayer as rp

SECRETS = REPO_ROOT / ".secrets"


def reset() -> None:
    from confluent_kafka import TopicPartition
    from confluent_kafka.admin import AdminClient

    admin = AdminClient(ka.client_config("admin", secrets_dir=SECRETS))
    tps = [TopicPartition(t, 0, -1) for t in ka.TOPICS]
    for fut in admin.delete_records(tps).values():
        fut.result(timeout=30)
    db.reset()
    subprocess.run(["just", "store-load"], cwd=REPO_ROOT, check=True, capture_output=True)


def replay(n: int, faults: rp.Faults, run: str) -> rp.Plan:
    from confluent_kafka import Producer

    rows = rp.load_rows(limit=n)
    p = rp.plan(rows, faults)
    run_dir = rp.RUNS / run
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "checkpoint.json").unlink(missing_ok=True)
    producer = Producer({**ka.client_config("replayer", secrets_dir=SECRETS), **ka.PRODUCER})
    rp.send(p, producer, run_dir / "checkpoint.json", speed=None)
    return p


def offline_scores(event_ids: set[int]) -> dict[int, float]:
    """The evaluation's own score for each transaction: training features, same model."""
    from graphguard.config import TRANSACTIONS_FILE
    from graphguard.data.loader import load_transactions
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.models.pipeline import features_for_split
    from graphguard.models.tabular import build_matrix
    from graphguard.serving.model_bundle import ModelBundle

    bundle = ModelBundle.load(REPO_ROOT / "models" / "production")
    lf = load_transactions(TRANSACTIONS_FILE)
    lf = (lf.lazy() if isinstance(lf, pl.DataFrame) else lf).with_row_index("source_row")
    frame = features_for_split(lf, "validation", frozen_boundaries())
    frame = frame.filter(pl.col("source_row").is_in(list(event_ids)))
    X, _ = build_matrix(frame, bundle.category_maps)
    scores = bundle.model.predict_proba(X.select(bundle.feature_columns).to_numpy())[:, 1]
    return dict(zip(frame["source_row"].to_list(), (float(s) for s in scores), strict=True))


def check(p: rp.Plan) -> dict:
    expected = {p.row(s.index)["source_row"] for s in p.sends if s.kind == "event"}
    malformed = sum(1 for s in p.sends if s.kind == "malformed")
    with db.connect(secrets_dir=SECRETS) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*), count(DISTINCT event_id) FROM decisions")
        rows, distinct = cur.fetchone()
        cur.execute("SELECT event_id, score FROM decisions")
        got = dict(cur.fetchall())
        cur.execute("SELECT split_part(reason, ':', 1), count(*) FROM dead_letters GROUP BY 1")
        dead = dict(cur.fetchall())
        cur.execute("SELECT count(*) FROM outbox WHERE published_at IS NULL")
        unpublished = cur.fetchone()[0]
    want = offline_scores(expected)
    wrong = [(i, got.get(i), want[i]) for i in expected if got.get(i) != want[i]]
    return {
        "sent": len(p.sends), "events": len(expected), "decisions": rows,
        "distinct": distinct, "missing": len(expected - set(got)),
        "extra": len(set(got) - expected), "dead_letters": dead,
        "malformed_planned": malformed, "score_mismatches": len(wrong),
        "first_mismatches": wrong[:3], "outbox_unpublished": unpublished,
        "ok": rows == distinct == len(expected) and not wrong and unpublished == 0
        and dead.get("malformed", 0) == malformed and "late" not in dead,
    }  # fmt: skip


def wait_for_pod(n: int, timeout: int = 1800) -> None:
    end = time.time() + timeout
    last = -1
    while time.time() < end:
        with db.connect(secrets_dir=SECRETS) as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM decisions")
            count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM outbox WHERE published_at IS NULL")
            pending = cur.fetchone()[0]
        if count >= n and pending == 0:
            return
        if count == last:
            time.sleep(5)
        last = count
        time.sleep(2)
    raise TimeoutError(f"the pod decided {last} of {n} in {timeout}s")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20_000)
    ap.add_argument("--faults", choices=("none", "chaos"), default="none")
    ap.add_argument("--consumer", choices=("local", "pod"), default="local")
    args = ap.parse_args(argv[1:])
    faults = rp.CHAOS if args.faults == "chaos" else rp.Faults()
    t0 = time.time()
    reset()
    print(f"reset ({time.time() - t0:.0f}s)", flush=True)
    p = replay(args.n, faults, run=f"e2e-{args.consumer}-{args.faults}")
    print(f"replayed {len(p.sends):,} records ({time.time() - t0:.0f}s)", flush=True)
    if args.consumer == "local":
        from graphguard.stream import consumer

        counts = consumer.run(max_idle_s=10)
        print(f"consumer: {counts} ({time.time() - t0:.0f}s)", flush=True)
    else:
        wait_for_pod(args.n)
    report = check(p)
    print(json.dumps(report, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
