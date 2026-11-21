"""The online feature store.

Two implementations behind one interface: in-memory for unit tests, Redis for
serving. The same test suite runs against both, because if they can diverge
then the thing the tests pass against is not the thing that serves.

**Why a store at all.** Computing an account's history means scanning millions
of rows. A scoring request has fifty milliseconds. So the history is
precomputed and looked up.

**Serialisation is explicit.** Redis stores strings, and the round trip has to
preserve types exactly -- in particular a null timestamp must come back null
rather than as epoch zero, because "this account has never sent" and "this
account last sent in 1970" are different inputs to the model.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Protocol

import redis

from graphguard.serving.online_features import AccountState

# GraphGuard's own Redis (not LuBot's). db 0 is the live store; tests use their
# own database number so they can never write into it.
REDIS_BASE = os.environ.get("GRAPHGUARD_REDIS_BASE", "redis://127.0.0.1:6380")


def redis_url(db: int = 0, user: str | None = None) -> str:
    """The store's URL. With `user`, it carries that Redis user's credentials (S5b.1:
    the default user is off, so a URL without them gets NOAUTH). The password comes
    from `.secrets/redis.env`; if it is missing this raises -- it never falls back to
    connecting without auth."""
    if user is None:
        return f"{REDIS_BASE}/{db}"
    from urllib.parse import quote, urlsplit

    from graphguard.serving.redis_acl import password

    base = urlsplit(REDIS_BASE)
    return f"{base.scheme}://{quote(user)}:{quote(password(user), safe='')}@{base.netloc}/{db}"


# Sentinel for "no timestamp". Redis has no null, and an empty string would be
# ambiguous with a corrupted write.
_NULL = "\x00"


class FeatureStore(Protocol):
    def get(self, account: str) -> AccountState | None: ...
    def get_many(self, accounts: list[str]) -> dict[str, AccountState | None]: ...
    def put(self, state: AccountState) -> None: ...
    def put_many(self, states: list[AccountState]) -> None: ...
    def set_marker(self, info: dict[str, str]) -> None: ...
    def marker(self) -> dict[str, str] | None: ...
    def readiness(self) -> str | None: ...


MARKER = "!store"  # not a valid account id: accounts are alphanumeric
STORE_DOWN = "feature store unavailable"
STORE_NOT_LOADED = "feature store not loaded"


def _encode(state: AccountState) -> dict[str, str]:
    def ts(value: dt.datetime | None) -> str:
        return _NULL if value is None else value.isoformat()

    return {
        "n_sent": str(state.n_sent),
        "n_received": str(state.n_received),
        "amount_sent": repr(state.amount_sent),
        "amount_received": repr(state.amount_received),
        "distinct_out": str(state.distinct_out),
        "distinct_in": str(state.distinct_in),
        "sent_last_24h": str(state.sent_last_24h),
        "last_seen": ts(state.last_seen),
        "last_sent": ts(state.last_sent),
        "materialised_at": ts(state.materialised_at),
    }


def _decode(account: str, raw: dict[str, str]) -> AccountState:
    def ts(value: str) -> dt.datetime | None:
        return None if value == _NULL else dt.datetime.fromisoformat(value)

    return AccountState(
        account=account,
        n_sent=int(raw["n_sent"]),
        n_received=int(raw["n_received"]),
        amount_sent=float(raw["amount_sent"]),
        amount_received=float(raw["amount_received"]),
        distinct_out=int(raw["distinct_out"]),
        distinct_in=int(raw["distinct_in"]),
        sent_last_24h=int(raw["sent_last_24h"]),
        last_seen=ts(raw["last_seen"]),
        last_sent=ts(raw["last_sent"]),
        materialised_at=ts(raw.get("materialised_at", _NULL)),
    )


class InMemoryFeatureStore:
    """For unit tests. Deliberately not a cache -- it holds whole states."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}
        self._marker: dict[str, str] | None = None

    def set_marker(self, info: dict[str, str]) -> None:
        self._marker = {k: str(v) for k, v in info.items()}

    def marker(self) -> dict[str, str] | None:
        return self._marker

    def readiness(self) -> str | None:
        # Unit tests fill it with put() and expect it to serve; an empty one with no
        # marker is the "never loaded" case.
        return None if (self._marker or self._data) else STORE_NOT_LOADED

    def get(self, account: str) -> AccountState | None:
        raw = self._data.get(account)
        return _decode(account, raw) if raw else None

    def get_many(self, accounts: list[str]) -> dict[str, AccountState | None]:
        return {a: self.get(a) for a in accounts}

    def put(self, state: AccountState) -> None:
        self._data[state.account] = _encode(state)

    def put_many(self, states: list[AccountState]) -> None:
        for s in states:
            self.put(s)

    def clear(self) -> None:
        self._data.clear()

    def prune_except(self, keep: set[str]) -> int:
        gone = [a for a in self._data if a not in keep]
        for a in gone:
            del self._data[a]
        return len(gone)


