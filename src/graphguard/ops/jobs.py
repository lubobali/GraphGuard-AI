"""One user per job (S5b.5): each lakehouse job runs as its own unprivileged user.

`just lakehouse-build`, `build-artifacts`, `store-load`, `sql` and `notebook` start a
transient systemd unit from a profile below. The unit runs as that job's user, capped,
read-only everywhere except what it writes, with no capabilities, no view of other
processes — and **only its own credentials**, handed in by systemd at
`$CREDENTIALS_DIRECTORY` (`graphguard.config.secrets_dir()` reads them there).
`.secrets/`, `private/`, the Docker socket and k3s are invisible to every job; trainer
and reader cannot see the raw CSVs either (they hold the test window, FINDING-011).

So "trainer cannot read the test set" holds even for a trainer process that goes
looking: there is no other job's key, no raw file and no Docker to reach for. This
closes the honest limit in ADR 0003 for jobs. Admin setup and tests stay root.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field

from graphguard.config import RAW_DIR, REPO_ROOT

SECRETS = REPO_ROOT / ".secrets"
PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
LINEAGE_DIR = REPO_ROOT / "lakehouse" / "lineage"
USERS = ("gg-builder", "gg-trainer", "gg-reader")
JOBS_GROUP = "gg-jobs"

# Never visible to any job ("-" = fine if it does not exist).
HIDDEN_FROM_ALL = (
    str(SECRETS),
    str(REPO_ROOT / "private"),
    str(REPO_ROOT / "runner"),
    "/run/docker.sock",
    "/etc/rancher",
    "/var/lib/rancher",
)


@dataclass(frozen=True)
class Job:
    name: str
    user: str
    command: tuple[str, ...]
    credentials: tuple[str, ...]  # file names in .secrets/, handed in read-only
    memory: str
    writes: tuple[str, ...] = ()  # paths under the repo it may write
    raw_allowed: tuple[str, ...] | None = None  # None = all raw files; () = none
    pty: bool = False
    extra: dict[str, str] = field(default_factory=dict)


JOBS: dict[str, Job] = {
    j.name: j
    for j in (
        Job(
            "lakehouse-build",
            "gg-builder",
            ("-m", "graphguard.lakehouse.build"),
            ("identity-builder.env",),
            memory="1800M",  # peak ~1.3 GB
            writes=("lakehouse/lineage", "lakehouse/tmp"),  # tmp: staged parquet
        ),
        Job(
            "build-artifacts",
            "gg-trainer",
            ("-m", "graphguard.serving.build_artifacts"),
            ("identity-trainer.env", "mlflow-trainer.env"),
            memory="2560M",  # measured peak 2,042 MiB (2026-11-19)
            writes=("lakehouse/lineage", "models/production"),
            # The ring list, joined onto silver (train + validation) only. The CSVs stay
            # hidden. Moving the ring list into the lakehouse is a follow-up.
            raw_allowed=("HI-Small_Patterns.txt",),
            extra={"GRAPHGUARD_MLFLOW_USER": "trainer"},
        ),
        Job(
            "store-load",
            "gg-reader",
            ("-m", "graphguard.lakehouse.store_load"),
            ("identity-reader.env", "redis-loader.env:redis.env"),
            memory="1G",  # peak ~0.6 GB
            writes=("lakehouse/lineage",),
            raw_allowed=(),
        ),
        Job(
            "sql",
            "gg-reader",
            ("-m", "graphguard.lakehouse.sql"),
            ("identity-reader.env",),
            memory="512M",
            raw_allowed=(),
        ),
        Job(
            "notebook",
            "gg-reader",
            (
                "-m",
                "marimo",
                "edit",
                "notebooks/lakehouse.py",
                "--host",
                "127.0.0.1",
                "--port",
                "2718",
                "--headless",
            ),
            ("identity-reader.env",),
            memory="1G",
            writes=("notebooks",),
            raw_allowed=(),
            pty=True,
        ),  # fmt: skip
    )
}


def _credential(spec: str) -> str:
    """`file` or `file:name-inside-the-unit` → a LoadCredential value."""
    src, _, name = spec.partition(":")
    return f"{name or src}:{SECRETS / src}"


def hidden_paths(job: Job, raw_files: list[str]) -> list[str]:
    hidden = list(HIDDEN_FROM_ALL)
    if job.raw_allowed is not None:
        if not job.raw_allowed:
            hidden.append(str(RAW_DIR))
        else:
            hidden += [str(RAW_DIR / f) for f in sorted(raw_files) if f not in job.raw_allowed]
    return hidden


def unit_args(job: Job, args: list[str], raw_files: list[str], env: dict[str, str]) -> list[str]:
    """The `systemd-run` command for one job (pure, tested)."""
    props = {
        "User": job.user,
        "Group": job.user,
        "WorkingDirectory": str(REPO_ROOT),
        "MemoryMax": job.memory,
        "MemorySwapMax": "0",
        "ProtectSystem": "strict",
        "ProtectHome": "yes",
        "PrivateTmp": "yes",
        "PrivateDevices": "yes",
        "ProtectProc": "invisible",
        "NoNewPrivileges": "yes",
        "RestrictSUIDSGID": "yes",
        "CapabilityBoundingSet": "",
        "UMask": "0002",
        "InaccessiblePaths": " ".join(f"-{p}" for p in hidden_paths(job, raw_files)),
    }
    if job.writes:
        props["ReadWritePaths"] = " ".join(str(REPO_ROOT / w) for w in job.writes)
    cmd = ["systemd-run", "--wait", "--collect", "--quiet", "--pty" if job.pty else "--pipe",
           f"--unit=gg-job-{job.name}-{uuid.uuid4().hex[:12]}"]  # fmt: skip
    for k, v in props.items():
        cmd += ["-p", f"{k}={v}"]
    for c in job.credentials:
        cmd += ["-p", f"LoadCredential={_credential(c)}"]
    # Only the overrides a job is meant to honour; never the caller's whole environment.
    passed = {
        k: v for k, v in env.items() if k.startswith("GRAPHGUARD_") or k == "MLFLOW_TRACKING_URI"
    }
    base = {
        "HOME": "/tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
        "GRAPHGUARD_SPILL_DIR": "/tmp/duckdb",  # DuckDB spills into the job's private /tmp
        # Lineage records the git sha; git refuses a repo owned by another user unless
        # told it is safe. For this repo only, for this job only.
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "safe.directory",
        "GIT_CONFIG_VALUE_0": str(REPO_ROOT),
    }
    for k, v in sorted({**base, **passed, **job.extra}.items()):
        cmd += ["-E", f"{k}={v}"]
    return [*cmd, str(PYTHON), *job.command, *args]


def run(name: str, args: list[str]) -> int:
    job = JOBS[name]
    raw = [p.name for p in RAW_DIR.iterdir()] if RAW_DIR.exists() else []
    cmd = unit_args(job, args, raw, dict(os.environ))
    os.execvp(cmd[0], cmd)  # the job's exit code is systemd-run's


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "run" or argv[2] not in JOBS:
        print(f"usage: {argv[0]} run {{{'|'.join(JOBS)}}} [args...]")
        return 2
    return run(argv[2], argv[3:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
