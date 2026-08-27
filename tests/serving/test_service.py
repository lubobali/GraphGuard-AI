"""The scoring service: one transaction in, one score out.

The cold path gets as much attention as the warm one. New accounts arrive
constantly, and a service that errors or silently mis-scores them fails on the
customers a bank is most careful about.
"""

import datetime as dt

import numpy as np
import pytest
import xgboost as xgb

from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.online_features import AccountState
from graphguard.serving.service import ScoringRequest, ScoringService
from graphguard.serving.store import InMemoryFeatureStore

T0 = dt.datetime(2022, 9, 6, 12, 0)

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
def service():
    rng = np.random.default_rng(0)
    X = rng.random((300, len(FEATURES)))
    y = (X[:, 0] > 0.6).astype(int)
    model = xgb.XGBClassifier(n_estimators=8, max_depth=3).fit(X, y)

    bundle = ModelBundle(
        model=model,
        feature_columns=FEATURES,
        category_maps={"payment_currency": {"US Dollar": 0, "Euro": 1}},
        trained_on="fixture",
    )

    store = InMemoryFeatureStore()
    store.put(
        AccountState(
            account="WARM",
            n_sent=40,
            n_received=12,
            amount_sent=90_000.0,
            amount_received=4_000.0,
            distinct_out=17,
            distinct_in=6,
            last_seen=T0 - dt.timedelta(hours=1),
            last_sent=T0 - dt.timedelta(hours=1),
            sent_last_24h=9,
        )
    )
    return ScoringService(bundle=bundle, store=store)


def _request(sender="WARM", receiver="WARM", **over):
    base = dict(
        from_account=sender,
        to_account=receiver,
        amount_paid=1500.0,
        amount_received=1500.0,
        from_bank="010",
        to_bank="011",
        payment_currency="US Dollar",
        timestamp=T0,
    )
    base.update(over)
    return ScoringRequest(**base)


@pytest.mark.unit
def test_score_is_a_probability(service):
    out = service.score(_request())
    assert 0.0 <= out.score <= 1.0


@pytest.mark.unit
def test_cold_sender_still_scores(service):
    """A brand new customer's first payment must be scoreable."""
    out = service.score(_request(sender="BRAND_NEW"))
    assert 0.0 <= out.score <= 1.0
    assert out.sender_cold is True


@pytest.mark.unit
def test_both_cold_still_scores(service):
    out = service.score(_request(sender="NEW_A", receiver="NEW_B"))
    assert out.sender_cold and out.receiver_cold


@pytest.mark.unit
def test_warm_account_is_not_flagged_cold(service):
    out = service.score(_request())
    assert out.sender_cold is False


@pytest.mark.unit
def test_unknown_currency_does_not_crash(service):
    """A currency never seen in training gets the unseen code, not an error."""
    out = service.score(_request(payment_currency="Klingon Darsek"))
    assert 0.0 <= out.score <= 1.0


@pytest.mark.unit
def test_response_reports_feature_staleness(service):
    """How old the stored state was. The UI and monitoring both need it."""
    out = service.score(_request())
    assert out.sender_staleness_seconds == pytest.approx(3600, abs=1)


@pytest.mark.unit
def test_cold_account_reports_no_staleness(service):
    out = service.score(_request(sender="BRAND_NEW"))
    assert out.sender_staleness_seconds is None


@pytest.mark.unit
def test_zero_amount_does_not_crash(service):
    out = service.score(_request(amount_paid=0.0, amount_received=0.0))
    assert 0.0 <= out.score <= 1.0


@pytest.mark.unit
def test_scoring_is_deterministic(service):
    a = service.score(_request())
    b = service.score(_request())
    assert a.score == b.score
