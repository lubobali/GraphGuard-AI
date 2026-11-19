"""The feature store: what goes in comes back out, unchanged.

Two implementations exist -- in-memory for unit tests, Redis for serving -- and
the same tests run against both. If they can diverge, the thing tests pass
against is not the thing that serves.
"""

import datetime as dt
import os
import uuid

import pytest

from graphguard.serving.online_features import AccountState
from graphguard.serving.store import InMemoryFeatureStore, RedisFeatureStore, redis_url

T0 = dt.datetime(2022, 9, 6, 12, 0)


def _state(account="A", **over):
    base = dict(
        account=account,
        n_sent=7,
        n_received=3,
        amount_sent=1234.56,
        amount_received=99.9,
        distinct_out=4,
        distinct_in=2,
        last_seen=T0,
        last_sent=T0 - dt.timedelta(hours=2),
        sent_last_24h=5,
    )
    base.update(over)
    return AccountState(**base)


# Integration tests use their OWN Redis database, never db 0 where the live
# store lives. Before S5.6a they wrote test:acct:* keys into the live store.
# Logs in as the `tests` Redis user (S5b.1), whose keys must match `test-*`. Built
# only when a Redis test runs, so CI (no Redis, no secrets) never needs a password.
def _test_db_url() -> str:
    return os.environ.get("GRAPHGUARD_TEST_REDIS_URL") or redis_url(db=15, user="tests")


# Redis tests are skipped only when this is set -- CI, which has no Redis, sets
# it explicitly, so the skip is a stated decision with a reason. Anywhere else
# an unreachable or password-protected Redis FAILS the test instead of quietly
# removing it from the run (which is what the old try/except did).
SKIP_REDIS = os.environ.get("GRAPHGUARD_SKIP_REDIS_TESTS") == "1"


@pytest.fixture(params=["memory", "redis"])
def store(request):
    if request.param == "memory":
        yield InMemoryFeatureStore()
        return
    if SKIP_REDIS:
        pytest.skip("GRAPHGUARD_SKIP_REDIS_TESTS=1 (no Redis in this environment)")
    # A namespace per test: xdist runs four workers against the same database,
    # and a shared namespace let one test's cleanup delete another's keys.
    s = RedisFeatureStore(url=_test_db_url(), namespace=f"test-{uuid.uuid4().hex}")
    s.ping()  # raises -> the test fails, loudly
    s.clear()
    yield s
    s.clear()


@pytest.mark.unit
def test_test_db_is_not_the_live_db():
    assert redis_url(db=15).endswith("/15") and not redis_url(db=15).endswith("/0")


@pytest.mark.integration
def test_round_trip_preserves_every_field(store):
    store.put(_state())
    got = store.get("A")
    assert got == _state()


@pytest.mark.integration
def test_missing_account_returns_none(store):
    assert store.get("NEVER_SEEN") is None


@pytest.mark.integration
def test_put_many_writes_all(store):
    store.put_many([_state("A"), _state("B", n_sent=1)])
    assert store.get("A").n_sent == 7
    assert store.get("B").n_sent == 1


@pytest.mark.integration
def test_overwriting_replaces_rather_than_merges(store):
    store.put(_state("A", n_sent=7))
    store.put(_state("A", n_sent=99))
    assert store.get("A").n_sent == 99


@pytest.mark.integration
def test_null_timestamps_survive_the_round_trip(store):
    """A cold account has never sent. That must not become epoch zero."""
    store.put(_state("COLD", last_seen=None, last_sent=None))
    got = store.get("COLD")
    assert got.last_seen is None
    assert got.last_sent is None


@pytest.mark.integration
def test_floats_are_not_truncated(store):
    store.put(_state("A", amount_sent=1234.56))
    assert store.get("A").amount_sent == pytest.approx(1234.56)


@pytest.mark.integration
def test_get_many_returns_a_state_per_requested_account(store):
    """Serving fetches two accounts per request; one round trip, not two."""
    store.put_many([_state("A"), _state("B")])
    got = store.get_many(["A", "B", "MISSING"])
    assert got["A"].n_sent == 7
    assert got["B"].n_sent == 7
    assert got["MISSING"] is None


# --- the store marker (S5.5): "completely loaded" is a fact the scorer can check -------
def test_a_never_loaded_store_is_not_ready_and_a_marked_one_is(store):
    assert store.readiness() == "feature store not loaded"
    store.set_marker({"accounts": 3, "as_of": "2022-09-06T00:00:00"})
    assert store.readiness() is None
    assert store.marker()["accounts"] == "3"


def test_pruning_after_a_reload_keeps_the_marker(store):
    if isinstance(store, InMemoryFeatureStore):
        pytest.skip("the marker key only exists in Redis")
    store.put(_state("A"))
    store.set_marker({"accounts": 1})
    store.prune_except({"A"})
    assert store.readiness() is None and store.get("A") is not None


def test_an_unreachable_redis_reports_down_quickly():
    import time

    s = RedisFeatureStore(url="redis://127.0.0.1:1/0", namespace="test-nowhere")
    t = time.perf_counter()
    assert s.readiness() == "feature store unavailable"
    assert time.perf_counter() - t < 3  # the 2 s timeout, not a hang
