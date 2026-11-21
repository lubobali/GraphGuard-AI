"""The Redis store gives exactly what the memory store gives (S6.3), on the live Redis.

Runs as the `tests` user in db 15 under a throwaway `test-…` namespace, so it can never
touch the live store; everything it wrote is deleted after. Skips where there is no Redis.
"""

import os
import uuid

import pytest
import redis
from test_updater import (  # noqa: I001 -- sibling test module, same fixtures
    HISTORY,
    SEED_AT,
    _events,
    _mismatches,
    _run,
    _stream_part,
)

from graphguard.serving.online_features import account_states_frame, recent_sends_frame
from graphguard.serving.store import redis_url
from graphguard.stream import updater as up

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_REDIS_TESTS") == "1",
        reason="GRAPHGUARD_SKIP_REDIS_TESTS=1 (no Redis in this environment)",
    ),
]


@pytest.fixture
def stores():
    client = redis.Redis.from_url(redis_url(15, "tests"))
    ns = f"test-{uuid.uuid4().hex[:12]}"
    pair = (up.RedisStore(client, namespace=ns), up.MemoryStore())
    past = HISTORY.lazy().drop("source_row")
    for store in pair:
        up.seed(store, account_states_frame(past, SEED_AT), recent_sends_frame(past, SEED_AT),
                up.edges_frame(past, SEED_AT), SEED_AT)  # fmt: skip
    yield pair
    keys = list(client.scan_iter(match=f"{ns}:*", count=5000))
    for i in range(0, len(keys), 1000):
        client.delete(*keys[i : i + 1000])


def test_redis_and_memory_agree_on_every_before_state(stores):
    rs, ms = stores
    events = _events(_stream_part())
    got = _run(rs, events, batch=250)
    want = _run(ms, events, batch=250)
    assert [b for _, b in got] == [b for _, b in want]
    assert _mismatches(got) == []  # and both equal training


def test_redis_keeps_the_same_account_hashes_as_memory(stores):
    rs, ms = stores
    events = _events(_stream_part())[:3000]
    _run(rs, events, batch=300)
    _run(ms, events, batch=300)
    for e in events[::50]:
        for a in (e.from_account, e.to_account):
            assert rs.account(a) == ms.account(a)


def test_repeats_and_acks_behave_the_same_on_redis(stores):
    rs, _ = stores
    events = _events(_stream_part())[:200]
    first = rs.apply(events)
    again = rs.apply(events)
    assert all(b.status == "replayed" for b in again)
    assert [(b.sender, b.receiver) for b in again] == [(b.sender, b.receiver) for b in first]
    rs.ack([e.source_row for e in events])
    assert all(b.status == "late" for b in rs.apply(events))
