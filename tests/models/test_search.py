"""The hyperparameter search must be reproducible and must not touch test.

An unreproducible search is not a result. The same seed and the same data must
propose the same trials, or "the tuned model scored X" cannot be checked
tomorrow.
"""

import pytest

from graphguard.models.search import SEARCH_SPACE, suggest_params, tune


class _FakeTrial:
    """Records what was asked for, returns the low end of each range."""

    def __init__(self):
        self.asked: list[str] = []

    def suggest_int(self, name, low, high, **kw):
        self.asked.append(name)
        return low

    def suggest_float(self, name, low, high, **kw):
        self.asked.append(name)
        return low


@pytest.mark.unit
def test_every_declared_parameter_is_suggested():
    trial = _FakeTrial()
    params = suggest_params(trial)
    assert set(trial.asked) == set(SEARCH_SPACE)
    assert set(params) == set(SEARCH_SPACE)


@pytest.mark.unit
def test_search_space_ranges_are_sane():
    """A silently inverted range would make the search a no-op."""
    for name, spec in SEARCH_SPACE.items():
        assert spec["low"] < spec["high"], name


@pytest.mark.unit
def test_tune_is_reproducible_for_a_fixed_seed():
    """Same seed, same objective -> same best parameters."""
    calls = {"n": 0}

    def objective(params):
        calls["n"] += 1
        # deterministic, so any difference comes from the sampler
        return -abs(params["max_depth"] - 5)

    first = tune(objective, n_trials=8, seed=1)
    second = tune(objective, n_trials=8, seed=1)
    assert first["best_params"] == second["best_params"]
    assert calls["n"] == 16


@pytest.mark.unit
def test_tune_reports_the_best_value_it_found():
    def objective(params):
        return float(params["max_depth"])

    out = tune(objective, n_trials=6, seed=3)
    assert out["best_value"] == max(t["value"] for t in out["trials"])


@pytest.mark.unit
def test_every_trial_is_recorded():
    out = tune(lambda p: 1.0, n_trials=5, seed=2)
    assert len(out["trials"]) == 5
    assert all("params" in t and "value" in t for t in out["trials"])
