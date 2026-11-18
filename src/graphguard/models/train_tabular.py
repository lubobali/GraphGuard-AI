"""Train the tabular baseline and score it on validation.

Scored through the same `evaluate()` the dumb baselines went through, on the
same frozen split, so the comparison is apples to apples. Validation only --
contract rule 4 keeps the test window sealed.
"""

from __future__ import annotations

import time

import numpy as np

from graphguard.analysis.patterns import parse_patterns
from graphguard.config import PATTERNS_FILE, SEED, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.dataset import attach_pattern_ids, frozen_boundaries
from graphguard.evaluation.evaluate import DEFAULT_K_VALUES, evaluate
from graphguard.evaluation.split import truncate_tail
from graphguard.models.pipeline import features_for_split
from graphguard.models.tabular import (
    FEATURE_COLUMNS,
    build_matrix,
    fit_category_maps,
    fit_xgboost,
    predict_scores,
)
from graphguard.tracking import log_run, start_tracking


def _flatten(result: dict) -> dict[str, float]:
    flat = {
        "pr_auc": result["pr_auc"],
        "base_rate": result["base_rate"],
        "n_rows": float(result["n_rows"]),
        "n_positives": float(result["n_positives"]),
    }
    for k, v in result["precision_at_k"].items():
        flat[f"precision_at_{k}"] = v
        flat[f"lift_at_{k}"] = result["lift_at_k"][k]
    for k, p in result.get("pattern", {}).items():
        flat[f"pattern_recall_at_{k}"] = p["recall"]
        flat[f"pattern_hit_rate_at_{k}"] = p["hit_rate"]
    return flat


# Features that separate the classes almost perfectly for reasons that look
# like properties of IBM's generator rather than properties of laundering.
# See FINDING-005 and FINDING-006. The model is trained twice, with and
# without them, and both numbers are reported.
ARTIFACT_FEATURES = ("payment_format_code", "is_cross_currency", "is_self_transfer")


def main() -> int:
    t0 = time.time()
    boundaries = frozen_boundaries()

    base = truncate_tail(load_transactions(TRANSACTIONS_FILE))
    base = attach_pattern_ids(base, parse_patterns(PATTERNS_FILE))

    print("building features...")
    train_df = features_for_split(base, "train", boundaries)
    val_df = features_for_split(base, "validation", boundaries)
    print(f"  train {train_df.height:,} rows   validation {val_df.height:,} rows")
    print(f"  {time.time() - t0:.1f}s")

    maps = fit_category_maps(train_df)
    X_train, y_train = build_matrix(train_df, maps)
    X_val, y_val = build_matrix(val_df, maps)

    print(f"training xgboost on {X_train.height:,} x {len(FEATURE_COLUMNS)}...")
    t1 = time.time()
    model = fit_xgboost(X_train, y_train, seed=SEED)
    train_seconds = time.time() - t1
    print(f"  {train_seconds:.1f}s")

    scores = predict_scores(model, X_val)
    result = evaluate(
        y_val.to_numpy(),
        scores,
        k_values=DEFAULT_K_VALUES,
        pattern_ids=val_df["pattern_id"].to_numpy(),
        amounts=val_df["amount_paid"].to_numpy(),
    )

    client, experiment_id = start_tracking()
    log_run(
        experiment_id,
        params={
            "model": "xgboost",
            "split": "validation",
            "seed": str(SEED),
            "kind": "tabular",
            "n_features": str(len(FEATURE_COLUMNS)),
        },
        metrics={**_flatten(result), "train_seconds": train_seconds},
        tags={"phase": "3"},
    )

    print("\n--- xgboost on validation ---")
    print(f"  PR-AUC {result['pr_auc']:.5f}   base rate {result['base_rate']:.5%}")
    for k in DEFAULT_K_VALUES:
        p = result["precision_at_k"][k]
        pat = result["pattern"][k]
        print(
            f"  k={k:<6} precision {p:8.5f}  lift {result['lift_at_k'][k]:7.2f}x"
            f"   rings {pat['n_caught']:>3}/{pat['n_patterns']}"
            f"   hit {pat['hit_rate']:6.2%}"
        )

    print("\n--- top features by gain ---")
    gains = model.get_booster().get_score(importance_type="gain")
    named = sorted(
        ((FEATURE_COLUMNS[int(k[1:])], v) for k, v in gains.items()),
        key=lambda kv: -kv[1],
    )
    total = sum(v for _, v in named)
    for name, gain in named[:10]:
        print(f"  {name:<34}{gain / total:7.2%}")

    # --- ablation: the same model without the suspected artifacts ----------
    keep = [c for c in FEATURE_COLUMNS if c not in ARTIFACT_FEATURES]
    print(f"\n--- retraining without {', '.join(ARTIFACT_FEATURES)} ---")
    model_clean = fit_xgboost(X_train.select(keep), y_train, seed=SEED)
    scores_clean = predict_scores(model_clean, X_val.select(keep))
    clean = evaluate(
        y_val.to_numpy(),
        scores_clean,
        k_values=DEFAULT_K_VALUES,
        pattern_ids=val_df["pattern_id"].to_numpy(),
        amounts=val_df["amount_paid"].to_numpy(),
    )

    log_run(
        experiment_id,
        params={
            "model": "xgboost_no_artifacts",
            "split": "validation",
            "seed": str(SEED),
            "kind": "tabular",
            "n_features": str(len(keep)),
            "excluded": ",".join(ARTIFACT_FEATURES),
        },
        metrics=_flatten(clean),
        tags={"phase": "3", "ablation": "true"},
    )

    print(f"  PR-AUC {clean['pr_auc']:.5f}   (with artifacts: {result['pr_auc']:.5f})")
    for k in DEFAULT_K_VALUES:
        print(
            f"  k={k:<6} precision {clean['precision_at_k'][k]:8.5f}"
            f"   (with: {result['precision_at_k'][k]:8.5f})"
            f"   rings {clean['pattern'][k]['n_caught']:>3}/{clean['pattern'][k]['n_patterns']}"
            f"   (with: {result['pattern'][k]['n_caught']:>3})"
        )

    np.save("/tmp/graphguard_val_scores.npy", scores)
    print(f"\ntotal {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
