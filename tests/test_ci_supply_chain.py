"""CI supply chain (S5b.2): pinned actions, isolated and unprivileged jobs."""

import re

import pytest
import yaml

from graphguard.config import REPO_ROOT

pytestmark = pytest.mark.unit

WORKFLOWS = sorted((REPO_ROOT / ".forgejo" / "workflows").glob("*.y*ml"))
RUNNER_CONFIG = REPO_ROOT / "runner" / "config.yml"


def _steps():
    for wf in WORKFLOWS:
        for job in (yaml.safe_load(wf.read_text()).get("jobs") or {}).values():
            for step in job.get("steps", []):
                yield wf.name, step


def test_there_are_workflows():
    assert WORKFLOWS


def test_every_action_is_pinned_to_a_full_commit_sha():
    # A tag can be moved to malicious code (tj-actions 2025, trivy-action 2026); a SHA cannot.
    for wf, step in _steps():
        if "uses" in step:
            ref = step["uses"].split("@", 1)[1] if "@" in step["uses"] else ""
            assert re.fullmatch(r"[0-9a-f]{40}", ref), f"{wf}: {step['uses']} is not a commit SHA"


def test_every_job_has_a_timeout_and_runs_on_our_runner():
    for wf in WORKFLOWS:
        for name, job in yaml.safe_load(wf.read_text())["jobs"].items():
            assert job.get("timeout-minutes"), f"{wf.name}:{name} has no timeout"
            assert job.get("runs-on") == "graphguard", f"{wf.name}:{name}"


def test_every_job_proves_its_isolation_first():
    for wf in WORKFLOWS:
        for name, job in yaml.safe_load(wf.read_text())["jobs"].items():
            runs = [s["run"] for s in job["steps"] if "run" in s]  # checkout has no `run`
            assert "isolation-probe.sh" in runs[0], (
                f"{wf.name}:{name}: probe is not the first run step"
            )


def test_no_job_installs_system_packages():
    # apt needs root powers; the job image carries git/curl so jobs run with none.
    for wf, step in _steps():
        assert "apt-get" not in step.get("run", ""), wf


@pytest.mark.skipif(
    not RUNNER_CONFIG.exists(),
    reason="runner/config.yml is local to the box (gitignored); in CI the probe checks it live",
)
def test_the_runner_isolates_and_unprivileges_every_job():
    cfg = yaml.safe_load(RUNNER_CONFIG.read_text())
    c = cfg["container"]
    assert c["network"] == ""  # a fresh network per job, never the shared default bridge
    assert c["privileged"] is False and c["docker_host"] == "-" and not c["valid_volumes"]
    assert "--cap-drop=ALL" in c["options"] and "--security-opt=no-new-privileges" in c["options"]
    assert cfg["cache"]["enabled"] is False
    assert cfg["runner"]["labels"] == ["graphguard:docker://graphguard/ci:1"]
    assert not cfg["runner"].get("envs")
