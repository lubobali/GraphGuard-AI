"""Train the production model, save it, and fill the online store.

This is the batch job a deployment runs: produce the artifact the service loads
and the state it reads. Kept as one script so the two cannot fall out of step --
a store filled from one feature definition and a model trained on another is the
skew this project spends most of its guards preventing.
"""

from __future__ import annotations

import time
from pathlib import Path

from graphguard.analysis.patterns import parse_patterns
from graphguard.config import PATTERNS_FILE, REPO_ROOT, SEED, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.dataset import attach_pattern_ids, frozen_boundaries
from graphguard.evaluation.split import truncate_tail
from graphguard.models.pipeline import features_for_split
from graphguard.models.tabular import (
    FEATURE_COLUMNS,
    build_matrix,
    fit_category_maps,
    fit_xgboost,
)
from graphguard.models.train_tabular import ARTIFACT_FEATURES
from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.online_features import build_account_states
from graphguard.serving.store import RedisFeatureStore

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
    train_end, val_end = frozen_boundaries()

    base = attach_pattern_ids(
        truncate_tail(load_transactions(TRANSACTIONS_FILE)), parse_patterns(PATTERNS_FILE)
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

    # Fill the online store as of the end of training -- the state a service
    # deployed at that moment would hold.
    t = time.time()
    states = build_account_states(base, as_of=train_end)
    store = RedisFeatureStore()
    store.clear()
    store.put_many(list(states.values()))
    print(f"online store filled: {len(states):,} accounts ({time.time() - t:.0f}s)")

    print(f"total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
