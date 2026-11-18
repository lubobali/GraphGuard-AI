"""Feature matrix and XGBoost model for the tabular baseline.

The baseline gets a real effort. PLAN.md is explicit: "A weak baseline makes
the GNN result worthless." So it receives the hand-built graph features too --
counterparties so far, velocity, in/out ratio -- and a proper hyperparameter
search. If the GNN wins later, it will have had to earn it.

Category encodings are fitted on the **training window only**. Fitting them on
all the data would let a category that appears only in validation influence the
mapping. Small, but it is a leak, and it is the invisible kind.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import xgboost as xgb

# A category never seen in training. Given its own code rather than folded into
# an existing one, so the model can learn "unfamiliar" as a signal in itself.
UNSEEN_CATEGORY = -1

CATEGORICAL_SOURCES = ("payment_format", "payment_currency")

FEATURE_COLUMNS: tuple[str, ...] = (
    # row-level
    "hour",
    "weekday",
    "log_amount",
    "amount_ratio",
    "is_cross_currency",
    "is_self_transfer",
    "is_same_bank",
    "payment_format_code",
    "payment_currency_code",
    # point-in-time graph history
    "sender_n_sent_before",
    "sender_amount_sent_before",
    "sender_distinct_out_before",
    "sender_sent_last_24h",
    "sender_seconds_since_last_send",
    "receiver_n_received_before",
    "receiver_amount_received_before",
    "receiver_distinct_in_before",
    "in_out_ratio_before",
)

LABEL = "is_laundering"


def fit_category_maps(train_df: pl.DataFrame) -> dict[str, dict[str, int]]:
    """Learn category -> code mappings from the training window only."""
    maps: dict[str, dict[str, int]] = {}
    for col in CATEGORICAL_SOURCES:
        values = sorted(train_df[col].unique().drop_nulls().to_list())
        maps[col] = {v: i for i, v in enumerate(values)}
    return maps


def build_matrix(
    df: pl.DataFrame, category_maps: dict[str, dict[str, int]]
) -> tuple[pl.DataFrame, pl.Series]:
    """Return (X, y). X holds exactly FEATURE_COLUMNS, in that order."""
    encoded = df.with_columns(
        [
            pl.col(col)
            .replace_strict(category_maps[col], default=UNSEEN_CATEGORY, return_dtype=pl.Int32)
            .alias(f"{col}_code")
            for col in CATEGORICAL_SOURCES
        ]
    )

    missing = [c for c in FEATURE_COLUMNS if c not in encoded.columns]
    if missing:
        raise KeyError(f"feature matrix is missing columns: {missing}")

    # Float32 halves the memory of a 3M x 18 matrix and costs nothing in
    # accuracy here. Nulls become NaN, which XGBoost treats as "missing" and
    # learns a default direction for -- that is wanted: "this account has never
    # sent before" is information, not absence of it.
    X = encoded.select(FEATURE_COLUMNS).cast(pl.Float32)
    y = encoded[LABEL] if LABEL in encoded.columns else pl.Series(LABEL, [], dtype=pl.Int8)
    return X, y


def fit_xgboost(
    X: pl.DataFrame,
    y: pl.Series,
    params: dict | None = None,
    *,
    seed: int,
    n_estimators: int = 400,
) -> xgb.XGBClassifier:
    """Train the classifier.

    The imbalance is handled with scale_pos_weight rather than resampling: at
    1 positive per ~1000 rows, undersampling the negatives would throw away
    most of the data, and oversampling the positives would duplicate 2,296 rows
    thousands of times.
    """
    defaults = {
        "max_depth": 6,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 1.0,
        "reg_lambda": 1.0,
    }
    defaults.update(params or {})

    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    scale_pos_weight = (n_neg / n_pos) if n_pos else 1.0

    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        objective="binary:logistic",
        eval_metric="aucpr",
        tree_method="hist",
        scale_pos_weight=scale_pos_weight,
        random_state=seed,
        n_jobs=4,
        **defaults,
    )
    model.fit(X.to_numpy(), y.to_numpy())
    return model


def predict_scores(model: xgb.XGBClassifier, X: pl.DataFrame) -> np.ndarray:
    """Ranking scores. Only the order matters to evaluate()."""
    return model.predict_proba(X.to_numpy())[:, 1]
