"""One user per job (S5b.5): every job is unprivileged, sandboxed and holds only its own key."""

import os

import pytest

from graphguard import config
from graphguard.config import RAW_DIR, REPO_ROOT
from graphguard.ops import jobs

pytestmark = pytest.mark.unit

RAW = ["HI-Small_Trans.csv", "HI-Small_accounts.csv", "HI-Small_Patterns.txt"]


def _props(job, args=()):
    cmd = jobs.unit_args(job, list(args), RAW, {"GRAPHGUARD_X": "1", "AWS_SECRET_ACCESS_KEY": "s"})
    props, env = {}, {}
    for flag, val in zip(cmd, cmd[1:], strict=False):
        if flag == "-p":
            k, _, v = val.partition("=")
            props.setdefault(k, []).append(v)
        elif flag == "-E":
            k, _, v = val.partition("=")
            env[k] = v
    return cmd, props, env


ALL = list(jobs.JOBS.values())


@pytest.mark.parametrize("job", ALL, ids=lambda j: j.name)
def test_every_job_runs_as_its_own_unprivileged_user(job):
    _, p, _ = _props(job)
    assert p["User"] == [job.user] and job.user in jobs.USERS
    assert p["CapabilityBoundingSet"] == [""] and p["NoNewPrivileges"] == ["yes"]
    assert p["ProtectSystem"] == ["strict"] and p["ProtectProc"] == ["invisible"]
    assert p["MemoryMax"] and p["MemorySwapMax"] == ["0"]


@pytest.mark.parametrize("job", ALL, ids=lambda j: j.name)
def test_no_job_can_see_secrets_private_docker_or_k3s(job):
    _, p, _ = _props(job)
    hidden = p["InaccessiblePaths"][0].split()
    for path in (".secrets", "private", "runner"):
        assert f"-{REPO_ROOT / path}" in hidden
    assert {"-/run/docker.sock", "-/etc/rancher", "-/var/lib/rancher"} <= set(hidden)


@pytest.mark.parametrize("job", ALL, ids=lambda j: j.name)
def test_each_job_is_handed_only_its_own_identity(job):
    _, p, _ = _props(job)
    creds = p["LoadCredential"]
    identities = [c for c in creds if c.startswith("identity-")]
    want = {"gg-builder": "builder", "gg-trainer": "trainer", "gg-reader": "reader"}[job.user]
    assert [c.split(":")[0] for c in identities] == [f"identity-{want}.env"]
    for c in creds:  # never the admin, the old S5.6b key, or all Redis passwords at once
        src = c.split(":", 1)[1]
        assert not src.endswith(("identity-admin.env", "/aws.env", "/redis.env", "mlflow.env"))


def test_trainer_and_reader_cannot_see_the_raw_csvs():
    for name in ("build-artifacts", "store-load", "sql", "notebook"):
        _, p, _ = _props(jobs.JOBS[name])
        hidden = p["InaccessiblePaths"][0]
        assert f"-{RAW_DIR}" in hidden.split() or (
            f"-{RAW_DIR / 'HI-Small_Trans.csv'}" in hidden
            and f"-{RAW_DIR / 'HI-Small_accounts.csv'}" in hidden
        ), name


def test_only_the_builder_reads_the_raw_csvs():
    _, p, _ = _props(jobs.JOBS["lakehouse-build"])
    assert str(RAW_DIR) not in p["InaccessiblePaths"][0]


def test_the_store_loader_gets_only_the_loader_password():
    _, p, _ = _props(jobs.JOBS["store-load"])
    assert f"redis.env:{jobs.SECRETS / 'redis-loader.env'}" in p["LoadCredential"]


def test_writes_are_only_what_each_job_produces():
    for job in ALL:
        _, p, _ = _props(job)
        rw = p.get("ReadWritePaths", [""])[0].split()
        assert all(path.startswith(str(REPO_ROOT)) for path in rw)
        assert str(REPO_ROOT) not in rw and str(REPO_ROOT / "models") not in rw
    assert jobs.JOBS["sql"].writes == ()


def test_the_callers_environment_is_not_passed_through():
    cmd, _, env = _props(jobs.JOBS["sql"], ["select 1"])
    assert "AWS_SECRET_ACCESS_KEY" not in env and env["GRAPHGUARD_X"] == "1"
    assert cmd[-3:] == ["-m", "graphguard.lakehouse.sql", "select 1"]
    assert cmd[cmd.index("-m") - 1] == str(jobs.PYTHON)  # the venv, never `uv` (no syncing)


def test_secrets_come_from_the_credentials_directory_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    assert config.secrets_dir() == tmp_path
    monkeypatch.delenv("CREDENTIALS_DIRECTORY")
    assert config.secrets_dir() == REPO_ROOT / ".secrets"


def test_identity_and_redis_read_from_the_credentials_directory(tmp_path, monkeypatch):
    from graphguard.lakehouse.identity import identity_file
    from graphguard.serving.redis_acl import password

    (tmp_path / "redis.env").write_text("GG_REDIS_LOADER_PASSWORD=pw\n")
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    assert identity_file("trainer") == tmp_path / "identity-trainer.env"
    assert password("loader") == "pw"
    with pytest.raises(KeyError):
        password("scorer")  # a job holds only its own password
    assert os.environ["CREDENTIALS_DIRECTORY"] == str(tmp_path)


def test_jobs_spill_and_find_git_inside_their_sandbox():
    _, _, env = _props(jobs.JOBS["sql"])
    assert env["GRAPHGUARD_SPILL_DIR"].startswith("/tmp/")  # PrivateTmp, not the repo
    assert env["GIT_CONFIG_KEY_0"] == "safe.directory"
    assert env["GIT_CONFIG_VALUE_0"] == str(REPO_ROOT)  # this repo only


def test_two_runs_of_one_job_get_different_unit_names():
    # Found by S5.7's pre-commit: names built from the current second collided when two
    # runs of the same job started together (parallel tests, or two `just sql` at once).
    def unit(cmd):
        return next(a for a in cmd if a.startswith("--unit="))

    job = jobs.JOBS["sql"]
    names = {unit(jobs.unit_args(job, [], RAW, {})) for _ in range(50)}
    assert len(names) == 50
