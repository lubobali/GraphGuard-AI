"""The overnight run (S6.11, the Phase 6 gate): the whole validation window, unattended.

    python -m graphguard.stream.soak start [--speed 6]   # reset, then replay + monitor, detached
    python -m graphguard.stream.soak report              # the morning check

`start` resets the stream (topics, decision tables, Redis seed), then launches two transient
systemd units that outlive any shell: the replay job (the whole validation window, ~1.0M
transactions, at `speed` x real time -- 6x is ~8.4 h) and a monitor that writes a line every
5 minutes to `stream-runs/soak/metrics.jsonl`: Kafka's end, the consumer's position (lag),
decisions so far, and the memory of every stream part.

`report` checks what Phase 6 promised: every transaction decided exactly once, every score
equal to the offline evaluation's, rules equal, no dead letters, the outbox drained, lag back
to zero, memory flat under its caps, decision latency (arrival in Kafka -> decision stored).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time

from graphguard.config import REPO_ROOT

RUN = "soak"
RUN_DIR = REPO_ROOT / "stream-runs" / RUN
METRICS = RUN_DIR / "metrics.jsonl"
PY = str(REPO_ROOT / ".tools" / "bin" / "uv")


def _cgroup_peak(deploy: str) -> int | None:
    out = subprocess.run(
        [
            "k3s",
            "kubectl",
            "exec",
            "-n",
            "graphguard",
            f"deploy/{deploy}",
            "--",
            "cat",
            "/sys/fs/cgroup/memory.current",
        ],
        capture_output=True,
        text=True,
    )
    return int(out.stdout) // 1048576 if out.returncode == 0 and out.stdout.strip() else None


def _docker_mem(name: str) -> str | None:
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip().split(" / ")[0] if out.returncode == 0 else None


def sample() -> dict:
    from graphguard.ops.alert import probe_stream
    from graphguard.stream import db

    hwm, committed = probe_stream()
    with db.connect(secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*), max(event_time) FROM decisions")
        decided, last = cur.fetchone()
    return {
        "at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "hwm": hwm,
        "committed": committed,
        "lag": (hwm - committed) if hwm and committed else None,
        "decided": decided,
        "event_time": last.isoformat() if last else None,
        "mem_consumer_mib": _cgroup_peak("graphguard-consumer"),
        "mem_shadow_mib": _cgroup_peak("graphguard-shadow"),
        "mem_redis": _docker_mem("graphguard-redis"),
        "mem_kafka": _docker_mem("graphguard-kafka"),
        "mem_postgres": _docker_mem("graphguard-mlflow-db"),
    }


def monitor(every_s: int = 300, hours: float = 14) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    end = time.time() + hours * 3600
    while time.time() < end:
        try:
            line = sample()
        except Exception as e:  # noqa: BLE001 -- a failed sample is itself a data point
            line = {"at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "error": str(e)}
        with METRICS.open("a") as f:
            f.write(json.dumps(line) + "\n")
        time.sleep(every_s)


def start(speed: float) -> None:
    import grp
    import os

    from graphguard.stream import e2e

    e2e.reset()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    # The replay job runs as gg-reader (S5b.5): the run folder must be the jobs group's.
    os.chown(RUN_DIR, -1, grp.getgrnam("gg-jobs").gr_gid)
    os.chmod(RUN_DIR, 0o2770)
    METRICS.unlink(missing_ok=True)
    (RUN_DIR / "checkpoint.json").unlink(missing_ok=True)
    (RUN_DIR / "started.json").write_text(
        json.dumps({"at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "speed": speed})
        + "\n"
    )
    base = [
        "systemd-run",
        "--collect",
        "--quiet",
        f"--working-directory={REPO_ROOT}",
        "-p",
        "MemoryMax=1G",
    ]
    subprocess.run(
        [
            *base,
            "--unit=graphguard-soak-replay",
            "just",
            "replay",
            "--run",
            RUN,
            "--speed",
            str(speed),
        ],
        check=True,
    )
    subprocess.run(
        [
            *base,
            "--unit=graphguard-soak-monitor",
            PY,
            "run",
            "--no-sync",
            "python",
            "-m",
            "graphguard.stream.soak",
            "monitor",
        ],
        check=True,
    )
    print(
        f"soak started at {speed}x: units graphguard-soak-replay + graphguard-soak-monitor; "
        f"metrics in {METRICS.relative_to(REPO_ROOT)}"
    )


def _percentiles(values: list[float]) -> dict:
    import numpy as np

    if not values:
        return {}
    a = np.array([float(v) for v in values])
    return {p: round(float(np.percentile(a, int(p[1:]))), 3) for p in ("p50", "p95", "p99")} | {
        "max": round(float(a.max()), 3)
    }


def report() -> dict:
    from graphguard.stream import db, e2e
    from graphguard.stream import replayer as rp

    rows = rp.load_rows()
    p = rp.plan(rows, rp.Faults())
    result = e2e.check(p)
    with db.connect(secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT extract(epoch FROM decided_at::timestamp - arrived_at) FROM decisions "
            "WHERE arrived_at IS NOT NULL"
        )
        latency = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT min(decided_at), max(decided_at) FROM decisions")
        first, last = cur.fetchone()
    metrics = [json.loads(x) for x in METRICS.read_text().splitlines()] if METRICS.exists() else []
    good = [m for m in metrics if "error" not in m]
    result.update(
        {
            "decision_latency_s": _percentiles(latency),
            "wall_clock": {"first": str(first), "last": str(last)},
            "samples": len(metrics),
            "sample_errors": len(metrics) - len(good),
            "max_lag": max((m["lag"] or 0) for m in good) if good else None,
            "final_lag": good[-1]["lag"] if good else None,
            "peak_mem_consumer_mib": max((m["mem_consumer_mib"] or 0) for m in good)
            if good
            else None,
            "peak_mem_shadow_mib": max((m["mem_shadow_mib"] or 0) for m in good) if good else None,
            "last_sample": good[-1] if good else None,
        }
    )
    return result


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("start", "monitor", "report", "sample"))
    ap.add_argument("--speed", type=float, default=6.0)
    args = ap.parse_args(argv[1:])
    if args.cmd == "start":
        start(args.speed)
    elif args.cmd == "monitor":
        monitor()
    elif args.cmd == "sample":
        print(json.dumps(sample()))
    else:
        result = report()
        (REPO_ROOT / "docs" / "analysis" / "s6.11-soak.json").write_text(
            json.dumps(result, indent=2, default=str) + "\n"
        )
        print(json.dumps(result, indent=2, default=str))
        return 0 if result["ok"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
