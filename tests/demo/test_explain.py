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
