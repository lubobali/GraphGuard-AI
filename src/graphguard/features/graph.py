"""Graph features for the tabular baseline, computed point-in-time.

This is the module leakage contract rule 3 exists for. Every feature here is an
aggregate over an account's past, and the failure mode is that "past" quietly
becomes "the whole dataset". That mistake looks like correct code and produces
a strong model, which is why the leakage guard blocks any builder in this
package that does not take an explicit `as_of`.

Two separate protections, both needed:

1. **`as_of` bounds the frame.** Nothing at or after the cutoff enters the
   computation at all. When building training features, `as_of` is the training
   window's end, so no validation or test row can contribute.

2. **Every aggregate is expanding and excludes the current row.** Within the
   window, a row sees only rows strictly before it, per account. An account's
   first transfer therefore sees a history of zero, not one. Off-by-one here
   would let every row see itself, which is leakage that looks like signal.

Giving the tabular model graph information is deliberate. PLAN.md: "The baseline
gets graph information too. This is the fair fight." A GNN that only beats a
model denied graph features has proved nothing.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

VELOCITY_HOURS = 24


def build_account_history_features(
    transactions: pl.LazyFrame,
    as_of: dt.datetime,
) -> pl.LazyFrame:
    """Add per-account history features, using only each row's own past.

    `as_of` is a hard upper bound: rows at or after it are dropped before
    anything is computed.
    """
    df = transactions.filter(pl.col("timestamp") < as_of).sort("timestamp").with_row_index("_row")

    # --- sender side --------------------------------------------------------
    # cum_count over the account, minus this row, is "how many before me".
    sender = df.with_columns(
        (pl.col("_row").cum_count().over("from_account") - 1).alias("sender_n_sent_before"),
        (pl.col("amount_paid").cum_sum().over("from_account") - pl.col("amount_paid")).alias(
            "sender_amount_sent_before"
        ),
        # A counterparty is new the first time this (sender, receiver) pair is
        # seen. Cumulative sum of "is new" is the distinct count so far.
        (pl.col("_row").cum_count().over(["from_account", "to_account"]) == 1)
        .cast(pl.Int64)
        .alias("_is_new_counterparty"),
        pl.col("timestamp").shift(1).over("from_account").alias("_prev_send"),
    ).with_columns(
        (
            pl.col("_is_new_counterparty").cum_sum().over("from_account")
            - pl.col("_is_new_counterparty")
        ).alias("sender_distinct_out_before"),
        (pl.col("timestamp") - pl.col("_prev_send"))
        .dt.total_seconds()
        .alias("sender_seconds_since_last_send"),
    )

    # --- receiver side ------------------------------------------------------
    received = sender.with_columns(
        (pl.col("_row").cum_count().over("to_account") - 1).alias("receiver_n_received_before"),
        (pl.col("amount_paid").cum_sum().over("to_account") - pl.col("amount_paid")).alias(
            "receiver_amount_received_before"
        ),
        (pl.col("_row").cum_count().over(["to_account", "from_account"]) == 1)
        .cast(pl.Int64)
        .alias("_is_new_source"),
    ).with_columns(
        (pl.col("_is_new_source").cum_sum().over("to_account") - pl.col("_is_new_source")).alias(
            "receiver_distinct_in_before"
        ),
    )

    # --- velocity -----------------------------------------------------------
    # Sends in the trailing 24h, excluding the current row. Computed as
    #   (count before now) - (count as at now minus 24h)
    # via an as-of join rather than a rolling group-by: an account can have two
    # transfers at the same timestamp in this data, and joining a grouped
    # rolling result back on (account, timestamp) would fan out on the tie.
    counted = received.with_columns(
        pl.col("_row").cum_count().over("from_account").alias("_cum_sent"),
        (pl.col("timestamp") - pl.duration(hours=VELOCITY_HOURS)).alias("_window_start"),
    )

    at_window_start = (
        counted.select("from_account", "timestamp", "_cum_sent")
        .sort("timestamp")
        .rename({"_cum_sent": "_cum_at_window_start"})
    )

    velocity = (
        counted.sort("_window_start")
        .join_asof(
            at_window_start,
            left_on="_window_start",
            right_on="timestamp",
            by="from_account",
            strategy="backward",
        )
        .with_columns(
            (pl.col("sender_n_sent_before") - pl.col("_cum_at_window_start").fill_null(0)).alias(
                "sender_sent_last_24h"
            )
        )
        .drop("_cum_sent", "_window_start", "_cum_at_window_start")
    )

    # --- ratios -------------------------------------------------------------
    # +1 keeps this finite for accounts with no history yet.
    out = velocity.with_columns(
        ((pl.col("receiver_n_received_before") + 1) / (pl.col("sender_n_sent_before") + 1)).alias(
            "in_out_ratio_before"
        ),
    )

    return out.drop("_row", "_is_new_counterparty", "_is_new_source", "_prev_send")
