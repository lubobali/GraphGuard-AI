"""Optuna search for the tabular baseline, every trial logged to MLflow.

Tuned on the **artifact-free** feature set. That is the model this project
quotes (FINDING-006) and the one Phase 4's GNN is compared against, so it is
the one that deserves the search budget.

Validation only. The test window stays sealed.
"""

from __future__ import annotations

import time

from graphguard.analysis.patterns import parse_patterns
from graphguard.config import PATTERNS_FILE, SEED, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.dataset import attach_pattern_ids, frozen_boundaries
from graphguard.evaluation.evaluate import DEFAULT_K_VALUES, evaluate
from graphguard.evaluation.metrics import pr_auc
from graphguard.evaluation.split import truncate_tail
from graphguard.models.pipeline import features_for_split
from graphguard.models.search import SEARCH_SPACE, tune
from graphguard.models.tabular import (
    FEATURE_COLUMNS,
    build_matrix,
    fit_category_maps,
    fit_xgboost,
    predict_scores,
)
from graphguard.models.train_tabular import ARTIFACT_FEATURES, _flatten
from graphguard.tracking import log_run, start_tracking

N_TRIALS = 20
N_ESTIMATORS = 300  # same for every trial and for the final fit


def main() -> int:
    t0 = time.time()
    boundaries = frozen_boundaries()

    base = attach_pattern_ids(
        truncate_tail(load_transactions(TRANSACTIONS_FILE)), parse_patterns(PATTERNS_FILE)
    )
    train_df = features_for_split(base, "train", boundaries)
    val_df = features_for_split(base, "validation", boundaries)

    maps = fit_category_maps(train_df)
    X_train, y_train = build_matrix(train_df, maps)
    X_val, y_val = build_matrix(val_df, maps)

    keep = [c for c in FEATURE_COLUMNS if c not in ARTIFACT_FEATURES]
    X_train, X_val = X_train.select(keep), X_val.select(keep)
    y_val_np = y_val.to_numpy()

    client, experiment_id = start_tracking()
    print(f"tuning on {len(keep)} artifact-free features, {N_TRIALS} trials")
    print(f"setup {time.time() - t0:.1f}s\n", flush=True)

    def objective(params: dict) -> float:
        started = time.time()
        model = fit_xgboost(X_train, y_train, params, seed=SEED, n_estimators=N_ESTIMATORS)
        score = pr_auc(y_val_np, predict_scores(model, X_val))

        log_run(
            experiment_id,
            params={
                "model": "xgboost_tuning",
                "kind": "trial",
                **{k: str(v) for k, v in params.items()},
            },
            metrics={"pr_auc": score, "fit_seconds": time.time() - started},
            tags={"phase": "3", "trial": "true"},
        )
        print(f"  pr_auc {score:.5f}  ({time.time() - started:.0f}s)  {params}", flush=True)
        return score

    study = tune(objective, n_trials=N_TRIALS, seed=SEED)

    print(f"\nbest pr_auc {study['best_value']:.5f}")
    print(f"best params {study['best_params']}\n", flush=True)

    # Final model on the best parameters, full evaluation.
    model = fit_xgboost(
        X_train, y_train, study["best_params"], seed=SEED, n_estimators=N_ESTIMATORS
    )
    result = evaluate(
        y_val_np,
        predict_scores(model, X_val),
        k_values=DEFAULT_K_VALUES,
        pattern_ids=val_df["pattern_id"].to_numpy(),
        amounts=val_df["amount_paid"].to_numpy(),
    )

    log_run(
        experiment_id,
        params={
            "model": "xgboost_tuned_no_artifacts",
            "split": "validation",
            "kind": "tabular",
            "seed": str(SEED),
            "n_features": str(len(keep)),
            "n_trials": str(N_TRIALS),
            "search_space": ",".join(sorted(SEARCH_SPACE)),
            **{f"best_{k}": str(v) for k, v in study["best_params"].items()},
        },
        metrics=_flatten(result),
        tags={"phase": "3", "tuned": "true"},
    )

    print("--- tuned xgboost, artifact-free, on validation ---")
    print(f"  PR-AUC {result['pr_auc']:.5f}")
    for k in DEFAULT_K_VALUES:
        pat = result["pattern"][k]
        print(
            f"  k={k:<6} precision {result['precision_at_k'][k]:8.5f}"
            f"  lift {result['lift_at_k'][k]:7.2f}x"
            f"   rings {pat['n_caught']:>3}/{pat['n_patterns']}"
        )
    print(f"\ntotal {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
