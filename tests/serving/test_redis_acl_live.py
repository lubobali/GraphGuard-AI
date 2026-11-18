"""The live Redis refuses what each user may not do (S5b.1).

The rules come from the ACL *file* Redis loads at start, so they hold across restarts
(unlike a live `ACL SETUSER`). Needs GraphGuard's Redis; CI has none and skips by the
explicit flag, reason printed. Writes only to test keys (db 15).
"""

import os
import uuid

import pytest
import redis

from graphguard.serving.store import redis_url

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_REDIS_TESTS") == "1",
        reason="GRAPHGUARD_SKIP_REDIS_TESTS=1 (no Redis in this environment)",
    ),
]


def _client(user=None, db=0):
    return redis.Redis.from_url(redis_url(db, user), decode_responses=True)


def test_no_password_gets_nothing():
    c = _client()
    with pytest.raises(redis.exceptions.AuthenticationError):
        c.hgetall("gg:acct:anything")


def test_a_wrong_password_is_refused():
    with pytest.raises(redis.exceptions.AuthenticationError):
        redis.Redis(
            host="127.0.0.1",
            port=6380,
            username="scorer",
            password="wrong",  # betterleaks:allow -- deliberately wrong; Redis must refuse it
        ).ping()


def test_the_scorer_reads_accounts_but_cannot_write():
    c = _client("scorer")
    assert c.ping()
    with pytest.raises(redis.exceptions.NoPermissionError):
        c.hset("gg:acct:probe", "n_sent", "1")
    with pytest.raises(redis.exceptions.NoPermissionError):
        c.scan(0)


@pytest.mark.parametrize("user", ["scorer", "loader", "tests"])
def test_nobody_can_run_scripts_or_admin_commands(user):
    c = _client(user, db=15 if user == "tests" else 0)
    for call in (
        lambda: c.eval("return 1", 0),
        lambda: c.execute_command("FUNCTION", "LIST"),
        lambda: c.config_get("*"),
        lambda: c.keys("*"),
        lambda: c.flushall(),
        lambda: c.execute_command("ACL", "LIST"),
    ):
        with pytest.raises(redis.exceptions.NoPermissionError):
            call()


def test_the_tests_user_cannot_touch_the_live_store():
    c = _client("tests", db=15)
    with pytest.raises(redis.exceptions.NoPermissionError):
        c.hgetall("gg:acct:anything")
    key = f"test-{uuid.uuid4().hex}:acct:x"
    c.hset(key, "n_sent", "1")
    assert c.hgetall(key) == {"n_sent": "1"}
    c.delete(key)


def test_the_loader_cannot_touch_test_or_other_keys():
    c = _client("loader")
    with pytest.raises(redis.exceptions.NoPermissionError):
        c.hset("other:thing", "x", "1")
