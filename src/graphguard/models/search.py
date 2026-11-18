"""Hyperparameter search with Optuna.

Two reasons this exists rather than a hand-picked configuration:

**Fairness.** Phase 4's GNN gets the same treatment -- same sampler, same trial
budget, same objective. Neither model then wins because its settings happened
to be guessed better, which is a real and common way comparisons go wrong.

**Reproducibility.** Every trial is recorded with its parameters and its score.
A search nobody can rerun is a notebook full of guesses, and "the tuned model
scored X" is unverifiable.

The search runs on **validation only**. The test window stays sealed
(contract rule 4).
"""

from __future__ import annotations

from typing import Callable

import optuna

# Declared as data rather than inline calls, so the search space can be
# asserted in tests and printed into the run record.
SEARCH_SPACE: dict[str, dict] = {
    "max_depth": {"type": "int", "low": 3, "high": 10},
    "learning_rate": {"type": "float", "low": 0.01, "high": 0.3, "log": True},
    "subsample": {"type": "float", "low": 0.5, "high": 1.0},
    "colsample_bytree": {"type": "float", "low": 0.5, "high": 1.0},
    "min_child_weight": {"type": "float", "low": 0.5, "high": 20.0, "log": True},
    "reg_lambda": {"type": "float", "low": 0.5, "high": 20.0, "log": True},
}


def suggest_params(trial) -> dict:
    """Ask the trial for one point in the search space."""
    params = {}
    for name, spec in SEARCH_SPACE.items():
        if spec["type"] == "int":
            params[name] = trial.suggest_int(name, spec["low"], spec["high"])
        else:
            params[name] = trial.suggest_float(
                name, spec["low"], spec["high"], log=spec.get("log", False)
            )
    return params


def tune(
    objective: Callable[[dict], float],
    *,
    n_trials: int,
    seed: int,
) -> dict:
    """Run the search. `objective` takes params and returns a score to maximise."""
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)

    records: list[dict] = []

    def _wrapped(trial):
        params = suggest_params(trial)
        value = objective(params)
        records.append({"number": trial.number, "params": params, "value": value})
        return value

    study.optimize(_wrapped, n_trials=n_trials, show_progress_bar=False)

    return {
        "best_params": study.best_params,
        "best_value": study.best_value,
        "trials": records,
    }
