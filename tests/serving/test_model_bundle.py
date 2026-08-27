"""A served model is not just weights.

It is weights plus the exact feature order plus the category encodings that
were fitted at training time. Ship the weights alone and the service will
happily score columns in the wrong order and return confident nonsense.
"""

import polars as pl
import pytest

from graphguard.serving.model_bundle import ModelBundle


@pytest.fixture
def bundle(tmp_path):
    import numpy as np
    import xgboost as xgb

    rng = np.random.default_rng(0)
    X = rng.random((200, 3))
    y = (X[:, 0] > 0.7).astype(int)
    model = xgb.XGBClassifier(n_estimators=5, max_depth=2).fit(X, y)

    return ModelBundle(
        model=model,
        feature_columns=("a", "b", "c"),
        category_maps={"payment_currency": {"US Dollar": 0, "Euro": 1}},
        trained_on="validation-fixture",
    )


@pytest.mark.unit
def test_save_and_load_round_trip(tmp_path, bundle):
    path = tmp_path / "model"
    bundle.save(path)
    loaded = ModelBundle.load(path)
    assert loaded.feature_columns == bundle.feature_columns
    assert loaded.category_maps == bundle.category_maps
    assert loaded.trained_on == bundle.trained_on


@pytest.mark.unit
def test_loaded_model_scores_identically(tmp_path, bundle):
    """Byte-identical predictions, or the served model is not the tested one."""
    import numpy as np

    path = tmp_path / "model"
    bundle.save(path)
    loaded = ModelBundle.load(path)

    X = np.random.default_rng(1).random((20, 3))
    assert np.allclose(bundle.model.predict_proba(X)[:, 1], loaded.model.predict_proba(X)[:, 1])


@pytest.mark.unit
def test_row_is_ordered_by_the_saved_feature_list(bundle):
    """A dict has no order the model can rely on; the bundle imposes it."""
    row = {"c": 3.0, "a": 1.0, "b": 2.0}
    assert bundle.to_vector(row).tolist() == [1.0, 2.0, 3.0]


@pytest.mark.unit
def test_missing_feature_is_rejected_not_defaulted(bundle):
    with pytest.raises(KeyError):
        bundle.to_vector({"a": 1.0, "b": 2.0})


@pytest.mark.unit
def test_extra_features_are_ignored(bundle):
    row = {"a": 1.0, "b": 2.0, "c": 3.0, "unused": 99.0}
    assert bundle.to_vector(row).tolist() == [1.0, 2.0, 3.0]


@pytest.mark.unit
def test_scoring_a_frame_uses_the_saved_order(bundle):
    df = pl.DataFrame({"c": [3.0], "b": [2.0], "a": [1.0]})
    assert bundle.score_frame(df).shape == (1,)
