"""GraphGuard's backups (S5b.3): nightly to an Object-Lock bucket, restored every week.

    just backup            # dumps + restic backup + retention (the nightly timer runs this)
    just restore-check     # restore the latest snapshot and prove it (the weekly timer)
    just backup-status     # exit 1 if the last backup or drill is stale or failed

What is kept: every GraphGuard database (one `pg_dump -Fc` each, the list comes from
`pg_access.SERVICES`, so a new service database cannot be forgotten) plus the roles,
the MLflow artifacts volume, `.secrets/` (without it the dumps cannot be brought back
to life), `models/production/` and `private/`. Not kept: the lakehouse data (S3,
versioned), Redis (rebuilt from gold), the raw CSV (Kaggle).

At backup time the row counts of key tables go *into* the backup (`counts.json`); the
drill restores the dumps into a throwaway Postgres and must find exactly those counts.

The bucket keeps every object for 30 days (Object Lock, Governance) and the backup key
cannot delete a version or shorten a retention: a compromised box can add backups but
not destroy them. Retention is time-based (`--keep-within`), never count-based -- an
attacker could otherwise plant snapshots to push the real ones out.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from graphguard.config import REPO_ROOT
from graphguard.ops.pg_access import SERVICES

RESTIC = REPO_ROOT / ".tools" / "bin" / "restic"
SECRETS = REPO_ROOT / ".secrets"
STATUS_FILE = REPO_ROOT / "private" / "backups" / "status.json"
PG_CONTAINER = "graphguard-mlflow-db"
MLFLOW_CONTAINER = "graphguard-mlflow"
DRILL_IMAGE = (
    "postgres:16.16-alpine@sha256:81e77a4833487b8132fe4b00bedd39dc3f74b8641e387f19312a48f7de218c2e"
)
PATHS = (".secrets", "models/production", "private")
KEEP_WITHIN = "30d"
MAX_BACKUP_AGE = dt.timedelta(days=2)
MAX_DRILL_AGE = dt.timedelta(days=8)

# Row counts that must survive a backup and restore, per database.
COUNTS: dict[str, dict[str, str]] = {
    "mlflow": {
        "experiments": "select count(*) from experiments",
        "runs": "select count(*) from runs",
        "metrics": "select count(*) from metrics",
        "params": "select count(*) from params",
    },
    "lakekeeper": {
        "tabulars": "select count(*) from tabular",
        "warehouses": "select count(*) from warehouse",
    },
    "openfga": {"tuples": "select count(*) from tuple"},
    "dex": {"keys": "select count(*) from keys"},
}


def databases() -> list[str]:
    """Every service database, from the access rules (single source of truth)."""
    return sorted(SERVICES)


def retention_args() -> list[str]:
    return ["forget", "--keep-within", KEEP_WITHIN, "--tag", "nightly"]


# --- the environment ----------------------------------------------------------


def _read_env(path: Path) -> dict[str, str]:
    return dict(
        ln.split("=", 1)
        for ln in path.read_text().splitlines()
        if "=" in ln and not ln.startswith("#")
    )


def restic_env() -> dict[str, str]:
    """restic's settings: the bucket key, the repository, the password *file* (never
    the password itself in the environment of a process listing)."""
    # A local repository, for rehearsing the whole pipeline without the bucket.
    if local := os.environ.get("GRAPHGUARD_BACKUP_LOCAL_REPO"):
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/root"),
            "RESTIC_REPOSITORY": local,
            "RESTIC_PASSWORD_FILE": os.environ["GRAPHGUARD_BACKUP_PASSWORD_FILE"],
            "RESTIC_CACHE_DIR": str(REPO_ROOT / ".tools" / "restic-cache"),
        }
    aws = _read_env(SECRETS / "backup-aws.env")
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/root"),
        "AWS_ACCESS_KEY_ID": aws["AWS_ACCESS_KEY_ID"],
        "AWS_SECRET_ACCESS_KEY": aws["AWS_SECRET_ACCESS_KEY"],
        "AWS_DEFAULT_REGION": aws.get("AWS_REGION", "us-east-1"),
        "RESTIC_REPOSITORY": aws["RESTIC_REPOSITORY"],
        "RESTIC_PASSWORD_FILE": str(SECRETS / "backup-restic-password"),
        "RESTIC_CACHE_DIR": str(REPO_ROOT / ".tools" / "restic-cache"),
    }


def restic(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(RESTIC), *args], env=restic_env(), check=True, text=True, capture_output=capture
    )


def _psql(
    db: str, sql: str, container: str = PG_CONTAINER, pw_env: str = "POSTGRES_PASSWORD"
) -> str:
    out = subprocess.run(
        [
            "docker",
            "exec",
            container,
            "sh",
            "-c",
            f'PGPASSWORD="${pw_env}" psql -U "$POSTGRES_USER" -d {db} -Atc "{sql}"',
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return out.stdout.strip()


def table_counts(container: str = PG_CONTAINER) -> dict[str, dict[str, int]]:
    return {
        db: {k: int(_psql(db, q, container)) for k, q in qs.items()} for db, qs in COUNTS.items()
    }


# --- backup -------------------------------------------------------------------


def dump_all(out: Path) -> None:
    """One custom-format dump per database plus the roles, the artifacts tar, and the
    row counts at this moment."""
    for db in databases():
        with open(out / f"{db}.dump", "wb") as f:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    PG_CONTAINER,
                    "sh",
                    "-c",
                    f'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U "$POSTGRES_USER" -Fc {db}',
                ],
                check=True,
                stdout=f,
            )
    with open(out / "globals.sql", "wb") as f:
        subprocess.run(
            [
                "docker",
                "exec",
                PG_CONTAINER,
                "sh",
                "-c",
                'PGPASSWORD="$POSTGRES_PASSWORD" pg_dumpall -U "$POSTGRES_USER" --globals-only',
            ],
            check=True,
            stdout=f,
        )
    with open(out / "mlflow-artifacts.tar", "wb") as f:
        subprocess.run(
            ["docker", "exec", MLFLOW_CONTAINER, "tar", "-C", "/mlflow", "-cf", "-", "artifacts"],
            check=True,
            stdout=f,
        )
    (out / "counts.json").write_text(json.dumps(table_counts(), indent=2, sort_keys=True))
    (out / "model.sha256").write_text(_sha256(REPO_ROOT / "models" / "production" / "model.json"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _status(update: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else {}
    data.update(update)
    STATUS_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.chmod(STATUS_FILE, 0o600)


def backup() -> int:
    t0 = time.time()
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    try:
        with tempfile.TemporaryDirectory(
            prefix="gg-backup-", dir=REPO_ROOT / "private" / "backups"
        ) as tmp:
            dumps = Path(tmp) / "dumps"
            dumps.mkdir()
            dump_all(dumps)
            os.chdir(REPO_ROOT)  # relative paths, so a restore lands in a clean tree
            out = restic(
                "backup",
                "--tag",
                "nightly",
                "--json",
                "--quiet",
                str(dumps.relative_to(REPO_ROOT)),
                *PATHS,
                capture=True,
            )
            summary = json.loads(out.stdout.strip().splitlines()[-1])
        restic(*retention_args(), "--quiet")
        if dt.datetime.now(dt.UTC).weekday() == 6:  # prune on Sundays only
            restic("prune", "--quiet")
        _status(
            {
                "backup": {
                    "ok": True,
                    "at": now,
                    "snapshot": summary.get("snapshot_id"),
                    "bytes_added": summary.get("data_added"),
                    "seconds": round(time.time() - t0),
                }
            }
        )
        print(
            f"backup ok: snapshot {summary.get('snapshot_id', '')[:8]}, "
            f"{summary.get('data_added', 0)} bytes added, {time.time() - t0:.0f}s"
        )
        return 0
    except Exception as e:  # recorded, then re-raised: the unit fails visibly too
        _status(
            {"backup": {"ok": False, "at": now, "error": f"{type(e).__name__}: {str(e)[:300]}"}}
        )
        raise


# --- the weekly drill -----------------------------------------------------------


def drill_run_args(name: str) -> list[str]:
    """`docker run` for the drill's throwaway Postgres: offline, no capabilities, no
    privilege escalation, 256 MB, its own non-root uid, data only in memory."""
    return [
        "docker", "run", "-d", "--rm", "--name", name,
        "--network", "none",
        "--memory", "256m", "--pids-limit", "128",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "70:70",
        "--tmpfs", "/var/lib/postgresql/data:uid=70,gid=70,mode=0700",
        "--tmpfs", "/var/run/postgresql:uid=70,gid=70",
        "--tmpfs", "/tmp:uid=70,gid=70",
        "-e", "POSTGRES_PASSWORD=drill", "-e", "POSTGRES_USER=postgres",
        DRILL_IMAGE,
    ]  # fmt: skip


def _drill_container(name: str) -> None:
    subprocess.run(drill_run_args(name), check=True, capture_output=True)
    for _ in range(60):
        r = subprocess.run(["docker", "exec", name, "pg_isready", "-U", "postgres", "-q"])
        if r.returncode == 0:
            time.sleep(1)
            return
        time.sleep(1)
    raise TimeoutError("drill Postgres did not start")


def restore_check() -> int:
    t0 = time.time()
    now = dt.datetime.now(dt.UTC)
    name = f"gg-restore-drill-{int(t0)}"
    try:
        week = now.isocalendar().week
        restic("check", f"--read-data-subset={week % 5 + 1}/5", "--quiet")
        with tempfile.TemporaryDirectory(
            prefix="gg-drill-", dir=REPO_ROOT / "private" / "backups"
        ) as tmp:
            restic("restore", "latest", "--tag", "nightly", "--target", tmp, "--quiet")
            root = Path(tmp)
            dumps = next(root.rglob("counts.json")).parent
            expected = json.loads((dumps / "counts.json").read_text())
            # secrets and model come back byte for byte
            for f in (root / ".secrets").iterdir():
                live = SECRETS / f.name
                assert live.exists() and live.read_bytes() == f.read_bytes(), (
                    f"secret {f.name} differs"
                )
            assert (
                _sha256(root / "models/production/model.json")
                == (dumps / "model.sha256").read_text()
            )
            _drill_container(name)
            # Each dump streams in on stdin: `docker cp` cannot write into the
            # container's tmpfs, so a copied file would be invisible to Postgres.
            for db in databases():
                subprocess.run(
                    ["docker", "exec", name, "createdb", "-U", "postgres", db],
                    check=True,
                    capture_output=True,
                )
                with open(dumps / f"{db}.dump", "rb") as f:
                    subprocess.run(
                        [
                            "docker",
                            "exec",
                            "-i",
                            name,
                            "pg_restore",
                            "-U",
                            "postgres",
                            "--no-owner",
                            "--no-privileges",
                            "-d",
                            db,
                        ],
                        stdin=f,
                        check=True,
                        capture_output=True,
                    )
            got = {
                db: {
                    k: int(
                        subprocess.run(
                            ["docker", "exec", name, "psql", "-U", "postgres", "-d", db, "-Atc", q],
                            check=True,
                            text=True,
                            capture_output=True,
                        ).stdout.strip()
                    )
                    for k, q in qs.items()
                }
                for db, qs in COUNTS.items()
            }
            assert got == expected, f"restored counts {got} != backed-up counts {expected}"
        _status(
            {
                "drill": {
                    "ok": True,
                    "at": now.isoformat(timespec="seconds"),
                    "counts": got,
                    "seconds": round(time.time() - t0),
                }
            }
        )
        print(
            f"restore drill ok: {sum(len(v) for v in got.values())} counts match, "
            f"secrets and model byte-equal, {time.time() - t0:.0f}s"
        )
        return 0
    except Exception as e:
        _status(
            {
                "drill": {
                    "ok": False,
                    "at": now.isoformat(timespec="seconds"),
                    "error": f"{type(e).__name__}: {str(e)[:300]}",
                }
            }
        )
        raise
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


# --- status -----------------------------------------------------------------------


def assess(status: dict, now: dt.datetime) -> list[str]:
    """Problems with the backup status. Pure, so the alarm logic is tested."""
    problems = []
    for key, max_age in (("backup", MAX_BACKUP_AGE), ("drill", MAX_DRILL_AGE)):
        s = status.get(key)
        if not s:
            problems.append(f"no {key} recorded yet")
            continue
        if not s.get("ok"):
            problems.append(f"last {key} FAILED at {s.get('at')}: {s.get('error')}")
        age = now - dt.datetime.fromisoformat(s["at"])
        if age > max_age:
            problems.append(f"last {key} is {age.days} days old (limit {max_age.days})")
    return problems


def status_main() -> int:
    status = json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else {}
    for key in ("backup", "drill"):
        s = status.get(key, {})
        print(f"{key:7s} {'ok' if s.get('ok') else 'FAIL' if s else '-':5s} {s.get('at', 'never')}")
    problems = assess(status, dt.datetime.now(dt.UTC))
    for p in problems:
        print(f"  PROBLEM: {p}")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "status"
    if cmd == "backup":
        return backup()
    if cmd == "restore-check":
        return restore_check()
    if cmd == "status":
        return status_main()
    if cmd == "init":
        restic("init")
        return 0
    print(f"unknown command {cmd!r}: backup | restore-check | status | init")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
