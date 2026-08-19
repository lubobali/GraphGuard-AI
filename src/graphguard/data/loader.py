"""Load the IBM AMLworld transactions file.

The raw CSV has two columns both named "Account" -- the sender's and the
receiver's. Reading it without care keeps only one, which would silently
destroy every edge in the graph. So the columns are renamed positionally on
read, and the mapping below is the single place that knowledge lives.

Everything returns a LazyFrame. At 5M rows that is not strictly necessary, but
the same code has to survive HI-Medium at 32M, and lazy scanning is what makes
that possible without rewriting it later.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

# Positional mapping from the raw header to canonical names. Order matters:
# this is applied to the columns as they appear in the file.
CANONICAL_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "from_bank",
    "from_account",
    "to_bank",
    "to_account",
    "amount_received",
    "receiving_currency",
    "amount_paid",
    "payment_currency",
    "payment_format",
    "is_laundering",
)

# Bank and account IDs look numeric but are identifiers with leading zeros
# ("010", "8000EBD30"). Coercing them to integers would merge distinct accounts.
_STRING_COLUMNS = ("from_bank", "from_account", "to_bank", "to_account")

TIMESTAMP_FORMAT = "%Y/%m/%d %H:%M"


def load_transactions(path: str | Path) -> pl.LazyFrame:
    """Scan the transactions CSV into a LazyFrame with canonical column names."""
    schema_overrides = dict.fromkeys(_STRING_COLUMNS, pl.String)

    return pl.scan_csv(
        path,
        new_columns=list(CANONICAL_COLUMNS),
        schema_overrides=schema_overrides,
        has_header=True,
    ).with_columns(pl.col("timestamp").str.to_datetime(TIMESTAMP_FORMAT))


def summarise(lf: pl.LazyFrame) -> dict:
    """Shape, date range and class balance -- the Phase 0 gate's three numbers."""
    stats = lf.select(
        pl.len().alias("n_transactions"),
        pl.col("timestamp").min().alias("date_min"),
        pl.col("timestamp").max().alias("date_max"),
        pl.col("is_laundering").sum().alias("n_laundering"),
    ).collect()

    n_accounts = (
        lf.select(pl.col("from_account").alias("a"))
        .merge_sorted(lf.select(pl.col("to_account").alias("a")), key="a")
        .select(pl.col("a").n_unique())
        .collect()
        .item()
    )

    n_transactions = int(stats["n_transactions"][0])
    n_laundering = int(stats["n_laundering"][0])

    return {
        "n_transactions": n_transactions,
        "n_accounts": int(n_accounts),
        "date_min": stats["date_min"][0],
        "date_max": stats["date_max"][0],
        "n_laundering": n_laundering,
        "laundering_rate": (n_laundering / n_transactions) if n_transactions else 0.0,
    }
