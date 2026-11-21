"""Measure the scorer's latency on k3s, open loop, from inside the cluster (S5.4).

    python -m graphguard.serving.perf_k8s run [--rates 10 50 200] [--reps 3]

For each rate: a short-lived load-generator pod (restricted, capped, egress to the
scorer only) runs `loadgen.py` against the scorer's Service by name -- the path Phase 6's
stream consumer will use -- and the same rate runs from the host for comparison. Between
rates the box is checked; a bad LuBot health check or a high load stops the run.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

from graphguard.config import REPO_ROOT

NS = "graphguard"
IMAGE = "graphguard/serving:0.1.12"  # the scorer's image: Python, nothing extra pulled
SERVICE_URL = "http://graphguard-scorer-serve-svc:8000/"
HOST_URL = "http://10.43.3.216:8000/"
LABEL = "graphguard-loadgen"
LUBOT_HEALTH = "https://lubot.ai/health"
MAX_LOAD1 = 10.0  # 8 cores: above this the box is busy enough to stop


def job_manifest(name: str, rates: list[float], reps: int, warmup: float, duration: float) -> dict:
    """The load-generator Job (pure, tested): Pod Security restricted, capped, no token."""
    args = ["python", "/lg/loadgen.py", "--url", SERVICE_URL, "--data", "/lg/requests.json",
            "--rate", *[str(r) for r in rates], "--reps", str(reps),
            "--warmup", str(warmup), "--duration", str(duration)]  # fmt: skip
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "namespace": NS, "labels": {"app": LABEL}},
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 600,
            "activeDeadlineSeconds": int(len(rates) * reps * (warmup + duration + 10) + 120),
            "template": {
                "metadata": {"labels": {"app": LABEL}},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [{
                        "name": "loadgen",
                        "image": IMAGE,
                        "imagePullPolicy": "IfNotPresent",
                        "command": args,
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "resources": {
                            "requests": {"cpu": "250m", "memory": "128Mi"},
                            "limits": {"cpu": "1", "memory": "256Mi"},
                        },
                        "volumeMounts": [{"name": "lg", "mountPath": "/lg", "readOnly": True}],
                    }],
                    "volumes": [{"name": "lg", "configMap": {"name": LABEL}}],
                },
            },
        },
    }  # fmt: skip


def _kubectl(*args: str, stdin: str | None = None) -> str:
    return subprocess.run(["k3s", "kubectl", *args], input=stdin, text=True,
                          check=True, capture_output=True).stdout  # fmt: skip


def requests_file(path: str, n: int = 2000) -> None:
    """2,000 real validation transactions, in time order, as scoring requests."""
    import polars as pl

    from graphguard.config import TRANSACTIONS_FILE
    from graphguard.data.loader import load_transactions
    from graphguard.evaluation.dataset import frozen_boundaries

    train_end, val_end = frozen_boundaries()
    rows = (load_transactions(TRANSACTIONS_FILE)
            .filter((pl.col("timestamp") >= train_end) & (pl.col("timestamp") < val_end))
            .head(n).collect())  # fmt: skip
    keys = ("from_account", "to_account", "amount_paid", "amount_received", "from_bank",
            "to_bank", "payment_currency")  # fmt: skip
    out = [{**{k: r[k] for k in keys}, "timestamp": r["timestamp"].isoformat()}
           for r in rows.iter_rows(named=True)]  # fmt: skip
    with open(path, "w") as f:
        json.dump(out, f)


def box_ok() -> str | None:
    """None if the box is fine to load, else why not."""
    load1 = os.getloadavg()[0]
    if load1 > MAX_LOAD1:
        return f"load average {load1:.1f} > {MAX_LOAD1}"
    try:
        with urllib.request.urlopen(LUBOT_HEALTH, timeout=10) as r:
            if r.status != 200:
                return f"lubot.ai health {r.status}"
    except Exception as e:  # noqa: BLE001
        return f"lubot.ai health failed: {type(e).__name__}"
    return None


def _scorer_cgroup() -> str:
    pod = json.loads(_kubectl("get", "pods", "-n", NS, "-l", "ray.io/node-type=head", "-o", "json"))
    uid = pod["items"][0]["metadata"]["uid"].replace("-", "_")
    for root, dirs, _ in os.walk("/sys/fs/cgroup/kubepods.slice"):
        for d in dirs:
            if uid in d:
                return os.path.join(root, d)
    raise LookupError("scorer pod cgroup not found")


def _cpu_usec(cg: str) -> int:
    for line in open(f"{cg}/cpu.stat"):
        if line.startswith("usage_usec"):
            return int(line.split()[1])
    return 0


def in_cluster(rate: float, reps: int, warmup: float, duration: float) -> list[dict]:
    name = f"{LABEL}-{int(rate)}-{int(time.time())}"
    cg = _scorer_cgroup()
    cpu0, t0 = _cpu_usec(cg), time.time()
    _kubectl(
        "apply", "-f", "-", stdin=json.dumps(job_manifest(name, [rate], reps, warmup, duration))
    )
    try:
        _kubectl("wait", "-n", NS, "--for=condition=complete", f"job/{name}",
                 f"--timeout={int(reps * (warmup + duration + 10) + 120)}s")  # fmt: skip
        lines = _kubectl("logs", "-n", NS, f"job/{name}").splitlines()
    finally:
        _kubectl("delete", "job", "-n", NS, name, "--wait=false")
    cores = (_cpu_usec(cg) - cpu0) / 1e6 / (time.time() - t0)
    mem = int(open(f"{cg}/memory.current").read()) >> 20
    results = [json.loads(x) for x in lines if x.startswith("{")]
    for r in results:
        r.update(where="in-cluster", scorer_cpu_cores=round(cores, 2), scorer_mem_mib=mem)
    return results


def from_host(rate: float, reps: int, warmup: float, duration: float, data: str) -> list[dict]:
    from graphguard.serving import loadgen

    with open(data) as f:
        bodies = [json.dumps(r).encode() for r in json.load(f)]
    return [{**loadgen.run(HOST_URL, bodies, rate, warmup, duration), "rep": i + 1, "where": "host"}
            for i in range(reps)]  # fmt: skip


def run(rates: list[float], reps: int, warmup: float, duration: float, out: str,
        step_until_p99_ms: float | None = None) -> list[dict]:  # fmt: skip
    with tempfile.TemporaryDirectory() as tmp:
        data = os.path.join(tmp, "requests.json")
        requests_file(data)
        # `create`, not `apply`: apply keeps a copy of the object in an annotation capped at
        # 256 KB, and 2,000 transactions are bigger than that.
        _kubectl("delete", "configmap", LABEL, "-n", NS, "--ignore-not-found")
        _kubectl("create", "configmap", LABEL, "-n", NS,
                 f"--from-file=loadgen.py={REPO_ROOT / 'src/graphguard/serving/loadgen.py'}",
                 f"--from-file=requests.json={data}")  # fmt: skip
        _kubectl("apply", "-f", str(REPO_ROOT / "k8s" / "loadgen-networkpolicy.yaml"))
        results: list[dict] = []
        # The headline rates: 3 repetitions in the cluster + one host run to compare.
        for rate in rates:
            if why := box_ok():
                print(f"STOP before {rate}/s: {why}", flush=True)
                break
            batch = in_cluster(rate, reps, warmup, duration) + from_host(
                rate, 1, warmup, duration, data
            )
            for r in batch:
                results.append(r)
                print(json.dumps(r), flush=True)
        # The capacity search: double the rate until p99 crosses the budget or errors
        # appear -- one shorter run each (it finds a limit, it is not the headline).
        rate = rates[-1]
        while step_until_p99_ms and rate < 3200:
            last = [r for r in results if r["rate"] == rate and r["where"] == "in-cluster"]
            if (
                not last
                or max(r["p99_ms"] for r in last) >= step_until_p99_ms
                or any(r["errors"] + r["timeouts"] for r in last)
            ):
                break
            rate *= 2
            if why := box_ok():
                print(f"STOP before {rate}/s: {why}", flush=True)
                break
            for r in in_cluster(rate, 1, 10, 30):
                r["capacity_search"] = True
                results.append(r)
                print(json.dumps(r), flush=True)
        with open(out, "w") as f:
            json.dump(results, f, indent=1)
        _kubectl("delete", "configmap", LABEL, "-n", NS)
    return results


def main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--rates", type=float, nargs="+", default=[10, 50, 200])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--warmup", type=float, default=15)
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--step-until-p99-ms", type=float, default=None)
    ap.add_argument("--out", default=str(REPO_ROOT / "docs" / "perf" / "s5.4-latency.json"))
    a = ap.parse_args(argv[1:])
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    run(a.rates, a.reps, a.warmup, a.duration, a.out, a.step_until_p99_ms)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
