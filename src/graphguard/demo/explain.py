"""Exact SHAP for the queue's top alerts (S7.4), from XGBoost's own TreeSHAP.

`pred_contribs=True` gives, per row, one contribution per feature plus a bias term, in
log-odds; they sum exactly to the model's raw margin, and sigmoid(margin) is the score.
No new library: the model that decided is the model that explains.
"""

from __future__ import annotations

import json

import numpy as np
import polars as pl

from graphguard.demo import reasons as R

TOP_N = 20_000  # 4x the slider's maximum k
SUM_FEATURES = ("sender_amount_sent_before", "receiver_amount_received_before")


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def contributions(model, X: np.ndarray, nthread: int = 4) -> tuple[float, np.ndarray]:
    """(base value, n x features contributions) -- log-odds units. Threads change speed
    only (measured identical; 1 thread, the serving setting, took ~90 s for 20,000 rows)."""
    booster = model.get_booster().copy()
    booster.set_param({"nthread": nthread})
    out = booster.predict(xgb_matrix(X), pred_contribs=True)
    return float(out[0, -1]), out[:, :-1].astype(np.float64)


def xgb_matrix(X: np.ndarray):
    import xgboost as xgb

    return xgb.DMatrix(np.asarray(X, dtype=np.float32))


def share_below(reference: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Percent of `reference` strictly below each value (for the mixed-currency sums)."""
    ref = np.sort(reference[~np.isnan(reference)])
    return np.searchsorted(ref, values, side="left") / len(ref) * 100.0


class ExplainError(RuntimeError):
    pass


def explain(tx: pl.DataFrame, feature_names: list[str], bundle) -> pl.DataFrame:
    """`tx`: the demo's queue table (all validation rows). Explains the top TOP_N by rank;
    refuses unless the bundle reproduces every explained stored score exactly."""
    if list(bundle.feature_columns) != list(feature_names):
        raise ExplainError("the bundle's features differ from the stream's feature set")
    # straight from Arrow; a million Python lists cost ~100 s (S7.4)
    all_X = tx["features"].list.to_array(len(feature_names)).to_numpy().astype(np.float64)
    top = tx.with_row_index("_i").filter(pl.col("rank") <= TOP_N).sort("rank")
    X = all_X[top["_i"].to_numpy()].astype(np.float32)

    recomputed = bundle.model.predict_proba(X)[:, 1].astype(np.float64)
    stored = top["score"].to_numpy()
    if not np.array_equal(recomputed, stored):
        bad = int((recomputed != stored).sum())
        raise ExplainError(f"{bad} recomputed scores differ from the stored ones: wrong model?")

    base, contribs = contributions(bundle.model, X)
    margin = base + contribs.sum(axis=1)
    if not np.allclose(sigmoid(margin), stored, atol=1e-5):
        raise ExplainError("contributions do not add up to the stored scores")

    pct = {
        f: share_below(all_X[:, feature_names.index(f)], X[:, feature_names.index(f)])
        for f in SUM_FEATURES
    }
    reasons, groups = [], []
    tx_cols = top.select(
        "amount_paid", "payment_currency", "amount_received", "receiving_currency"
    ).to_dicts()
    for i in range(len(top)):
        c = dict(zip(feature_names, contribs[i].tolist(), strict=True))
        p = {f: float(pct[f][i]) for f in SUM_FEATURES}
        v = dict(zip(feature_names, X[i].astype(np.float64).tolist(), strict=True))
        reasons.append([R.sentence(f, v[f], tx_cols[i], p) for f in R.top_features(c, n=3)])
        groups.append(json.dumps(R.groups(c, v, tx_cols[i], p)))  # S7.13
    return pl.DataFrame(
        {
            "event_id": top["event_id"],
            "base": [base] * len(top),
            "contribs": [row.tolist() for row in contribs],
            "reasons": reasons,
            "groups": groups,
        },
        schema={
            "event_id": pl.Int64,
            "base": pl.Float64,
            "contribs": pl.List(pl.Float64),
            "reasons": pl.List(pl.Utf8),
            "groups": pl.Utf8,
        },
    )
