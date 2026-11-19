"""The startup check (CLAUDE.md's promised CI stage, added in S5.7).

The serving app must import, load its model THROUGH THE S3 PATH -- download by a pinned
version, verify against a pinned hash -- and answer one scoring request. CI holds no
cloud key, so the S3 here is fake (moto); the real bucket is proven on the box
(test_model_store_live.py). A wrong pinned hash must stop the scorer from starting.
"""

import boto3
import numpy as np
import pytest
import xgboost as xgb
from moto import mock_aws

from graphguard.serving import app as app_mod
from graphguard.serving import model_store as ms
from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.store import InMemoryFeatureStore

pytestmark = pytest.mark.unit

FEATURES = (
    "sender_n_sent_before", "sender_amount_sent_before", "sender_distinct_out_before",
    "sender_sent_last_24h", "sender_seconds_since_last_send", "receiver_n_received_before",
    "receiver_amount_received_before", "receiver_distinct_in_before", "in_out_ratio_before",
    "hour", "weekday", "log_amount", "amount_ratio", "is_same_bank", "payment_currency_code",
)  # fmt: skip


@pytest.fixture
def published(tmp_path, monkeypatch):
    for k, v in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
                 "AWS_REGION": "us-east-1"}.items():  # fmt: skip
        monkeypatch.setenv(k, v)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=ms.BUCKET)
        X = np.random.default_rng(0).random((200, len(FEATURES)))
        model = xgb.XGBClassifier(n_estimators=5, max_depth=2).fit(X, (X[:, 0] > 0.6).astype(int))
        ModelBundle(model, FEATURES, {"payment_currency": {"US Dollar": 0}}, "ci").save(
            tmp_path / "bundle"
        )
        version, msha = ms.publish(s3, tmp_path / "bundle", {"git_sha": "ci"})
        monkeypatch.setattr(app_mod, "MODEL_DIR", tmp_path / "downloaded")
        yield version, msha


def _start(monkeypatch, version, msha):
    monkeypatch.setattr(app_mod, "MODEL_VERSION", version)
    monkeypatch.setattr(app_mod, "MODEL_SHA256", msha)
    return app_mod.Scorer.func_or_class(redis_url="redis://127.0.0.1:1/0")  # never dialled


def test_the_app_loads_its_model_from_s3_and_answers_one_request(published, monkeypatch):
    version, msha = published
    scorer = _start(monkeypatch, version, msha)
    store = InMemoryFeatureStore()
    store.set_marker({"accounts": 0})
    scorer._service._store = store
    out = scorer._score({
        "from_account": "A", "to_account": "B", "amount_paid": 100.0, "amount_received": 100.0,
        "from_bank": "1", "to_bank": "2", "payment_currency": "US Dollar",
        "timestamp": "2022-09-07T10:00:00",
    })  # fmt: skip
    assert 0.0 <= out["score"] <= 1.0 and out["model_version"] == version
    import json

    health = json.loads(scorer._health().body)
    assert health["model_version"] == version and health["model_sha256"] == msha


def test_a_wrong_pinned_hash_stops_the_scorer_from_starting(published, monkeypatch):
    version, _ = published
    with pytest.raises(ms.ModelVerificationError):
        _start(monkeypatch, version, "f" * 64)


def test_a_version_pinned_without_its_hash_is_refused(published, monkeypatch):
    version, _ = published
    with pytest.raises(ms.ModelVerificationError, match="without its sha256"):
        _start(monkeypatch, version, "")
