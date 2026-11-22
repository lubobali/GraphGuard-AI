"""Is `weekday` a simulator artifact? (S7.4 -> FINDING-018)

    python -m graphguard.analysis.calendar_features

Found while explaining alerts: weekday is a top-3 reason for most of the top 5,000. The
training window holds each weekday exactly once (2022-09-01 Thu .. 09-06 Tue), the simulator
launders ~400 transactions a day whatever the day's volume, and validation's Wednesday never
occurs in training. This retrains the production recipe (same features, params, seed, trees,
window) with and without the calendar features and scores each on validation through
`evaluate()`. The run WITH them must reproduce the production numbers, or the comparison is
void. Measures only: the production model is not changed here.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

from graphguard.config import REPO_ROOT, SEED

VARIANTS = {
    "production (with weekday + hour)": (),
    "without weekday": ("weekday",),
    "without weekday and hour": ("weekday", "hour"),
}


def daily_rates(silver: pl.DataFrame, train_end) -> list[dict]:
    return (
        silver.with_columns(
            pl.when(pl.col("timestamp") < train_end)
            .then(pl.lit("train"))
            .otherwise(pl.lit("validation"))
            .alias("split"),
            pl.col("timestamp").dt.date().alias("day"),
            pl.col("timestamp").dt.strftime("%A").alias("weekday"),
        )
        .group_by("split", "day", "weekday")
        .agg(pl.len().alias("transactions"), pl.col("is_laundering").sum().alias("laundering"))
        .with_columns(
            (pl.col("laundering") / pl.col("transactions") * 1000).round(3).alias("per_1000")
        )  # fmt: skip
        .sort("day", "split")
        .with_columns(pl.col("day").cast(pl.Utf8))
        .to_dicts()
    )


def main(argv: list[str]) -> int:
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.evaluation.evaluate import evaluate
    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.tables import SILVER_TX, _scan, scan_silver_with_ring_ids
    from graphguard.models.pipeline import features_for_split
    from graphguard.models.tabular import (
        FEATURE_COLUMNS,
        build_matrix,
        fit_category_maps,
        fit_xgboost,
    )
    from graphguard.models.train_tabular import ARTIFACT_FEATURES
    from graphguard.serving.build_artifacts import BEST_PARAMS

    b = frozen_boundaries()
    cat = open_catalog("reader")
    base = scan_silver_with_ring_ids(cat)
    train_df = features_for_split(base, "train", b)
    val_df = features_for_split(base, "validation", b)
    maps = fit_category_maps(train_df)
    X_tr, y_tr = build_matrix(train_df, maps)
    X_va, y_va = build_matrix(val_df, maps)
    pids = val_df["pattern_id"].to_numpy()
    keep = tuple(c for c in FEATURE_COLUMNS if c not in ARTIFACT_FEATURES)

    out = {"daily": daily_rates(
        _scan(cat, SILVER_TX).select("timestamp", "is_laundering").collect(), b[0]),
        "variants": {}}  # fmt: skip
    for name, drop in VARIANTS.items():
        cols = [c for c in keep if c not in drop]
        model = fit_xgboost(X_tr.select(cols), y_tr, BEST_PARAMS, seed=SEED, n_estimators=300)
        scores = model.predict_proba(X_va.select(cols).cast(pl.Float32).to_numpy())[:, 1]
        r = evaluate(y_va.to_numpy(), scores, k_values=(211, 1_000, 5_000), pattern_ids=pids)
        out["variants"][name] = {
            "features": len(cols),
            "pr_auc": round(r["pr_auc"], 5),
            "caught_at_k": {k: round(v) for k, v in r["caught_at_k"].items()},
            "rings_caught_at_k": {k: v["n_caught"] for k, v in r["pattern"].items()},
            "rings_touched_at_k": {
                k: round(v["hit_rate"] * v["n_patterns"]) for k, v in r["pattern"].items()
            },  # fmt: skip
        }
        print(name, json.dumps(out["variants"][name]), flush=True)
        del model, scores
    prod = out["variants"]["production (with weekday + hour)"]["pr_auc"]
    out["reproduces_production"] = bool(np.isclose(prod, 0.28155, atol=5e-6))
    (REPO_ROOT / "docs" / "analysis" / "finding-018-calendar.json").write_text(
        json.dumps(out, indent=2) + "\n"
    )
    return 0 if out["reproduces_production"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
