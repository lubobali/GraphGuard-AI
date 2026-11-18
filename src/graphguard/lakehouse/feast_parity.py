"""Feast's online values against the store the scorer actually serves (S5.6e).

    just feast-parity

Reads `lakehouse/feast/online_export.parquet` (written by `featurestore/run.py` in
Feast's own environment) and the live Redis store (read-only), and compares every
account, feature by feature: counts must be equal integers, money equal floats bit
for bit, timestamps the same instant. The two projects never import each other;
they meet in this file.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from dataclasses import dataclass, field

import polars as pl

from graphguard.config import REPO_ROOT
from graphguard.serving.online_features import AccountState

EXPORT = REPO_ROOT / "lakehouse" / "feast" / "online_export.parquet"
INTS = ("n_sent", "n_received", "distinct_out", "distinct_in", "sent_last_24h")
FLOATS = ("amount_sent", "amount_received")
TIMES = ("last_seen", "last_sent")


@dataclass
class Parity:
    accounts: int = 0
    missing_in_ours: int = 0
    missing_in_feast: int = 0
    differences: dict[str, int] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)

    @property
    def identical(self) -> bool:
        return not (self.missing_in_ours or self.missing_in_feast or any(self.differences.values()))


def _naive_utc(v: dt.datetime | None) -> dt.datetime | None:
    if v is None:
        return None
    return v.astimezone(dt.UTC).replace(tzinfo=None) if v.tzinfo else v


def compare(feast_rows: list[dict], ours: dict[str, AccountState | None]) -> Parity:
    """Pure: Feast's rows (as exported) against our states, keyed by account."""
    p = Parity(accounts=len(feast_rows), differences={c: 0 for c in (*INTS, *FLOATS, *TIMES)})
    for row in feast_rows:
        mine = ours.get(row["account"])
        if mine is None:
            p.missing_in_ours += 1
            continue
        if all(row.get(c) is None for c in (*INTS, *FLOATS)):
            p.missing_in_feast += 1
            continue
        for c in INTS + FLOATS:
            if row[c] != getattr(mine, c):  # exact: ints as ints, floats bit for bit
                p.differences[c] += 1
                if len(p.examples) < 5:
                    p.examples.append(
                        f"{row['account']}.{c}: feast={row[c]!r} ours={getattr(mine, c)!r}"
                    )
        for c in TIMES:
            if _naive_utc(row[c]) != getattr(mine, c):
                p.differences[c] += 1
                if len(p.examples) < 5:
                    p.examples.append(
                        f"{row['account']}.{c}: feast={row[c]!r} ours={getattr(mine, c)!r}"
                    )
    return p


def main() -> int:
    from graphguard.serving.store import RedisFeatureStore

    feast_rows = pl.read_parquet(EXPORT).to_dicts()
    store = RedisFeatureStore()
    ours: dict[str, AccountState | None] = {}
    accounts = [r["account"] for r in feast_rows]
    for i in range(0, len(accounts), 20_000):
        ours.update(store.get_many(accounts[i : i + 20_000]))
    p = compare(feast_rows, ours)
    print(json.dumps({**p.__dict__, "identical": p.identical}, indent=2, default=str))
    return 0 if p.identical else 1


if __name__ == "__main__":
    sys.exit(main())
