"""Client and server MLflow are the same version (S5b.7).

The server ran 2.19 while the client was 3.15 for months (S5.6e): some calls hit
endpoints the server did not have. Image tag, server requirements and the client lock
must name one version, or the build fails.
"""

import re
import tomllib

import pytest
import yaml

from graphguard.config import REPO_ROOT

pytestmark = pytest.mark.unit


def _compose_tag() -> str:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    image = compose["services"]["mlflow"]["image"]
    assert image.startswith("graphguard/mlflow:")
    return image.split(":", 1)[1]


def _server_requirement() -> str:
    text = (REPO_ROOT / "docker" / "mlflow-requirements.txt").read_text()
    return re.search(r"^mlflow==([\d.]+)", text, re.M).group(1)


def _client_lock() -> str:
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
    (pkg,) = [p for p in lock["package"] if p["name"] == "mlflow-skinny"]
    return pkg["version"]


def test_image_server_and_client_name_one_mlflow_version():
    assert _compose_tag() == _server_requirement() == _client_lock()


def test_server_requirements_are_hash_pinned():
    text = (REPO_ROOT / "docker" / "mlflow-requirements.txt").read_text()
    pins = re.findall(r"^[A-Za-z0-9_.\-\[\]]+==", text, re.M)
    assert pins and text.count("--hash=sha256:") >= len(pins)


def test_the_server_image_installs_by_hash_on_a_pinned_base():
    df = (REPO_ROOT / "docker" / "mlflow.Dockerfile").read_text()
    assert re.search(r"^FROM \S+@sha256:[0-9a-f]{64}", df, re.M)
    assert "--require-hashes" in df
