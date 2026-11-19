"""The latency budget fails the build (S5.4).

CLAUDE.md promised a CI latency assertion that did not exist. This is it. It guards our
own code path -- feature assembly + inference -- with a production-sized model (300
trees, depth 10, 15 features). The end-to-end p99 on k3s is measured by the load
generator and recorded as a finding; CI cannot run k3s.
"""

import datetime as dt
import time

import numpy as np
import pytest
import xgboost as xgb

from graphguard.serving.latency_budget import COMPUTE_SHARE_MS, assert_within
from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.online_features import AccountState
from graphguard.serving.service import ScoringRequest, ScoringService
from graphguard.serving.store import InMemoryFeatureStore

pytestmark = [pytest.mark.unit, pytest.mark.xdist_group("latency")]

T0 = dt.datetime(2022, 9, 6, 12, 0)
FEATURES = (
    "sender_n_sent_before", "sender_amount_sent_before", "sender_distinct_out_before",
    "sender_sent_last_24h", "sender_seconds_since_last_send", "receiver_n_received_before",
    "receiver_amount_received_before", "receiver_distinct_in_before", "in_out_ratio_before",
    "hour", "weekday", "log_amount", "amount_ratio", "is_same_bank", "payment_currency_code",
)  # fmt: skip


@pytest.fixture(scope="module")
def production_sized_service():
    rng = np.random.default_rng(0)
    X = rng.random((3000, len(FEATURES)))
    y = (X[:, 0] + rng.normal(0, 0.3, len(X)) > 0.8).astype(int)
    model = xgb.XGBClassifier(n_estimators=300, max_depth=10, n_jobs=1).fit(X, y)
    bundle = ModelBundle(model, FEATURES, {"payment_currency": {"US Dollar": 0}}, "fixture")
    store = InMemoryFeatureStore()
    for name in ("A", "B"):
        store.put(AccountState(
            account=name, n_sent=40, n_received=12, amount_sent=90_000.0,
            amount_received=4_000.0, distinct_out=17, distinct_in=6,
            last_seen=T0 - dt.timedelta(hours=1), last_sent=T0 - dt.timedelta(hours=1),
            sent_last_24h=9, materialised_at=T0 - dt.timedelta(hours=1),
        ))  # fmt: skip
    return ScoringService(bundle=bundle, store=store)


def _request():
    return ScoringRequest(
        from_account="A", to_account="B", amount_paid=1500.0, amount_received=1500.0,
        from_bank="010", to_bank="011", payment_currency="US Dollar", timestamp=T0,
    )  # fmt: skip


def test_feature_assembly_and_inference_stay_inside_their_budget_share(production_sized_service):
    request = _request()
    assert_within(lambda: production_sized_service.score(request))


def test_the_guard_fails_a_slow_path():
    # Proof the assertion can fail: a path slower than the share must be caught.
    with pytest.raises(AssertionError, match="over the"):
        assert_within(lambda: time.sleep((COMPUTE_SHARE_MS + 2) / 1000), n=20, warmup=0)
