"""The feature store: what goes in comes back out, unchanged.

Two implementations exist -- in-memory for unit tests, Redis for serving -- and
the same tests run against both. If they can diverge, the thing tests pass
against is not the thing that serves.
"""

import datetime as dt

import pytest

from graphguard.serving.online_features import AccountState
from graphguard.serving.store import InMemoryFeatureStore, RedisFeatureStore

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


def _redis_available() -> bool:
    try:
        RedisFeatureStore().ping()
        return True
    except Exception:
        return False


STORES = ["memory"] + (["redis"] if _redis_available() else [])


@pytest.fixture(params=STORES)
def store(request):
    if request.param == "memory":
        return InMemoryFeatureStore()
    s = RedisFeatureStore(namespace="test")
    s.clear()
    return s


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
