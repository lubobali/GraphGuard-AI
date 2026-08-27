"""The HTTP layer must validate, not assume.

Only the translation is tested here; the scoring logic is covered in
test_service.py. Testing it twice through a server would be slower and would
prove less.
"""

import numpy as np
import pytest
import xgboost as xgb

from graphguard.serving.app import REQUIRED_FIELDS, Scorer
from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.store import InMemoryFeatureStore

# The production feature list, duplicated rather than imported across test
# modules: tests are not a package, and a shared fixture module would couple
# two suites that should be able to fail independently.
FEATURES = (
    "sender_n_sent_before",
    "sender_amount_sent_before",
    "sender_distinct_out_before",
    "sender_sent_last_24h",
    "sender_seconds_since_last_send",
    "receiver_n_received_before",
    "receiver_amount_received_before",
    "receiver_distinct_in_before",
    "in_out_ratio_before",
    "hour",
    "weekday",
    "log_amount",
    "amount_ratio",
    "is_same_bank",
    "payment_currency_code",
)


@pytest.fixture
def scorer(tmp_path):
    rng = np.random.default_rng(0)
    X = rng.random((200, len(FEATURES)))
    model = xgb.XGBClassifier(n_estimators=5, max_depth=2).fit(X, (X[:, 0] > 0.6).astype(int))
    ModelBundle(
        model=model,
        feature_columns=FEATURES,
        category_maps={"payment_currency": {"US Dollar": 0}},
        trained_on="fixture",
    ).save(tmp_path / "bundle")

    # func_or_class reaches the underlying class without starting Ray.
    instance = Scorer.func_or_class.__new__(Scorer.func_or_class)
    from graphguard.serving.service import ScoringService

    instance._bundle = ModelBundle.load(tmp_path / "bundle")
    instance._service = ScoringService(bundle=instance._bundle, store=InMemoryFeatureStore())
    return instance


def _payload(**over):
    base = {
        "from_account": "A",
        "to_account": "B",
        "amount_paid": 100.0,
        "amount_received": 100.0,
        "from_bank": "010",
        "to_bank": "011",
        "payment_currency": "US Dollar",
        "timestamp": "2022-09-06T12:00:00",
    }
    base.update(over)
    return base


@pytest.mark.unit
def test_valid_payload_returns_a_score(scorer):
    out = scorer._score(_payload())
    assert 0.0 <= out["score"] <= 1.0


@pytest.mark.unit
@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_missing_field_is_reported_not_defaulted(scorer, field):
    payload = _payload()
    del payload[field]
    assert "error" in scorer._score(payload)
    assert field in scorer._score(payload)["error"]


@pytest.mark.unit
def test_response_reports_which_model_answered(scorer):
    """Traceability: a score with no model identity cannot be investigated."""
    assert scorer._score(_payload())["model_trained_on"] == "fixture"


@pytest.mark.unit
def test_unknown_accounts_are_reported_cold(scorer):
    out = scorer._score(_payload())
    assert out["sender_cold"] and out["receiver_cold"]


@pytest.mark.unit
def test_string_numbers_are_accepted(scorer):
    """Real callers send JSON, and JSON numbers arrive as strings often enough."""
    out = scorer._score(_payload(amount_paid="100.0", amount_received="100.0"))
    assert 0.0 <= out["score"] <= 1.0
