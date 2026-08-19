"""A run must survive the round trip to the tracking server and back.

Marked integration: it needs the MLflow service running. It skips rather than
fails when the server is unreachable, so CI (which runs in a container with no
route to the host's localhost) reports honestly instead of red.
"""

import urllib.error
import urllib.request

import pytest

from graphguard.config import MLFLOW_TRACKING_URI
from graphguard.tracking import log_run, start_tracking


def _server_up() -> bool:
    try:
        urllib.request.urlopen(f"{MLFLOW_TRACKING_URI}/health", timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


requires_server = pytest.mark.skipif(
    not _server_up(), reason=f"MLflow not reachable at {MLFLOW_TRACKING_URI}"
)


@pytest.mark.integration
@requires_server
def test_run_round_trips():
    """Params and metrics written must read back identically."""
    client, experiment_id = start_tracking("graphguard-tests")

    run_id = log_run(
        experiment_id,
        params={"model": "smoke", "seed": "42"},
        metrics={"precision_at_k": 0.5},
        tags={"phase": "0"},
    )

    run = client.get_run(run_id)
    assert run.data.params["model"] == "smoke"
    assert run.data.params["seed"] == "42"
    assert run.data.metrics["precision_at_k"] == pytest.approx(0.5)
    assert run.data.tags["phase"] == "0"
    assert run.info.status == "FINISHED"


@pytest.mark.integration
@requires_server
def test_experiment_is_reused_not_duplicated():
    """Calling start_tracking twice must not create a second experiment."""
    _, first = start_tracking("graphguard-tests")
    _, second = start_tracking("graphguard-tests")
    assert first == second
