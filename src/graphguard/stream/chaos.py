"""Chaos (S6.7): break the stream on purpose and prove the decisions do not change.

    python -m graphguard.stream.chaos [--n 20000] [--only NAME]

Every scenario resets the stream, replays the first N validation transactions into the k3s
consumer while something goes wrong, then checks with `e2e.check` (each transaction decided
exactly once, only the planned dead letters, every score == the offline evaluation's) and
compares Redis's final account state with a batch recomputation. Because every run must
equal the same offline scores, passing them all IS decision parity across speeds and faults.

Scenarios: clean at max speed; clean at 600x; seeded faults; the consumer pod killed twice
(kill -9 semantics); a crash between Redis and Postgres (the consumer's chaos hook); the
broker restarted mid-replay.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time

import polars as pl

from graphguard.stream import e2e
from graphguard.stream import replayer as rp

NS, DEPLOY = "graphguard", "deploy/graphguard-consumer"


def _kubectl(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ["k3s", "kubectl", *args], check=check, capture_output=True, text=True
    ).stdout


def kill_pod() -> None:
    _kubectl(
        "delete",
        "pod",
        "-n",
        NS,
        "-l",
        "app=graphguard-consumer",
        "--grace-period=0",
        "--force",
        "--wait=false",
    )


def restart_broker() -> None:
    subprocess.run(["docker", "restart", "graphguard-kafka"], check=True, capture_output=True)


def set_crash_hook(event_id: int | None) -> None:
    value = (
        f"GRAPHGUARD_CHAOS_CRASH_AFTER_REDIS={event_id}"
        if event_id
        else ("GRAPHGUARD_CHAOS_CRASH_AFTER_REDIS-")
    )
    _kubectl("set", "env", "-n", NS, DEPLOY, value)
    _kubectl("rollout", "status", "-n", NS, DEPLOY, "--timeout=180s")


def _replay_async(n: int, faults: rp.Faults, speed: float | None, run: str):
    """Replay in a thread (so faults can be injected meanwhile); returns (thread, holder)."""
    from confluent_kafka import Producer

    from graphguard.stream import kafka_admin as ka

    rows = rp.load_rows(limit=n)
    p = rp.plan(rows, faults)
    run_dir = rp.RUNS / run
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "checkpoint.json").unlink(missing_ok=True)
    holder: dict = {"plan": p}

    def go():
        producer = Producer(
            {
                **ka.client_config("replayer", secrets_dir=e2e.SECRETS),
                **ka.PRODUCER,
                "message.timeout.ms": 600_000,
            }
        )
        try:
            rp.send(p, producer, run_dir / "checkpoint.json", speed=speed)
        except Exception as ex:  # noqa: BLE001 -- reported by the scenario
            holder["error"] = ex

    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t, holder


def redis_matches_batch(p: rp.Plan, sample: int = 300) -> dict:
    """The live store's final state for a sample of accounts == a batch recomputation."""
    import datetime as dt

    from graphguard.config import TRANSACTIONS_FILE
    from graphguard.data.loader import load_transactions
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.serving.online_features import account_states_frame
    from graphguard.serving.store import RedisFeatureStore, redis_url

    rows = p.rows
    # State after every replayed event = batch state just after the last one, from the
    # training history (< train_end) plus exactly the replayed rows.
    train_end, _ = frozen_boundaries()
    lf = load_transactions(TRANSACTIONS_FILE)
    lf = (lf.lazy() if isinstance(lf, pl.DataFrame) else lf).with_row_index("source_row")
    ids = rows["source_row"].to_list()
    history = lf.filter((pl.col("timestamp") < train_end) | pl.col("source_row").is_in(ids))
    after = rows["timestamp"].max() + dt.timedelta(minutes=1)
    batch = account_states_frame(history.drop("source_row"), after)
    touched = sorted(set(rows["from_account"].to_list()) | set(rows["to_account"].to_list()))
    pick = touched[:: max(1, len(touched) // sample)][:sample]
    store = RedisFeatureStore(url=redis_url(0, "loader"))
    want = {
        r["account"]: r for r in batch.filter(pl.col("account").is_in(pick)).iter_rows(named=True)
    }
    bad = []
    for a in pick:
        got = store.get(a)
        w = want[a]
        for f in (
            "n_sent",
            "n_received",
            "amount_sent",
            "amount_received",
            "distinct_out",
            "distinct_in",
            "last_sent",
        ):
            if getattr(got, f) != w[f]:
                bad.append((a, f, getattr(got, f), w[f]))
    return {"accounts_checked": len(pick), "state_mismatches": len(bad), "first": bad[:3]}


def scenario(
    name: str,
    n: int,
    faults: rp.Faults,
    speed: float | None,
    during=None,
    crash_at: int | None = None,
) -> dict:
    t0 = time.time()
    e2e.reset()
    if crash_at:
        set_crash_hook(crash_at)
    t, holder = _replay_async(n, faults, speed, run=f"chaos-{name}")
    if during:
        during()
    t.join()
    if "error" in holder:
        raise RuntimeError(f"{name}: replayer failed: {holder['error']}")
    p = holder["plan"]
    e2e.wait_for_pod(n, timeout=1200)
    report = e2e.check(p)
    report.update(redis_matches_batch(p))
    if crash_at:
        set_crash_hook(None)
    restarts = _kubectl(
        "get",
        "pods",
        "-n",
        NS,
        "-l",
        "app=graphguard-consumer",
        "-o",
        "jsonpath={.items[*].status.containerStatuses[0].restartCount}",
    )
    report.update(
        {
            "scenario": name,
            "seconds": round(time.time() - t0),
            "pod_restarts_now": restarts,
            "ok": report["ok"] and report["state_mismatches"] == 0,
        }
    )
    return report


def _after(seconds: float, action):
    def run():
        time.sleep(seconds)
        action()

    return run


def _twice(a, b, action):
    def run():
        time.sleep(a)
        action()
        time.sleep(b)
        action()

    return run


SCENARIOS = {
    "clean-max": lambda n: scenario("clean-max", n, rp.Faults(), None),
    "clean-600x": lambda n: scenario("clean-600x", n, rp.Faults(), 600.0),
    "faults": lambda n: scenario("faults", n, rp.CHAOS, None),
    "pod-killed-twice": lambda n: scenario(
        "pod-killed-twice", n, rp.CHAOS, 600.0, during=_twice(2, 3, kill_pod)
    ),
    "crash-between-redis-and-postgres": lambda n: scenario(
        "crash-between-redis-and-postgres", n, rp.Faults(), 600.0, crash_at=None
    ),
    "broker-restart": lambda n: scenario(
        "broker-restart", n, rp.CHAOS, 600.0, during=_after(2, restart_broker)
    ),
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20_000)
    ap.add_argument("--only")
    args = ap.parse_args(argv[1:])
    names = [args.only] if args.only else list(SCENARIOS)
    results = []
    for name in names:
        if name == "crash-between-redis-and-postgres":
            rows = rp.load_rows(limit=args.n)
            crash = int(rows["source_row"][args.n // 3])  # a third of the way in
            r = scenario(name, args.n, rp.Faults(), 600.0, crash_at=crash)
            r["crash_event"] = crash
        else:
            r = SCENARIOS[name](args.n)
        print(json.dumps(r, default=str), flush=True)
        results.append(r)
    ok = all(r["ok"] for r in results)
    print(f"chaos: {sum(r['ok'] for r in results)}/{len(results)} scenarios exact")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
