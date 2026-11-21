"""Live account features for the stream (S6.3).

Every event gets both accounts' state **before** it -- exactly what training computed for
that row (`features.graph`) -- and is then applied, so the next event sees it. FINDING-008:
a store refreshed in batch loses 83% of PR-AUC, because cumulative counts go stale; this
keeps them exact instead.

**One writer, one transaction per micro-batch.** No Lua: S5b.1 banned scripting
(RediShell, CVE-2025-49844) and that stands. The single writer reads what a batch needs,
`plan()` computes the whole batch in Python with training's float64 arithmetic, and the
writes go out in one MULTI/EXEC -- all or nothing. `plan` is pure; the stores only read
and write.

Redis layout (namespace `gg`):

    acct:{a}        the account's hash (what the scorer reads) + `wm`, the last applied
                    (timestamp, source_row) touching it -- repeats and late events stop here
    edge:{shard}    "from<TAB>to" pairs seen so far, 16,384 shards (small sets stay
                    compact): one SADD answer says "new counterparty" for BOTH sides
    win:{a}         the sender's sends in the last 24 h, score = epoch seconds; counted with
                    an exclusive lower bound, as training is, and trimmed as time moves
    ev:{source_row} the before-state of an applied event, until its decision is stored
                    (`ack`) or 6 h pass: a redelivered event gets the same features back
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import zlib
from collections import defaultdict
from dataclasses import dataclass, field

import polars as pl

from graphguard.serving.online_features import AccountState, states_from_frame
from graphguard.serving.store import _decode, _encode

SHARDS = 16_384
WINDOW = 24 * 3600
EV_TTL = 6 * 3600
EPOCH = dt.datetime(1970, 1, 1)
APPLIED, REPLAYED, LATE = "applied", "replayed", "late"


@dataclass(frozen=True)
class Event:
    source_row: int
    timestamp: dt.datetime
    from_account: str
    to_account: str
    amount_paid: float


@dataclass(frozen=True)
class Before:
    """Both accounts as of just before the event. `sender.sent_last_24h` is the 24 h count
    at the event's own time. For `late`, the states are not exact and must not be scored."""

    status: str
    sender: AccountState
    receiver: AccountState


def order(e: Event) -> tuple[dt.datetime, int]:
    """Training's order: time, then source order (FINDING-010, FINDING-015)."""
    return (e.timestamp, e.source_row)


def epoch(ts: dt.datetime) -> int:
    return int((ts - EPOCH).total_seconds())


def mark(e: Event) -> str:
    """Comparable as a string: the watermark of an applied event."""
    return f"{epoch(e.timestamp):012d}:{e.source_row:012d}"


def edge(frm: str, to: str) -> str:
    return f"{frm}\t{to}"


def shard(member: str) -> int:
    return zlib.crc32(member.encode()) % SHARDS


# --- what a batch reads and writes ----------------------------------------------------
@dataclass
class Reads:
    accounts: dict[str, dict[str, str]]  # raw hash, {} when unseen
    edges: dict[str, bool]  # pair -> already seen
    windows: dict[tuple[str, int], int]  # (sender, cutoff) -> stored sends with score > cutoff
    replays: dict[int, str | None]  # source_row -> stored before-state (JSON)


@dataclass
class Writes:
    accounts: dict[str, dict[str, str]] = field(default_factory=dict)
    edges: dict[int, set[str]] = field(default_factory=lambda: defaultdict(set))
    windows: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(dict))
    trims: dict[str, int] = field(default_factory=dict)  # sender -> drop scores <= this
    replays: dict[int, str] = field(default_factory=dict)


def needs(events: list[Event]) -> tuple[set[str], set[str], set[tuple[str, int]], set[int]]:
    accts = {a for e in events for a in (e.from_account, e.to_account)}
    pairs = {edge(e.from_account, e.to_account) for e in events}
    windows = {(e.from_account, epoch(e.timestamp) - WINDOW) for e in events}
    return accts, pairs, windows, {e.source_row for e in events}


def _state(account: str, raw: dict[str, str]) -> AccountState:
    if not raw:
        return AccountState.cold(account)
    return _decode(account, raw)


