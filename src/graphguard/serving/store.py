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
from typing import Protocol

import redis

from graphguard.serving.online_features import AccountState

DEFAULT_URL = "redis://127.0.0.1:6380/0"

# Sentinel for "no timestamp". Redis has no null, and an empty string would be
# ambiguous with a corrupted write.
_NULL = "\x00"


class FeatureStore(Protocol):
    def get(self, account: str) -> AccountState | None: ...
    def get_many(self, accounts: list[str]) -> dict[str, AccountState | None]: ...
    def put(self, state: AccountState) -> None: ...
    def put_many(self, states: list[AccountState]) -> None: ...


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
    )


class InMemoryFeatureStore:
    """For unit tests. Deliberately not a cache -- it holds whole states."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, str]] = {}

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


class RedisFeatureStore:
    """Serving. One hash per account, one pipeline per multi-account read."""

    def __init__(self, url: str = DEFAULT_URL, namespace: str = "gg") -> None:
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._ns = namespace

    def _key(self, account: str) -> str:
        return f"{self._ns}:acct:{account}"

    def ping(self) -> bool:
        return bool(self._client.ping())

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