class RedisFeatureStore:
    """Serving. One hash per account, one pipeline per multi-account read."""

    def __init__(self, url: str | None = None, namespace: str = "gg", user: str = "loader") -> None:
        # GRAPHGUARD_REDIS_URL (the scorer pod: its URL comes from a Kubernetes
        # Secret) beats the default, which logs in as `user` with its own password.
        url = url or os.environ.get("GRAPHGUARD_REDIS_URL") or redis_url(0, user)
        # Timeouts: a hung Redis must fail a request in ~2 s, not hold it forever.
        self._client = redis.Redis.from_url(
            url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
        )
        self._ns = namespace

    def _key(self, account: str) -> str:
        return f"{self._ns}:acct:{account}"

    @property
    def client(self) -> redis.Redis:
        """The same connection, for the stream's seed (S6.3) -- one login, one user."""
        return self._client

    def ping(self) -> bool:
        return bool(self._client.ping())

    # --- the store marker (S5.5) ----------------------------------------------------------
    # Written by `store-load` after every account, so "no marker" means "never completely
    # loaded" -- after a Redis restart, before the refill finishes. Inside the `acct`
    # pattern (the users' ACL allows only that), under a name no account can have.
    def _marker_key(self) -> str:
        return f"{self._ns}:acct:{MARKER}"

    def set_marker(self, info: dict[str, str]) -> None:
        self._client.hset(self._marker_key(), mapping={k: str(v) for k, v in info.items()})

    def marker(self) -> dict[str, str] | None:
        return self._client.hgetall(self._marker_key()) or None

    def readiness(self) -> str | None:
        """None when ready to serve; otherwise why not. One round trip."""
        try:
            raw = self._client.hgetall(self._marker_key())
        except (redis.ConnectionError, redis.TimeoutError):
            return STORE_DOWN
        return None if raw else STORE_NOT_LOADED

    def get(self, account: str) -> AccountState | None:
        raw = self._client.hgetall(self._key(account))
        return _decode(account, raw) if raw else None

    def get_many(self, accounts: list[str]) -> dict[str, AccountState | None]:
        """One round trip for all of them. Serving reads two per request, and
        two sequential round trips is two network hops inside a 50ms budget."""
        pipe = self._client.pipeline(transaction=False)
        for account in accounts:
            pipe.hgetall(self._key(account))
        results = pipe.execute()
        return {
            account: (_decode(account, raw) if raw else None)
            for account, raw in zip(accounts, results, strict=True)
        }

    def put(self, state: AccountState) -> None:
        self._client.hset(self._key(state.account), mapping=_encode(state))

    def put_many(self, states: list[AccountState], batch: int = 5_000) -> None:
        for start in range(0, len(states), batch):
            pipe = self._client.pipeline(transaction=False)
            for state in states[start : start + batch]:
                pipe.hset(self._key(state.account), mapping=_encode(state))
            pipe.execute()

    def clear(self) -> None:
        """Delete only this namespace. Never flushes the database -- other
        things may live in it, and a stray FLUSHALL on a shared box is how
        someone else's afternoon disappears."""
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=f"{self._ns}:*", count=1000)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break

    def prune_except(self, keep: set[str]) -> int:
        """Delete accounts in this namespace that are not in `keep`.

        Used after an in-place reload: overwrite every current account first,
        then remove the ones that no longer exist. The store is never empty
        during a reload, so no request ever sees every account as cold.
        """
        prefix = f"{self._ns}:acct:"
        removed = 0
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor, match=f"{prefix}*", count=5000)
            stale = [k for k in keys if k[len(prefix) :] not in keep and k[len(prefix) :] != MARKER]
            if stale:
                removed += self._client.delete(*stale)
            if cursor == 0:
                break
        return removed