def _pack(before: Before) -> str:
    return json.dumps({"s": [before.sender.account, _encode(before.sender), before.sender.is_cold],
                       "r": [before.receiver.account, _encode(before.receiver),
                             before.receiver.is_cold]})  # fmt: skip


def _unpack(text: str) -> Before:
    d = json.loads(text)
    s = dataclasses.replace(_decode(d["s"][0], d["s"][1]), is_cold=d["s"][2])
    r = dataclasses.replace(_decode(d["r"][0], d["r"][1]), is_cold=d["r"][2])
    return Before(REPLAYED, s, r)


def _later(a: dt.datetime | None, b: dt.datetime) -> dt.datetime:
    return b if a is None or b > a else a


def plan(events: list[Event], reads: Reads) -> tuple[list[Before], Writes]:
    """The whole batch, pure: before-states in training's order, and the writes."""
    events = sorted(events, key=order)
    state = {a: _state(a, raw) for a, raw in reads.accounts.items()}
    wm = {a: raw.get("wm", "") for a, raw in reads.accounts.items()}
    sends: dict[str, list[int]] = defaultdict(list)  # this batch's sends per sender
    new_pairs: set[str] = set()
    done: dict[int, Before] = {}
    touched: set[str] = set()
    out: list[Before] = []
    w = Writes()

    for e in events:
        f, t, a, k = e.from_account, e.to_account, e.amount_paid, mark(e)
        if e.source_row in done:  # the same event twice in one batch
            out.append(dataclasses.replace(done[e.source_row], status=REPLAYED))
            continue
        if (stored := reads.replays.get(e.source_row)) is not None:
            out.append(done.setdefault(e.source_row, _unpack(stored)))
            continue
        if k <= wm[f] or k <= wm[t]:  # older than what these accounts already saw
            out.append(Before(LATE, state[f], state[t]))
            continue

        s0, r0 = state[f], state[t]
        now, cutoff = epoch(e.timestamp), epoch(e.timestamp) - WINDOW
        window = reads.windows[(f, cutoff)] + sum(1 for x in sends[f] if x > cutoff)
        pair = edge(f, t)
        new = 0 if (reads.edges[pair] or pair in new_pairs) else 1
        before = Before(APPLIED, dataclasses.replace(s0, sent_last_24h=window), r0)

        s1 = dataclasses.replace(
            s0, n_sent=s0.n_sent + 1, amount_sent=s0.amount_sent + a,
            distinct_out=s0.distinct_out + new, last_sent=e.timestamp,
            last_seen=_later(s0.last_seen, e.timestamp), sent_last_24h=window + 1,
            materialised_at=e.timestamp, is_cold=False,
        )  # fmt: skip
        base = s1 if f == t else r0  # a self-transfer is one account on both sides
        r1 = dataclasses.replace(
            base, n_received=base.n_received + 1, amount_received=base.amount_received + a,
            distinct_in=base.distinct_in + new, last_seen=_later(base.last_seen, e.timestamp),
            materialised_at=e.timestamp, is_cold=False,
        )  # fmt: skip
        state[f], state[t] = s1, r1
        if f == t:
            state[f] = r1
        wm[f] = wm[t] = k
        touched.update((f, t))
        sends[f].append(now)
        new_pairs.add(pair)
        if new:
            w.edges[shard(pair)].add(pair)
        w.windows[f][str(e.source_row)] = now
        w.trims[f] = cutoff
        packed = _pack(before)
        w.replays[e.source_row] = packed
        done[e.source_row] = before
        out.append(before)

    w.accounts = {a: {**_encode(state[a]), "wm": wm[a]} for a in touched}
    return out, w


