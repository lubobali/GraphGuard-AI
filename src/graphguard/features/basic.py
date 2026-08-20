"""Point-in-time features taken from the transaction row itself.

Every value here comes from the row being scored, so none of it can contain
information from the future. That is why this module has no time-cutoff
argument: there is no history being aggregated. Anything that *does* aggregate
history lives in `graph.py` and takes an explicit `as_of`.
"""

from __future__ import annotations

import polars as pl


def build_basic_features(transactions: pl.LazyFrame) -> pl.LazyFrame:
    """Add row-level features. No history, no aggregation, no leakage surface."""
    return transactions.with_columns(
        # Time of day and day of week. Laundering hops in this data are spread
        # across the clock, but ordinary business traffic is not, so the
        # contrast is informative.
        pl.col("timestamp").dt.hour().alias("hour"),
        pl.col("timestamp").dt.weekday().alias("weekday"),
        # Amounts span 0.01 to billions. On the raw scale a tree spends every
        # split separating the giants; log1p keeps 0.01 finite and non-null.
        pl.col("amount_paid").log1p().alias("log_amount"),
        # Sent and received differ when currencies do. The gap is where FX
        # sits, and laundering chains hop currencies deliberately.
        (
            pl.when(pl.col("amount_paid") > 0)
            .then(pl.col("amount_received") / pl.col("amount_paid"))
            .otherwise(1.0)
        ).alias("amount_ratio"),
        (pl.col("receiving_currency") != pl.col("payment_currency"))
        .cast(pl.Int8)
        .alias("is_cross_currency"),
        # Reinvestment rows point an account at itself and are very common in
        # this dataset; they are structurally different from a real transfer.
        (pl.col("from_account") == pl.col("to_account")).cast(pl.Int8).alias("is_self_transfer"),
        (pl.col("from_bank") == pl.col("to_bank")).cast(pl.Int8).alias("is_same_bank"),
    )
