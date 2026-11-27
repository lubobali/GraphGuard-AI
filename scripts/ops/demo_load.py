"""S8b.2: load test of the demo API as the public will use it, from the host.

    uv run python scripts/ops/demo_load.py [--visitors 50] [--seconds 60]

Each simulated visitor has its own address (sent as X-Real-IP; the host reaches the container
through the trusted gateway, as nginx will) and its own marked visitor id, so its saved actions
are deleted afterwards by id, never by age. Prints status counts, latency and the container's
peak memory. TEST-NET addresses only (RFC 5737).
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8130"
MARK = "00000000-0000-4000-8000-0000000b2"  # + 3 hex digits: this test's visitor ids


def request(method: str, path: str, ip: str, body: dict | None = None) -> tuple[int, float]:
    data = json.dumps(body).encode() if body else None
    headers = {"X-Real-IP": ip, "Content-Type": "application/json"}
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = -1
    return code, time.perf_counter() - t0


def visitor(n: int, until: float, alerts: list[int], out: list, lock: threading.Lock) -> None:
    ip = f"203.0.113.{n % 250 + 1}" if n < 250 else f"198.51.100.{n % 250 + 1}"
    vid = f"{MARK}{n:03x}"
    rng = random.Random(n)
    pages = ["/", "/try/", "/api/queue?per_day=100", "/api/capacity?per_day=100",
             "/api/capacity/curve", f"/api/manager?visitor={vid}&scope=all",
             f"/api/decisions?visitor={vid}"]  # fmt: skip
    while time.time() < until:
        eid = rng.choice(alerts)
        if rng.random() < 0.1:
            body = {"visitor": vid, "role": "investigator", "action": "escalate",
                    "reason": "load test"}  # fmt: skip
            res = ("POST", *request("POST", f"/api/alerts/{eid}/actions", ip, body))
        elif rng.random() < 0.4:
            res = ("GET alert", *request("GET", f"/api/alerts/{eid}", ip))
        else:
            res = ("GET page", *request("GET", rng.choice(pages), ip))
        with lock:
            out.append(res)
        time.sleep(rng.uniform(0.1, 0.4))  # a fast human


def memory() -> float:
    s = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}",
                        "graphguard-demo-api"], capture_output=True, text=True).stdout  # fmt: skip
    v = s.split("/")[0].strip()
    return float(v[:-3]) if v.endswith("MiB") else float(v[:-3]) * 1024


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--visitors", type=int, default=50)
    ap.add_argument("--seconds", type=int, default=60)
    a = ap.parse_args()
    with urllib.request.urlopen(BASE + "/api/queue?per_day=100") as r:
        alerts = [g["event_id"] for g in json.load(r)["groups"]]
    out: list = []
    lock = threading.Lock()
    until = time.time() + a.seconds
    threads = [threading.Thread(target=visitor, args=(n, until, alerts, out, lock))
               for n in range(a.visitors)]  # fmt: skip
    mem = [memory()]
    for t in threads:
        t.start()
    while any(t.is_alive() for t in threads):
        time.sleep(3)
        mem.append(memory())
    by = collections.Counter((kind, code) for kind, code, _ in out)
    lat = sorted(s for _, code, s in out if code in (200, 201))
    q = statistics.quantiles(lat, n=100)
    print(json.dumps({
        "visitors": a.visitors, "seconds": a.seconds, "requests": len(out),
        "per_second": round(len(out) / a.seconds, 1),
        "status": {f"{k} {c}": n for (k, c), n in sorted(by.items())},
        "latency_ms": {"p50": round(q[49] * 1000), "p95": round(q[94] * 1000),
                       "p99": round(q[98] * 1000), "max": round(lat[-1] * 1000)},
        "memory_mib": {"before": mem[0], "peak": max(mem)},
    }, indent=1))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
