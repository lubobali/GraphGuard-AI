"""Exact SHAP from XGBoost itself (S7.4): contributions add up to the model's own margin."""

import numpy as np
import pytest
import xgboost as xgb

from graphguard.demo import explain as E

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def model():
    rng = np.random.default_rng(0)
    X = rng.random((2_000, 4)).astype(np.float32)
    X[::7, 2] = np.nan  # missing values, like "never sent before"
    y = (X[:, 0] + rng.random(2_000) * 0.3 > 0.9).astype(int)
    m = xgb.XGBClassifier(n_estimators=30, max_depth=4, scale_pos_weight=50, random_state=0)
    return m.fit(X, y), X


def test_contributions_add_up_to_the_margin(model):
    m, X = model
    base, contribs = E.contributions(m, X[:200])
    margin = m.predict(X[:200], output_margin=True)
    assert np.allclose(base + contribs.sum(axis=1), margin, atol=1e-4)


def test_contributions_explain_the_probability_the_model_gives(model):
    m, X = model
    base, contribs = E.contributions(m, X[:200])
    p = m.predict_proba(X[:200])[:, 1]
    assert np.allclose(E.sigmoid(base + contribs.sum(axis=1)), p, atol=1e-5)


def test_percentile_is_the_share_strictly_below():
    ref = np.array([1.0, 2.0, 3.0, 4.0])
    assert E.share_below(ref, np.array([0.5, 3.0, 9.0])).tolist() == [0.0, 50.0, 100.0]


def test_explain_stores_groups_and_never_a_weekday_reason():
    """S7.13: the stored rows carry the behaviour groups (they add up to the contributions)
    and the three reasons skip the simulator's weekday even when the model leans on it."""
    import json
    import types

    import polars as pl

    from graphguard.demo import reasons as R

    names = list(R.TEMPLATES)
    rng = np.random.default_rng(1)
    X = rng.random((600, len(names))).astype(np.float32) * 5
    wd = names.index("weekday")
    X[:, wd] = rng.integers(1, 8, 600)
    y = (X[:, wd] >= 6).astype(int)  # the model can only learn the weekday
    m = xgb.XGBClassifier(n_estimators=20, max_depth=3, random_state=0).fit(X, y)
    score = m.predict_proba(X)[:, 1].astype(np.float64)
    tx = pl.DataFrame({
        "event_id": np.arange(600), "rank": np.argsort(np.argsort(-score, kind="stable")) + 1,
        "score": score, "features": X.astype(np.float64).tolist(),
        "amount_paid": [100.0] * 600, "payment_currency": ["Euro"] * 600,
        "amount_received": [100.0] * 600, "receiving_currency": ["Euro"] * 600,
    })  # fmt: skip
    bundle = types.SimpleNamespace(model=m, feature_columns=names)
    out = E.explain(tx, names, bundle)
    for row in out.head(50).to_dicts():
        assert not any("Wednesday" in r or "simulator" in r for r in row["reasons"])
        gs = json.loads(row["groups"])
        assert sum(g["contribution"] for g in gs) == pytest.approx(sum(row["contribs"]), abs=1e-6)
        assert gs[-1]["key"] == "calendar"
