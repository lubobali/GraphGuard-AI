"""Print the dataset's shape, date range and class balance.

This is the command the Phase 0 gate names. It exists so the first thing
anyone learns about the data is measured rather than assumed -- including the
row count and column names, which the dataset's own documentation gets
slightly wrong.
"""

from __future__ import annotations

from graphguard.config import TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions, summarise


def main() -> int:
    if not TRANSACTIONS_FILE.exists():
        print(f"missing: {TRANSACTIONS_FILE}")
        print("run: just data-download")
        return 1

    s = summarise(load_transactions(TRANSACTIONS_FILE))
    span_days = (s["date_max"] - s["date_min"]).days

    print(f"file:          {TRANSACTIONS_FILE.name}")
    print(f"transactions:  {s['n_transactions']:,}")
    print(f"accounts:      {s['n_accounts']:,}")
    print(f"date range:    {s['date_min']}  ->  {s['date_max']}  ({span_days} days)")
    print(f"laundering:    {s['n_laundering']:,}")
    print(f"rate:          {s['laundering_rate']:.5%}  (1 in {round(1 / s['laundering_rate']):,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
