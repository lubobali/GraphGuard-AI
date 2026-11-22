"""Train the production model from the lakehouse and save it.

Since S5.6a this no longer fills the online store. Training and loading are
separate jobs that share one definition instead of one script:

    just lakehouse-build   # CSV -> bronze -> silver -> gold
    just build-artifacts   # train from silver; log which snapshots it read
    just store-load        # fill Redis from gold, no retraining

Skew is still prevented by construction: gold is written by
`account_states_frame`, the same function the store used to be filled with, and
the parity tests assert it. What changed is that refilling Redis no longer
means retraining, and every model now names the exact table snapshots it saw.
"""

from __future__ import annotations

import time
from pathlib import Path

from mlflow.tracking import MlflowClient

from graphguard.config import REPO_ROOT, SEED
from graphguard.evaluation.dataset import frozen_boundaries
from graphguard.lakehouse.catalog import open_catalog
from graphguard.lakehouse.lineage import training_lineage
from graphguard.lakehouse.lineage_events import lineage_run
from graphguard.lakehouse.tables import GOLD_RINGS, SILVER_TX, scan_silver_with_ring_ids
from graphguard.models.pipeline import features_for_split
from graphguard.models.tabular import (
    FEATURE_COLUMNS,
    build_matrix,
    fit_category_maps,
    fit_xgboost,
)
from graphguard.models.train_tabular import ARTIFACT_FEATURES
from graphguard.serving.model_bundle import ModelBundle
from graphguard.tracking import log_run, start_tracking

# Tuned in Phase 3 on validation.
BEST_PARAMS = {
    "max_depth": 10,
    "learning_rate": 0.07761956691643652,
    "subsample": 0.7051730042593098,
    "colsample_bytree": 0.6757942904913252,
    "min_child_weight": 6.248413484212628,
    "reg_lambda": 0.5077554481105739,
}

BUNDLE_DIR = REPO_ROOT / "models" / "production"


def main() -> int:
    t0 = time.time()
    catalog = open_catalog("trainer")
    lineage = training_lineage(catalog)  # recorded BEFORE reading, so it names what is read
    with lineage_run("build-artifacts") as run:
        # Only what training reads. The other tables' snapshot ids are context,
        # kept as MLflow params; trainer cannot even read bronze's rows.
        run.read(SILVER_TX, lineage[f"snapshot.{SILVER_TX}"])
        bundle_path = str(Path(BUNDLE_DIR).relative_to(REPO_ROOT))
        run.wrote(bundle_path, lineage["git_sha"], namespace="file://graphguard")
        run_id = _train(catalog, lineage, t0)
    # After the block, so the record includes the COMPLETE event.
    MlflowClient().log_dict(run_id, {"events": run.events}, "lineage/openlineage.json")
    print(f"lineage logged to MLflow run {run_id} (params + OpenLineage events)")
    print("the online store is NOT refilled here: run `just store-load`")
    print(f"total {time.time() - t0:.0f}s")
    return 0


def _train(catalog, lineage: dict, t0: float) -> str:
    """Train, save the bundle, log the run to MLflow; returns the MLflow run id."""
    train_end, val_end = frozen_boundaries()
    # Silver holds train + validation with the tail already removed; the test
    # window is in `sealed`, which training never opens.
    # In source order, so features match the CSV path bit for bit (S5.6a).
    # Ring ids from gold.rings (S7.2), no longer the raw ring list -- a slow test holds
    # the two equal on all of silver.
    base = scan_silver_with_ring_ids(
        catalog, lineage[f"snapshot.{SILVER_TX}"], lineage[f"snapshot.{GOLD_RINGS}"]
    )

    train_df = features_for_split(base, "train", boundaries=(train_end, val_end))
    keep = tuple(c for c in FEATURE_COLUMNS if c not in ARTIFACT_FEATURES)

    maps = fit_category_maps(train_df)
    X_train, y_train = build_matrix(train_df, maps)
    model = fit_xgboost(X_train.select(keep), y_train, BEST_PARAMS, seed=SEED, n_estimators=300)
    print(f"model trained on {X_train.height:,} rows ({time.time() - t0:.0f}s)", flush=True)

    bundle = ModelBundle(
        model=model,
        feature_columns=keep,
        category_maps=maps,
        trained_on=f"train window ending {train_end.isoformat()}",
    )
    bundle.save(BUNDLE_DIR)
    print(f"bundle saved to {Path(BUNDLE_DIR).relative_to(REPO_ROOT)}")

    _, experiment_id = start_tracking()
    run_id = log_run(
        experiment_id,
        params={**{k: str(v) for k, v in lineage.items()}, "n_train_rows": str(X_train.height)},
        tags={"job": "build-artifacts", "bundle": str(Path(BUNDLE_DIR).relative_to(REPO_ROOT))},
    )
    return run_id


if __name__ == "__main__":
    raise SystemExit(main())
