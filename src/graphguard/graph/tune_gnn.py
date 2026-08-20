"""Optuna search for the GNN, same budget the tabular baseline received.

PLAN.md: "Tuned with Optuna, same as the baseline, so neither model got a
luckier search." XGBoost had 20 trials, so the GNN gets 20 trials. Declaring a
winner before that would be the same rigged comparison this project exists to
avoid, just rigged the other way.

Trials are cheaper than the final run (fewer epochs, smaller per-day sample) so
the search fits in a sensible wall-clock. The final model is then retrained at
full settings on the winning parameters.
"""

from __future__ import annotations

import datetime as dt
import time

import optuna
import polars as pl
import torch

from graphguard.analysis.patterns import parse_patterns
from graphguard.config import PATTERNS_FILE, SEED, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.dataset import attach_pattern_ids, frozen_boundaries
from graphguard.evaluation.metrics import pr_auc
from graphguard.evaluation.split import truncate_tail
from graphguard.features.basic import build_basic_features
from graphguard.graph.run_gnn import _days_between, _parity_features
from graphguard.graph.train import make_model, run_epoch
from graphguard.tracking import log_run, start_tracking

N_TRIALS = 20
TRIAL_EPOCHS = 3
TRIAL_ROWS_PER_DAY = 120_000


def main() -> int:
    t0 = time.time()
    train_end, val_end = frozen_boundaries()

    base = attach_pattern_ids(
        truncate_tail(load_transactions(TRANSACTIONS_FILE)), parse_patterns(PATTERNS_FILE)
    )
    frame = build_basic_features(base)

    train_targets = frame.filter(pl.col("timestamp") < train_end)
    val_targets = frame.filter((pl.col("timestamp") >= train_end) & (pl.col("timestamp") < val_end))
    train_days = _days_between(dt.datetime(2022, 9, 1), train_end)
    val_days = _days_between(train_end, val_end)

    edge_columns, train_targets, val_targets = _parity_features(
        train_targets, val_targets, train_end, val_end
    )

    counts = (
        frame.filter(pl.col("timestamp") < train_end)
        .select(pl.len().alias("n"), pl.col("is_laundering").sum().alias("pos"))
        .collect()
    )
    n, pos = int(counts["n"][0]), int(counts["pos"][0])

    _, experiment_id = start_tracking()
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial) -> float:
        params = {
            "hidden": trial.suggest_categorical("hidden", [32, 64, 128]),
            "dropout": trial.suggest_float("dropout", 0.0, 0.5),
            "lr": trial.suggest_float("lr", 1e-4, 3e-2, log=True),
            # pos_weight is searched rather than fixed: 1326 is the exact class
            # ratio, but an extreme weight destabilises gradient descent in a
            # way it does not destabilise a tree.
            "pos_weight": trial.suggest_float("pos_weight", 1.0, (n - pos) / pos, log=True),
            "use_graph": trial.suggest_categorical("use_graph", [True, False]),
        }
        started = time.time()

        model = make_model(
            hidden=params["hidden"],
            dropout=params["dropout"],
            seed=SEED,
            edge_dim=len(edge_columns),
            use_graph=params["use_graph"],
        )
        opt = torch.optim.Adam(model.parameters(), lr=params["lr"])

        for _ in range(TRIAL_EPOCHS):
            run_epoch(
                model,
                frame,
                train_targets,
                train_days,
                optimizer=opt,
                pos_weight=params["pos_weight"],
                max_rows_per_day=TRIAL_ROWS_PER_DAY,
                seed=SEED,
                edge_columns=edge_columns,
            )

        _, scores, labels = run_epoch(
            model, frame, val_targets, val_days, edge_columns=edge_columns
        )
        score = pr_auc(labels.astype(int), scores)

        log_run(
            experiment_id,
            params={
                "model": "gnn_tuning",
                "kind": "trial",
                **{k: str(v) for k, v in params.items()},
            },
            metrics={"pr_auc": score, "seconds": time.time() - started},
            tags={"phase": "4", "trial": "true"},
        )
        print(f"  pr_auc {score:.5f}  ({time.time() - started:.0f}s)  {params}", flush=True)
        return score

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=N_TRIALS, show_progress_bar=False)

    print(f"\nbest pr_auc {study.best_value:.5f}")
    print(f"best params {study.best_params}")
    print(f"total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
