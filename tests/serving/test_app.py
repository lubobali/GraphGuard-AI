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
    instance._model = {"bundle": instance._bundle, "version": "local", "sha256": None}
    store = InMemoryFeatureStore()
    store.set_marker({"accounts": 0})  # a loaded store in which A and B are simply new
    instance._service = ScoringService(bundle=instance._bundle, store=store)
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
    status, body = _http(scorer._score(payload))
    assert status == 422 and field in body["error"]  # S5.5: never a 200 with an error inside


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


def _http(out):
    """(status, body) for both a plain dict (200) and a JSONResponse."""
    import json

    if isinstance(out, dict):
        return 200, out
    return out.status_code, json.loads(out.body)


class _DownStore:
    """Redis unreachable: every call raises like redis-py does."""

    def readiness(self):
        from graphguard.serving.store import STORE_DOWN

        return STORE_DOWN

    def get_many(self, accounts):
        import redis

        raise redis.ConnectionError("down")


def _with_store(scorer, store):
    from graphguard.serving.service import ScoringService

    scorer._service = ScoringService(bundle=scorer._bundle, store=store)
    scorer._ready_cache = None
    return scorer


@pytest.mark.unit
@pytest.mark.parametrize(
    ("over", "why"),
    [({"amount_paid": "lots"}, "malformed"), ({"timestamp": "yesterday"}, "malformed")],
)
def test_malformed_fields_are_422(scorer, over, why):
    status, body = _http(scorer._score(_payload(**over)))
    assert status == 422 and why in body["error"]


@pytest.mark.unit
def test_redis_down_is_503_never_a_cold_score(scorer):
    _with_store(scorer, _DownStore())
    status, body = _http(scorer._score(_payload()))
    assert status == 503 and body["error"] == "feature store unavailable"
    assert "score" not in body
    assert _http(scorer._health())[0] == 503


@pytest.mark.unit
def test_an_empty_never_loaded_store_is_503_never_all_cold(scorer):
    _with_store(scorer, InMemoryFeatureStore())  # no marker, no accounts: a Redis restart
    status, body = _http(scorer._score(_payload()))
    assert status == 503 and body["error"] == "feature store not loaded"
    h_status, h_body = _http(scorer._health())
    assert h_status == 503 and h_body["reason"] == "feature store not loaded"


@pytest.mark.unit
def test_a_loaded_store_is_healthy(scorer):
    status, body = _http(scorer._health())
    assert status == 200 and body["status"] == "ok"


@pytest.mark.unit
def test_redis_failing_mid_request_is_503_and_marks_the_store_down(scorer):
    class _FlakyStore(InMemoryFeatureStore):
        def get_many(self, accounts):
            import redis

            raise redis.TimeoutError("slow")

    store = _FlakyStore()
    store.set_marker({"accounts": 0})
    _with_store(scorer, store)
    assert _http(scorer._score(_payload()))[0] == 503
    assert scorer._readiness() == "feature store unavailable"  # cached: no retry storm


@pytest.mark.unit
def test_both_new_accounts_are_sent_to_review(scorer):
    _, body = _http(scorer._score(_payload()))
    assert body["sender_cold"] and body["receiver_cold"]
    assert body["cold_policy"] == "review: both accounts new"


@pytest.mark.unit
def test_readiness_is_checked_at_most_once_a_second(scorer):
    calls = []

    class _Counting(InMemoryFeatureStore):
        def readiness(self):
            calls.append(1)
            return None

    store = _Counting()
    _with_store(scorer, store)
    for _ in range(50):
        scorer._score(_payload())
    assert len(calls) == 1
