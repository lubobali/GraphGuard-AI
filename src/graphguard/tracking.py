"""MLflow tracking.

Every run is recorded, or a comparison between two models is an anecdote
rather than a result. This module is the only place the tracking server is
addressed, so the URI is configured once and not scattered through the code.
"""

from __future__ import annotations

import mlflow
from mlflow.tracking import MlflowClient

from graphguard.config import MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI


def start_tracking(experiment: str | None = None) -> tuple[MlflowClient, str]:
    """Point MLflow at the tracking server and return (client, experiment_id).

    The experiment is created on first use and reused afterwards, so calling
    this repeatedly does not scatter runs across duplicate experiments.
    """
    name = experiment or MLFLOW_EXPERIMENT
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