# --- stores ---------------------------------------------------------------------------
class MemoryStore:
    """The same contract as RedisStore, in dicts: unit tests and the fast full proof."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.edges: set[str] = set()
        self.windows: dict[str, dict[str, int]] = defaultdict(dict)
        self.replays: dict[int, str] = {}

    def read(self, events: list[Event]) -> Reads:
        accts, pairs, windows, ids = needs(events)
        return Reads(
            accounts={a: dict(self.hashes.get(a, {})) for a in accts},
            edges={p: p in self.edges for p in pairs},
            windows={
                (a, c): sum(1 for s in self.windows.get(a, {}).values() if s > c)
                for a, c in windows
            },  # fmt: skip
            replays={i: self.replays.get(i) for i in ids},
        )

    def write(self, w: Writes) -> None:
        for a, mapping in w.accounts.items():
            self.hashes.setdefault(a, {}).update(mapping)
        for members in w.edges.values():
            self.edges |= members
        for a, members in w.windows.items():
            self.windows[a].update(members)
        for a, cut in w.trims.items():
            self.windows[a] = {m: s for m, s in self.windows[a].items() if s > cut}
        self.replays.update(w.replays)

    def apply(self, events: list[Event]) -> list[Before]:
        befores, writes = plan(events, self.read(events))
        self.write(writes)
        return befores

    def ack(self, source_rows: list[int]) -> None:
        for i in source_rows:
            self.replays.pop(i, None)

    def account(self, a: str) -> AccountState | None:
        raw = self.hashes.get(a)
        return _decode(a, raw) if raw else None

    # seeding
    def load_accounts(self, mapping: dict[str, dict[str, str]]) -> None:
        self.hashes.update(mapping)

    def clear_stream(self) -> None:
        self.edges, self.windows, self.replays = set(), defaultdict(dict), {}

    def reset_watermarks(self, accounts: list[str]) -> None:
        for a in accounts:
            if a in self.hashes:
                self.hashes[a]["wm"] = ""

    def load_windows(self, windows: dict[str, dict[str, int]]) -> None:
        for a, m in windows.items():
            self.windows[a].update(m)

    def load_edges(self, members: dict[int, set[str]]) -> None:
        for m in members.values():
            self.edges |= m


class RedisStore:
    """The live store. Reads in one pipeline, writes in one MULTI/EXEC per batch."""

    def __init__(self, client, namespace: str = "gg") -> None:
        self._r = client
        self._ns = namespace

    def _k(self, kind: str, name: object) -> str:
        return f"{self._ns}:{kind}:{name}"

    def read(self, events: list[Event]) -> Reads:
        accts, pairs, windows, ids = needs(events)
        accts, windows, ids = sorted(accts), sorted(windows), sorted(ids)
        by_shard: dict[int, list[str]] = defaultdict(list)
        for p in sorted(pairs):
            by_shard[shard(p)].append(p)
        shards = sorted(by_shard)
        p = self._r.pipeline(transaction=False)
        for a in accts:
            p.hgetall(self._k("acct", a))
        for s in shards:
            p.smismember(self._k("edge", s), by_shard[s])
        for a, c in windows:
            p.zcount(self._k("win", a), f"({c}", "+inf")
        for i in ids:
            p.get(self._k("ev", i))
        res = p.execute()
        n1, n2, n3 = len(accts), len(accts) + len(shards), len(accts) + len(shards) + len(windows)
        seen = {}
        for s, flags in zip(shards, res[n1:n2], strict=True):
            seen.update({m: bool(f) for m, f in zip(by_shard[s], flags, strict=True)})
        return Reads(
            accounts={a: _text(h) for a, h in zip(accts, res[:n1], strict=True)},
            edges=seen,
            windows=dict(zip(windows, (int(x) for x in res[n2:n3]), strict=True)),
            replays={
                i: (v.decode() if isinstance(v, bytes) else v)
                for i, v in zip(ids, res[n3:], strict=True)
            },  # fmt: skip
        )

    def write(self, w: Writes) -> None:
        p = self._r.pipeline(transaction=True)  # MULTI ... EXEC: all or nothing
        for a, mapping in w.accounts.items():
            p.hset(self._k("acct", a), mapping=mapping)
        for s, members in w.edges.items():
            p.sadd(self._k("edge", s), *members)
        for a, members in w.windows.items():
            p.zadd(self._k("win", a), members)
        for a, cut in w.trims.items():
            p.zremrangebyscore(self._k("win", a), "-inf", cut)
        for i, packed in w.replays.items():
            p.set(self._k("ev", i), packed, ex=EV_TTL)
        p.execute()

    def apply(self, events: list[Event]) -> list[Before]:
        befores, writes = plan(events, self.read(events))
        self.write(writes)
        return befores

    def ack(self, source_rows: list[int]) -> None:
        if source_rows:
            self._r.delete(*(self._k("ev", i) for i in source_rows))

    def account(self, a: str) -> AccountState | None:
        raw = _text(self._r.hgetall(self._k("acct", a)))
        return _decode(a, raw) if raw else None

    # seeding (loader user)
    def clear_stream(self) -> int:
        """Delete this namespace's edge/window/pending keys (SCAN + DEL; never FLUSH)."""
        n = 0
        for kind in ("edge", "win", "ev"):
            batch = []
            for key in self._r.scan_iter(match=self._k(kind, "*"), count=5_000):
                batch.append(key)
                if len(batch) >= 5_000:
                    n += self._r.delete(*batch)
                    batch = []
            if batch:
                n += self._r.delete(*batch)
        return n

    def reset_watermarks(self, accounts: list[str], batch: int = 5_000) -> None:
        for i in range(0, len(accounts), batch):
            p = self._r.pipeline(transaction=False)
            for a in accounts[i : i + batch]:
                p.hset(self._k("acct", a), "wm", "")
            p.execute()

    def load_accounts(self, mapping: dict[str, dict[str, str]], batch: int = 5_000) -> None:
        items = list(mapping.items())
        for i in range(0, len(items), batch):
            p = self._r.pipeline(transaction=False)
            for a, m in items[i : i + batch]:
                p.hset(self._k("acct", a), mapping=m)
            p.execute()

    def load_windows(self, windows: dict[str, dict[str, int]], batch: int = 5_000) -> None:
        items = list(windows.items())
        for i in range(0, len(items), batch):
            p = self._r.pipeline(transaction=False)
            for a, m in items[i : i + batch]:
                p.zadd(self._k("win", a), m)
            p.execute()

    def load_edges(self, members: dict[int, set[str]], batch: int = 2_000) -> None:
        items = list(members.items())
        for i in range(0, len(items), batch):
            p = self._r.pipeline(transaction=False)
            for s, m in items[i : i + batch]:
                p.sadd(self._k("edge", s), *m)
            p.execute()


