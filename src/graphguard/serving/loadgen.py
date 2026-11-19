"""An open-loop load generator for the scorer (S5.4). Standard library only: the same
file runs on the host and inside a pod.

    python loadgen.py --url http://graphguard-scorer-serve-svc:8000/ --data requests.json \\
        --rate 200 --warmup 15 --duration 60

**Open loop.** Request *i* is due at `t0 + i / rate`, whatever the server is doing.
Latency counts from that *intended* time, not from when a thread got round to sending
it. A closed-loop client (send, wait, send) stops sending while the server stalls, so the
stall never reaches its percentiles -- "coordinated omission". Here a stall shows up in
every request that was due during it, as it would for a real stream.

Prints one JSON line: rate, counts, p50/p95/p99/p99.9/max over the measured window
(warm-up excluded), the worst send lag, and the cold-account rate.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import queue
import sys
import threading
import time
import urllib.parse


def percentile(sorted_ms: list[float], q: float) -> float:
    """Nearest-rank percentile of an already sorted list (pure, tested)."""
    if not sorted_ms:
        return float("nan")
    k = max(0, min(len(sorted_ms) - 1, math.ceil(q * len(sorted_ms)) - 1))
    return sorted_ms[k]


def summarise(records: list[tuple], rate: float, warmup: float, t0: float) -> dict:
    """records: (intended, started, ended, ok, timeout, cold_sides). Pure, tested."""
    measured = [r for r in records if r[0] >= t0 + warmup]
    lat = sorted((r[2] - r[0]) * 1000 for r in measured if r[3])
    span = (max(r[0] for r in measured) - min(r[0] for r in measured)) if measured else 0
    ok = sum(1 for r in measured if r[3])
    return {
        "rate": rate,
        "sent": len(measured),
        "ok": ok,
        "errors": sum(1 for r in measured if not r[3] and not r[4]),
        "timeouts": sum(1 for r in measured if r[4]),
        "achieved_rate": round(len(measured) / span, 1) if span else 0.0,
        "p50_ms": round(percentile(lat, 0.50), 2),
        "p95_ms": round(percentile(lat, 0.95), 2),
        "p99_ms": round(percentile(lat, 0.99), 2),
        "p999_ms": round(percentile(lat, 0.999), 2),
        "max_ms": round(lat[-1], 2) if lat else float("nan"),
        "worst_send_lag_ms": round(max(((r[1] - r[0]) * 1000 for r in measured), default=0), 2),
        "cold_side_rate": round(sum(r[5] for r in measured if r[3]) / (2 * ok), 4) if ok else 0.0,
    }


def _send(conn, connect, path: str, body: bytes):
    """One request on a kept-alive connection -> (ok, timed out, cold sides, connection).
    A failed connection is replaced, so one error never poisons the next request."""
    try:
        conn.request("POST", path, body, {"Content-Type": "application/json"})
        resp = conn.getresponse()
        payload = resp.read()
        if resp.status != 200:
            return False, False, 0, conn
        r = json.loads(payload)
        return (
            True,
            False,
            int(bool(r.get("sender_cold"))) + int(bool(r.get("receiver_cold"))),
            conn,
        )
    except TimeoutError:
        conn.close()
        return False, True, 0, connect()
    except Exception:  # noqa: BLE001 -- counted as an error
        conn.close()
        return False, False, 0, connect()


def run(url: str, bodies: list[bytes], rate: float, warmup: float, duration: float,
        threads: int = 32, timeout: float = 2.0) -> dict:  # fmt: skip
    u = urllib.parse.urlsplit(url)
    path = u.path or "/"
    work: queue.Queue = queue.Queue()
    records: list[tuple] = []
    lock = threading.Lock()

    def connect() -> http.client.HTTPConnection:
        return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)

    def worker() -> None:
        conn = connect()
        while (item := work.get()) is not None:
            intended, body = item
            started = time.perf_counter()
            ok, to, cold, conn = _send(conn, connect, path, body)
            ended = time.perf_counter()
            with lock:
                records.append((intended, started, ended, ok, to, cold))

    pool = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
    for t in pool:
        t.start()
    t0 = time.perf_counter() + 0.2
    total = int((warmup + duration) * rate)
    for i in range(total):
        intended = t0 + i / rate
        if (delay := intended - time.perf_counter()) > 0:
            time.sleep(delay)
        work.put((intended, bodies[i % len(bodies)]))
    for _ in pool:
        work.put(None)
    for t in pool:
        t.join(timeout + 5)
    return summarise(records, rate, warmup, t0)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--data", required=True, help="JSON list of scoring requests")
    ap.add_argument("--rate", type=float, nargs="+", required=True)
    ap.add_argument("--warmup", type=float, default=15)
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--threads", type=int, default=32)
    a = ap.parse_args(argv[1:])
    with open(a.data) as f:
        bodies = [json.dumps(r).encode() for r in json.load(f)]
    for rate in a.rate:
        for rep in range(a.reps):
            out = run(a.url, bodies, rate, a.warmup, a.duration, a.threads)
            print(json.dumps({**out, "rep": rep + 1}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
