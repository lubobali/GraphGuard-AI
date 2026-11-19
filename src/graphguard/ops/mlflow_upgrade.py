"""Upgrade MLflow's server safely (S5b.7): rehearse on a restored copy, then switch.

    python -m graphguard.ops.mlflow_upgrade rehearse <new image> <old image>
    python -m graphguard.ops.mlflow_upgrade snapshot <base url>       (stdlib only)

**Rehearse**: the latest restic snapshot → a throwaway Postgres on an internal network
→ `mlflow db upgrade` with the new image → a throwaway server on it → its answers must
equal the live server's, run for run (metrics, params, tags, status) — and an artifact
downloads. Then the way back: the pre-migration dump into a fresh database under the
OLD image, same answers. Nothing live is touched.

`snapshot` and `compare` use only the standard library and the REST API, so the same
file runs inside a throwaway container against a server that has no host port.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request


# --- stdlib only: a version-independent picture of the record ---------------------------
def _post(base: str, path: str, body: dict, auth: tuple[str, str] | None) -> dict:
    req = urllib.request.Request(
        f"{base}/api/2.0/mlflow/{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _all(base: str, path: str, body: dict, key: str, auth) -> list[dict]:
    out, token = [], None
    while True:
        page = _post(base, path, {**body, **({"page_token": token} if token else {})}, auth)
        out += page.get(key, [])
        token = page.get("next_page_token")
        if not token:
            return out


def snapshot(base: str, auth: tuple[str, str] | None = None) -> dict:
    """Every experiment and run as plain data: what must survive an upgrade."""
    exps = _all(base, "experiments/search", {"max_results": 1000, "view_type": "ALL"},
                "experiments", auth)  # fmt: skip
    runs = _all(
        base,
        "runs/search",
        {"experiment_ids": [e["experiment_id"] for e in exps], "max_results": 1000,
         "run_view_type": "ALL"},
        "runs",
        auth,
    )  # fmt: skip
    return {
        "experiments": sorted((e["experiment_id"], e["name"]) for e in exps),
        "runs": {
            r["info"]["run_id"]: {
                "experiment": r["info"]["experiment_id"],
                "status": r["info"]["status"],
                "metrics": {m["key"]: m["value"] for m in r["data"].get("metrics", [])},
                "params": {p["key"]: p["value"] for p in r["data"].get("params", [])},
                "tags": sorted(
                    t["key"]
                    for t in r["data"].get("tags", [])
                    if not t["key"].startswith("mlflow.")
                ),  # fmt: skip
            }
            for r in runs
        },
    }


def compare(before: dict, after: dict) -> list[str]:
    """Differences that would mean the record changed (pure, tested)."""
    out = []
    if [list(e) for e in before["experiments"]] != [list(e) for e in after["experiments"]]:
        out.append("experiments differ")
    missing = set(before["runs"]) - set(after["runs"])
    extra = set(after["runs"]) - set(before["runs"])
    out += [f"run missing: {r}" for r in sorted(missing)]
    out += [f"run added: {r}" for r in sorted(extra)]
    for rid in sorted(set(before["runs"]) & set(after["runs"])):
        b, a = before["runs"][rid], after["runs"][rid]
        for field in ("experiment", "status", "metrics", "params", "tags"):
            if b[field] != a[field]:
                out.append(f"run {rid}: {field} differs")
    return out


# --- the rehearsal (host side) ----------------------------------------------------------
NET = "gg-mlflow-rehearsal"
PG = "gg-mlflow-rehearsal-pg"
SERVER = "gg-mlflow-rehearsal-server"
# A throwaway database on an internal network, deleted after the rehearsal.
PW = "rehearsal"  # betterleaks:allow -- throwaway


def _sh(*cmd: str, check: bool = True, **kw):
    import subprocess

    r = subprocess.run(list(cmd), capture_output=True, text=True, **kw)
    if check and r.returncode != 0:
        tail = "\n".join((r.stderr or r.stdout).strip().splitlines()[-15:])
        raise RuntimeError(f"{' '.join(cmd[:4])}... failed ({r.returncode}):\n{tail}")
    return r


def _server(image: str, artifacts: str) -> None:
    import time

    _sh("docker", "run", "-d", "--rm", "--name", SERVER, "--network", NET,
        "--memory", "1g", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "-v", f"{artifacts}:/mlflow/artifacts:ro",
        image, "mlflow", "server", "--host", "0.0.0.0", "--port", "5000",
        "--backend-store-uri", f"postgresql+psycopg2://postgres:{PW}@{PG}:5432/mlflow",
        "--artifacts-destination", "/mlflow/artifacts", "--serve-artifacts", "--workers", "1",
        *(["--allowed-hosts", f"{SERVER},{SERVER}:5000"] if _is_v3(image) else []))  # fmt: skip
    for _ in range(120):
        r = _probe(image, "health")
        if r == "OK":
            return
        time.sleep(1)
    raise TimeoutError(f"{image} did not become healthy")


def _is_v3(image: str) -> bool:
    """MLflow 3 refuses unknown Host headers (DNS-rebinding protection); 2.x has no flag."""
    return image.rsplit(":", 1)[-1].startswith("3.")


def _probe(image: str, what: str, run_id: str = "") -> str:
    """Run this file inside a throwaway container on the internal network."""
    import subprocess

    here = os.path.abspath(__file__)
    r = subprocess.run(
        ["docker", "run", "--rm", "--network", NET, "-v", f"{here}:/probe.py:ro", image,
         "python", "/probe.py", what, f"http://{SERVER}:5000", run_id],
        capture_output=True, text=True,
    )  # fmt: skip
    if not r.stdout.strip():
        return "PROBE-ERROR " + " | ".join(r.stderr.strip().splitlines()[-3:])
    return r.stdout.strip()


def _restored_copy(tmp: str):
    """Restore the latest snapshot into `tmp`; return (dumps dir, artifacts dir)."""
    import pathlib
    import tarfile

    from graphguard.ops import backup as bk

    bk.restic("restore", "latest", "--tag", "nightly", "--target", tmp, "--quiet")
    dumps = next(pathlib.Path(tmp).rglob("counts.json")).parent
    art = pathlib.Path(tmp) / "artifacts"
    art.mkdir()
    with tarfile.open(dumps / "mlflow-artifacts.tar") as t:
        t.extractall(art, filter="data")
    os.chmod(tmp, 0o755)  # the throwaway server (uid 10001) reads the artifacts
    for p in pathlib.Path(tmp).rglob("*"):
        p.chmod(0o755 if p.is_dir() else 0o644)
    return dumps, str(art / "artifacts")


def _start_postgres() -> None:
    import time

    from graphguard.ops import backup as bk

    _sh("docker", "network", "create", "--internal", NET)
    _sh("docker", "run", "-d", "--rm", "--name", PG, "--network", NET, "--memory", "512m",
        "--tmpfs", "/var/lib/postgresql/data", "-e", f"POSTGRES_PASSWORD={PW}",
        bk.DRILL_IMAGE)  # fmt: skip
    for _ in range(60):
        if (
            _sh("docker", "exec", PG, "pg_isready", "-U", "postgres", "-q", check=False).returncode
            == 0
        ):
            time.sleep(2)
            return
        time.sleep(1)
    raise TimeoutError("rehearsal Postgres did not start")


def _load_dump(dumps) -> None:
    import subprocess

    _sh("docker", "exec", PG, "dropdb", "-U", "postgres", "--if-exists", "mlflow")
    _sh("docker", "exec", PG, "createdb", "-U", "postgres", "mlflow")
    with open(dumps / "mlflow.dump", "rb") as f:
        subprocess.run(["docker", "exec", "-i", PG, "pg_restore", "-U", "postgres",
                        "--no-owner", "--no-privileges", "-d", "mlflow"],
                       stdin=f, check=True, capture_output=True)  # fmt: skip


def _served_snapshot(image: str) -> dict:
    raw = _probe(image, "snapshot")
    if raw.startswith("PROBE-ERROR"):
        raise RuntimeError(raw)
    return json.loads(raw)


def rehearse(new_image: str, old_image: str) -> int:
    import shutil
    import tempfile
    import time

    from graphguard.ops import backup as bk

    # A backup taken now, so the restored copy and the live server hold the same runs.
    if bk.backup() != 0:
        raise RuntimeError("the fresh backup failed; not rehearsing on a stale copy")
    live = snapshot("http://127.0.0.1:5010", _admin())
    print(f"live: {len(live['experiments'])} experiments, {len(live['runs'])} runs")
    tmp = tempfile.mkdtemp(prefix="gg-mlflow-", dir=bk.REPO_ROOT / "private" / "backups")
    try:
        dumps, art_dir = _restored_copy(tmp)
        _start_postgres()
        _load_dump(dumps)
        t0 = time.time()
        _sh("docker", "run", "--rm", "--network", NET, "--memory", "1g", new_image, "mlflow",
            "db", "upgrade", f"postgresql+psycopg2://postgres:{PW}@{PG}:5432/mlflow")  # fmt: skip
        print(f"migration: {time.time() - t0:.1f}s")
        _server(new_image, art_dir)
        diffs = compare(live, _served_snapshot(new_image))
        print(f"new server: {len(diffs)} differences")
        for d in diffs[:20]:
            print("  DIFF:", d)
        art_ok = _probe(new_image, "artifact", _run_with_lineage(live) or next(iter(live["runs"])))
        print(f"artifact download: {art_ok}")
        print(f"new server memory (1 worker, after the reads): {_memory(SERVER)}")
        _sh("docker", "stop", SERVER)
        # The way back: the pre-migration dump under the old image.
        _load_dump(dumps)
        _server(old_image, art_dir)
        back_diffs = compare(live, _served_snapshot(old_image))
        print(f"rollback to {old_image}: {len(back_diffs)} differences")
        return 0 if not diffs and not back_diffs and art_ok == "OK" else 1
    finally:
        for c in (SERVER, PG):
            _sh("docker", "rm", "-f", c, check=False)
        _sh("docker", "network", "rm", NET, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def _admin() -> tuple[str, str] | None:
    """The live server needs a login since S5b.7 (the throwaway copy has no auth app)."""
    try:
        from graphguard.ops.mlflow_auth import credentials

        return credentials("admin")
    except (ImportError, KeyError):
        return None


def _memory(container: str) -> str:
    """Anonymous (process) memory and the peak, from the cgroup -- not page cache."""
    cid = _sh("docker", "inspect", "-f", "{{.Id}}", container).stdout.strip()
    base = f"/sys/fs/cgroup/system.slice/docker-{cid}.scope"
    stat = dict(line.split() for line in open(f"{base}/memory.stat"))
    peak = int(open(f"{base}/memory.peak").read())
    anon, cache = int(stat["anon"]) >> 20, int(stat["file"]) >> 20
    return f"anon {anon} MiB, file cache {cache} MiB, peak {peak >> 20} MiB"


def _run_with_lineage(snap: dict) -> str | None:
    for rid, r in snap["runs"].items():
        if "lineage" in " ".join(r["tags"]) or r["params"].get("git_sha"):
            return rid
    return None


def _artifact(base: str, run_id: str) -> str:
    """Download the run's lineage record through the server's artifact proxy."""
    url = f"{base}/get-artifact?run_id={run_id}&path=lineage/openlineage.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return "OK" if json.load(r).get("events") is not None else "EMPTY"
    except Exception as e:  # noqa: BLE001
        return f"FAIL {type(e).__name__}: {e}"


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "health":
        try:
            with urllib.request.urlopen(f"{argv[2]}/health", timeout=3) as r:
                print("OK" if r.status == 200 else r.status)
        except Exception:  # noqa: BLE001
            print("DOWN")
        return 0
    if cmd == "snapshot":
        print(json.dumps(snapshot(argv[2])))
        return 0
    if cmd == "artifact":
        print(_artifact(argv[2], argv[3]))
        return 0
    if cmd == "rehearse":
        return rehearse(argv[2], argv[3])
    print(f"usage: {argv[0]} rehearse <new image> <old image> | snapshot <url>")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
