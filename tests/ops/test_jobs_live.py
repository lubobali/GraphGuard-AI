"""One user per job, proven from INSIDE each job (S5b.5).

Each test starts a real transient unit from the job's own profile, swaps the job's
command for a probe, and the probe tries to reach what the job must not. Runs on the
box as root once the job users exist (`just job-users-install`); skips elsewhere (CI).
"""

import dataclasses
import json
import os
import pwd
import subprocess

import pytest

from graphguard.config import RAW_DIR, REPO_ROOT
from graphguard.ops import jobs


def _users_exist():
    try:
        return all(pwd.getpwnam(u) for u in jobs.USERS) and os.geteuid() == 0
    except KeyError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _users_exist(), reason="job users not installed (S5b.5) or not root"),
]

S = REPO_ROOT / ".secrets"
PROBE = r"""
import json, os, socket, sys
out = {"uid": os.getuid()}
for p in sys.argv[1:]:
    try:
        with open(p, "rb") as f:
            f.read(1)
        out[p] = "read"
    except FileNotFoundError:
        out[p] = "absent"
    except PermissionError:
        out[p] = "denied"
try:
    s = socket.socket(socket.AF_UNIX); s.connect("/run/docker.sock"); out["docker"] = "connected"
except OSError:
    out["docker"] = "refused"
cd = os.environ.get("CREDENTIALS_DIRECTORY")
out["creds"] = sorted(os.listdir(cd)) if cd else []
print("PROBE" + json.dumps(out))
"""


def _probe(job_name: str, paths: list) -> dict:
    job = dataclasses.replace(jobs.JOBS[job_name], command=("-c", PROBE), pty=False)
    raw = [p.name for p in RAW_DIR.iterdir()]
    cmd = jobs.unit_args(job, [str(p) for p in paths], raw, {})
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
    (line,) = [x for x in r.stdout.splitlines() if x.startswith("PROBE")]
    return json.loads(line[5:])


FORBIDDEN_FOR_ALL = [
    S / "identity-admin.env",
    S / "aws.env",
    S / "redis.env",
    S / "mlflow.env",
    S / "backup-restic-password",
    REPO_ROOT / "private" / "security",
    "/etc/rancher/k3s/k3s.yaml",
]
CSV = [RAW_DIR / "HI-Small_Trans.csv", RAW_DIR / "HI-Small_accounts.csv"]


def _blocked(v):
    return v in {"absent", "denied"}


@pytest.mark.parametrize(
    ("job", "own", "other_identities"),
    [
        ("lakehouse-build", "identity-builder.env", ["trainer", "reader"]),
        ("build-artifacts", "identity-trainer.env", ["builder", "reader"]),
        ("store-load", "identity-reader.env", ["builder", "trainer"]),
        ("sql", "identity-reader.env", ["builder", "trainer"]),
    ],
)
def test_a_job_holds_only_its_own_key_and_reaches_nothing_else(job, own, other_identities):
    others = [S / f"identity-{o}.env" for o in other_identities]
    got = _probe(job, [*FORBIDDEN_FOR_ALL, *others])
    assert got["uid"] == pwd.getpwnam(jobs.JOBS[job].user).pw_uid != 0
    for p in [*FORBIDDEN_FOR_ALL, *others]:
        assert _blocked(got[str(p)]), f"{job} could read {p}"
    assert got["docker"] == "refused"
    assert own in got["creds"] and not any(o.name in got["creds"] for o in others)


@pytest.mark.parametrize("job", ["build-artifacts", "store-load", "sql"])
def test_trainer_and_reader_cannot_read_the_raw_csvs(job):
    got = _probe(job, CSV)
    assert all(_blocked(got[str(p)]) for p in CSV), got


def test_the_builder_can_read_the_raw_csvs():
    got = _probe("lakehouse-build", CSV)
    assert all(got[str(p)] == "read" for p in CSV)


def test_the_store_loader_holds_only_the_loader_password():
    job = dataclasses.replace(
        jobs.JOBS["store-load"],
        command=(
            "-c",
            "import os;print('PW'+open(os.environ['CREDENTIALS_DIRECTORY']+'/redis.env').read())",
        ),
        pty=False,
    )
    r = subprocess.run(jobs.unit_args(job, [], [], {}), capture_output=True, text=True, check=True)
    names = [ln.split("=")[0] for ln in r.stdout.split("PW", 1)[1].splitlines() if "=" in ln]
    assert names == ["GG_REDIS_LOADER_PASSWORD"]


def test_as_trainer_the_builder_login_and_the_test_window_are_out_of_reach():
    code = r"""
import json
from graphguard.lakehouse.catalog import open_catalog
out = {}
try:
    open_catalog("builder"); out["builder"] = "opened"
except Exception as e:
    out["builder"] = type(e).__name__
cat = open_catalog("trainer")
for ident in ("sealed.transactions", "bronze.transactions_raw"):
    try:
        cat.load_table(ident).scan(limit=1).to_arrow(); out[ident] = "read"
    except Exception as e:
        out[ident] = type(e).__name__
out["silver"] = cat.load_table("silver.transactions").scan(limit=1).to_arrow().num_rows
print("PROBE" + json.dumps(out))
"""
    job = dataclasses.replace(jobs.JOBS["build-artifacts"], command=("-c", code), pty=False)
    r = subprocess.run(
        jobs.unit_args(job, [], [p.name for p in RAW_DIR.iterdir()], {}),
        capture_output=True, text=True, timeout=120, check=True,
    )  # fmt: skip
    (line,) = [x for x in r.stdout.splitlines() if x.startswith("PROBE")]
    got = json.loads(line[5:])
    assert got["builder"] == "FileNotFoundError"  # there is no builder secret to log in with
    assert got["sealed.transactions"] != "read" and got["bronze.transactions_raw"] != "read"
    assert got["silver"] == 1  # and its own job still works
