"""MLflow tracking.

Every run is recorded, or a comparison between two models is an anecdote
rather than a result. This module is the only place the tracking server is
addressed, so the URI is configured once and not scattered through the code.
"""

from __future__ import annotations

import os

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")  # MLflow 3 prints a hint on import

import mlflow  # noqa: E402
from mlflow.tracking import MlflowClient  # noqa: E402

from graphguard.config import MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI, secrets_dir  # noqa: E402


def use_login() -> str | None:
    """Log in to MLflow as this caller (S5b.7: the server refuses anonymous requests).

    `GRAPHGUARD_MLFLOW_USER` names the login (default `research`, the root-run scripts
    and tests); its file `mlflow-<user>.env` comes from the secrets directory -- for a
    job, only its own, handed in by systemd. Credentials already in the environment win.
    Returns the user, or None when no login file exists (a server without auth)."""
    if os.environ.get("MLFLOW_TRACKING_USERNAME"):
        return os.environ["MLFLOW_TRACKING_USERNAME"]
    user = os.environ.get("GRAPHGUARD_MLFLOW_USER", "research")
    path = secrets_dir() / f"mlflow-{user}.env"
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        if line.startswith(("MLFLOW_TRACKING_USERNAME=", "MLFLOW_TRACKING_PASSWORD=")):
            key, value = line.split("=", 1)
            os.environ[key] = value.strip()
    return user


def start_tracking(experiment: str | None = None) -> tuple[MlflowClient, str]:
    """Point MLflow at the tracking server and return (client, experiment_id).

    The experiment is created on first use and reused afterwards, so calling
    this repeatedly does not scatter runs across duplicate experiments.
    """
    name = experiment or MLFLOW_EXPERIMENT
    use_login()
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)

    existing = client.get_experiment_by_name(name)
    experiment_id = existing.experiment_id if existing else client.create_experiment(name)

    return client, experiment_id


def log_run(
    experiment_id: str,
    *,
    params: dict[str, str] | None = None,
    metrics: dict[str, float] | None = None,
    tags: dict[str, str] | None = None,
) -> str:
    """Record one run and return its id."""
    with mlflow.start_run(experiment_id=experiment_id) as run:
        if params:
            mlflow.log_params(params)
        if metrics:
            mlflow.log_metrics(metrics)
        if tags:
            mlflow.set_tags(tags)
        return run.info.run_id
