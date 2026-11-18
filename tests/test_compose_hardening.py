"""Every GraphGuard container meets the same floor (S5b.1).

Adding a service to docker-compose.yml without these fails the build, so the August-era
gap (three unhardened containers next to hardened ones) cannot come back.
"""

import pytest
import yaml

from graphguard.config import REPO_ROOT

pytestmark = pytest.mark.unit

SERVICES = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())["services"]

# Built here from docker/*.Dockerfile, so pinned by its pinned base and its tag, and
# its non-root user is the Dockerfile's USER (10001), not a compose `user:`.
LOCALLY_BUILT = {"mlflow"}
# Run-once jobs that exit; they need no ports, logs rotation or read-only tmpfs.
ONE_SHOT = {"lakekeeper-migrate", "openfga-migrate"}


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_every_service_is_capped_and_unprivileged(name):
    svc = SERVICES[name]
    assert svc.get("mem_limit"), f"{name}: no memory cap (swap on this box is ~full)"
    assert svc.get("cap_drop") == ["ALL"], f"{name}: capabilities not dropped"
    assert "no-new-privileges:true" in svc.get("security_opt", []), name
    assert 0 < svc.get("pids_limit", 0) <= 256, name
    assert svc.get("read_only") is True, f"{name}: writable root filesystem"
    if name not in LOCALLY_BUILT:
        assert not str(svc.get("user", "0")).startswith("0"), f"{name}: runs as root"


@pytest.mark.parametrize("name", sorted(set(SERVICES) - LOCALLY_BUILT))
def test_every_pulled_image_is_pinned_by_digest(name):
    assert "@sha256:" in SERVICES[name]["image"], name


@pytest.mark.parametrize("name", sorted(set(SERVICES) - ONE_SHOT))
def test_every_long_running_service_rotates_logs(name):
    opts = SERVICES[name].get("logging", {}).get("options", {})
    assert opts.get("max-size") and opts.get("max-file"), name


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_no_port_is_published_on_all_interfaces(name):
    for p in SERVICES[name].get("ports", []):
        host = str(p).rsplit(":", 2)[0]
        assert host.startswith(("127.0.0.1", "10.42.0.1")), f"{name}: {p}"


def test_no_service_mounts_the_docker_socket():
    for name, svc in SERVICES.items():
        assert not any("docker.sock" in str(v) for v in svc.get("volumes", [])), name