def _text(h: dict) -> dict[str, str]:
    return {(k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
            for k, v in h.items()}  # fmt: skip


# --- the seed: the stream starts from the train_end snapshot --------------------------
def edges_frame(transactions: pl.LazyFrame, as_of: dt.datetime) -> pl.DataFrame:
    """Every distinct (from, to) pair seen strictly before `as_of`."""
    return (
        transactions.filter(pl.col("timestamp") < as_of)
        .select("from_account", "to_account")
        .unique()
        .sort("from_account", "to_account")
        .collect()
    )


def window_members(recent: pl.DataFrame) -> dict[str, dict[str, int]]:
    """Seeded 24 h windows; members are named `seed:{n}` (stream members are source rows)."""
    windows: dict[str, dict[str, int]] = defaultdict(dict)
    for n, (a, ts) in enumerate(recent.select("account", "timestamp").iter_rows()):
        windows[a][f"seed:{n}"] = epoch(ts)
    return windows


def edge_members(edges: pl.DataFrame) -> dict[int, set[str]]:
    members: dict[int, set[str]] = defaultdict(set)
    for f, t in edges.select("from_account", "to_account").iter_rows():
        pair = edge(f, t)
        members[shard(pair)].add(pair)
    return members


def seed_stream(store, accounts: list[str], recent: pl.DataFrame, edges: pl.DataFrame) -> None:
    """Reset the stream to the snapshot: old windows/edges/pending gone, seed loaded,
    watermarks cleared (every stream event is after the snapshot)."""
    store.clear_stream()
    store.load_windows(window_members(recent))
    store.load_edges(edge_members(edges))
    store.reset_watermarks(accounts)


def seed(store, states: pl.DataFrame, recent: pl.DataFrame, edges: pl.DataFrame,
         as_of: dt.datetime) -> dict[str, int]:  # fmt: skip
    """Accounts + the stream seed in one go (tests, the offline proof)."""
    accounts = {a: _encode(st) for a, st in states_from_frame(states, as_of).items()}
    store.load_accounts(accounts)
    seed_stream(store, list(accounts), recent, edges)
    return {"accounts": len(accounts), "window_sends": recent.height, "edges": edges.height}
