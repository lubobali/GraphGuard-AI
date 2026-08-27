"""Measure what a refresh interval costs, so the policy is a number not a guess.

The model is trained once on exact point-in-time features. It is then scored
three ways on the same validation window:

- **exact** -- features computed at the transaction's own instant. This is the
  training path, and the ceiling.
- **refresh every N hours** -- features read from the most recent snapshot at or
  before the transaction, which is what production actually does.

The gap between them is the cost of not refreshing continuously, and the
refresh interval the system should run at is whichever one keeps that gap
acceptable.
"""

from __future__ import annotations

import datetime as dt
import time

import polars as pl

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
from graphguard.models.train_tabular import ARTIFACT_FEATURES
from graphguard.serving.online_features import AccountState, build_account_states, to_model_row
from graphguard.serving.staleness import materialisation_points, snapshot_for
from graphguard.tracking import log_run, start_tracking

# Tuned in Phase 3.
BEST_PARAMS = {
    "max_depth": 10,
    "learning_rate": 0.07761956691643652,
    "subsample": 0.7051730042593098,
    "colsample_bytree": 0.6757942904913252,
    "min_child_weight": 6.248413484212628,
    "reg_lambda": 0.5077554481105739,
}

REFRESH_INTERVALS = (dt.timedelta(hours=6), dt.timedelta(hours=24))


def _served_features(
    frame: pl.LazyFrame,
    val_df: pl.DataFrame,
    interval: dt.timedelta,
    currency_map: dict[str, int],
) -> pl.DataFrame:
    """Rebuild validation features the way serving would, at this interval."""
    start, end = val_df["timestamp"].min(), val_df["timestamp"].max()
    points = materialisation_points(start, end + interval, interval)

    rows: list[dict] = []
    for point in points:
        states = build_account_states(frame, as_of=point)
        due = val_df.filter(
            (pl.col("timestamp") >= point) & (pl.col("timestamp") < point + interval)
        )
        for tx in due.iter_rows(named=True):
            sender = states.get(tx["from_account"]) or AccountState.cold(tx["from_account"])
            receiver = states.get(tx["to_account"]) or AccountState.cold(tx["to_account"])
            rows.append(
                to_model_row(
                    sender=sender,
                    receiver=receiver,
                    timestamp=tx["timestamp"],
                    amount_paid=tx["amount_paid"],
                    amount_received=tx["amount_received"],
                    from_bank=tx["from_bank"],
                    to_bank=tx["to_bank"],
                    payment_currency_code=currency_map.get(tx["payment_currency"], -1),
                )
                | {"timestamp": tx["timestamp"], "is_laundering": tx["is_laundering"]}
            )

    assert snapshot_for(start, points) is not None
    return pl.DataFrame(rows).sort("timestamp")


def main() -> int:
    t0 = time.time()
    boundaries = frozen_boundaries()
    base = attach_pattern_ids(
        truncate_tail(load_transactions(TRANSACTIONS_FILE)), parse_patterns(PATTERNS_FILE)
    )

    train_df = features_for_split(base, "train", boundaries)
    val_df = features_for_split(base, "validation", boundaries)

    keep = [c for c in FEATURE_COLUMNS if c not in ARTIFACT_FEATURES]
    maps = fit_category_maps(train_df)
    X_train, y_train = build_matrix(train_df, maps)
    model = fit_xgboost(X_train.select(keep), y_train, BEST_PARAMS, seed=SEED, n_estimators=300)
    print(f"model trained ({time.time() - t0:.0f}s)", flush=True)

    y_val = val_df["is_laundering"].to_numpy()
    pattern_ids = val_df["pattern_id"].to_numpy()
    amounts = val_df["amount_paid"].to_numpy()

    results = {}

    X_val, _ = build_matrix(val_df, maps)
    results["exact"] = evaluate(
        y_val,
        predict_scores(model, X_val.select(keep)),
        k_values=DEFAULT_K_VALUES,
        pattern_ids=pattern_ids,
        amounts=amounts,
    )

    for interval in REFRESH_INTERVALS:
        t = time.time()
        served = _served_features(base, val_df, interval, maps["payment_currency"])

        # Refusing to zero-fill is the point. A feature the serving path forgot
        # to carry is a missing feature, not staleness, and held at zero it
        # looks exactly like staleness in the metric. This check caught that
        # happening: three features were silently zeroed and the result read as
        # an 87% staleness penalty.
        missing = [c for c in keep if c not in served.columns]
        if missing:
            raise RuntimeError(
                f"serving path does not produce {missing}. Refusing to zero-fill: "
                "that would be measured as staleness."
            )

        scores = predict_scores(model, served.select(keep).cast(pl.Float32))
        label = f"refresh_{int(interval.total_seconds() // 3600)}h"
        results[label] = evaluate(
            served["is_laundering"].to_numpy(),
            scores,
            k_values=DEFAULT_K_VALUES,
            pattern_ids=pattern_ids,
            amounts=amounts,
        )
        print(f"{label} scored ({time.time() - t:.0f}s)", flush=True)

    print(f"\n{'policy':<14}{'PR-AUC':>10}{'p@1000':>10}{'rings@5000':>13}{'vs exact':>11}")
    exact_pr = results["exact"]["pr_auc"]
    for label, r in results.items():
        rings = r["pattern"][5000]
        delta = "" if label == "exact" else f"{(r['pr_auc'] / exact_pr - 1) * 100:+.1f}%"
        print(
            f"{label:<14}{r['pr_auc']:>10.5f}{r['precision_at_k'][1000]:>10.5f}"
            f"{rings['n_caught']:>9}/{rings['n_patterns']:<4}{delta:>11}"
        )

    _, experiment_id = start_tracking()
    for label, r in results.items():
        log_run(
            experiment_id,
            params={"model": "xgboost", "kind": "staleness", "policy": label},
            metrics={
                "pr_auc": r["pr_auc"],
                **{f"precision_at_{k}": v for k, v in r["precision_at_k"].items()},
            },
            tags={"phase": "5"},
        )

    print(f"\ntotal {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
