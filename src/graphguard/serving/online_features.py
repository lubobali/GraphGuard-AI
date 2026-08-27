"""What the online store holds, and how a scoring request is assembled.

**The problem.** Training computes an account's history by scanning three
million rows. A live request has fifty milliseconds. So the history is
precomputed into a small per-account record, stored, and looked up.

**The danger.** The stored record must produce exactly the numbers the training
path produced. If the two drift, the deployed model behaves differently from
the one that was evaluated and nothing fails -- the scores just quietly become
wrong. That is train/serve skew, and it is the reason this module exists as one
shared definition rather than as a second implementation.

**Cold accounts are a first-class case, not an error.** 515,080 accounts appear
across 18 days and new ones arrive constantly. An account nobody has seen gets a
state of all zeros, which is honest: nothing is known about it yet. It is still
scoreable, because refusing to score a new customer is not an option a bank has.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import polars as pl

# The columns the production model consumes. Named to match the training
# feature names exactly, because a mismatch here is silent.
ACCOUNT_FEATURES: tuple[str, ...] = (
    "sender_n_sent_before",
    "sender_amount_sent_before",
    "sender_distinct_out_before",
    "sender_sent_last_24h",
    "sender_seconds_since_last_send",
    "receiver_n_received_before",
    "receiver_amount_received_before",
    "receiver_distinct_in_before",
    "in_out_ratio_before",
)


@dataclass(frozen=True)
class AccountState:
    """One account's history, as of some instant. This is what Redis holds."""

    account: str
    n_sent: int
    n_received: int
    amount_sent: float
    amount_received: float
    distinct_out: int
    distinct_in: int
    last_seen: dt.datetime | None
    # The model uses both of these, so the store must carry them. Holding a
    # feature at zero because serving forgot to store it is not staleness, it
    # is a missing feature, and it looks exactly like staleness in a metric.
    last_sent: dt.datetime | None = None
    sent_last_24h: int = 0
    # When this state was computed. Staleness is measured against this, not
    # against the account's last activity: those are different questions, and
    # conflating them means monitoring reports account recency while believing
    # it is reporting store freshness.
    materialised_at: dt.datetime | None = None
    is_cold: bool = False

    @classmethod
    def cold(cls, account: str) -> AccountState:
        """An account the store has never seen. Zeros, not an error."""
        return cls(
            account=account,
            n_sent=0,
            n_received=0,
            amount_sent=0.0,
            amount_received=0.0,
            distinct_out=0,
            distinct_in=0,
            last_seen=None,
            last_sent=None,
            sent_last_24h=0,
            materialised_at=None,
            is_cold=True,
        )


def build_account_states(transactions: pl.LazyFrame, as_of: dt.datetime) -> dict[str, AccountState]:
    """Materialise every account's state from history strictly before `as_of`.

    This is the batch job that fills the online store. `as_of` is a hard bound,
    applied before any aggregation, so a later transfer cannot reach the state.
    """
    past = transactions.filter(pl.col("timestamp") < as_of)

    window_start = as_of - dt.timedelta(hours=24)

    sent = (
        past.group_by("from_account")
        .agg(
            pl.len().alias("n_sent"),
            pl.col("amount_paid").sum().alias("amount_sent"),
            pl.col("to_account").n_unique().alias("distinct_out"),
            pl.col("timestamp").max().alias("last_sent"),
            (pl.col("timestamp") >= window_start).sum().alias("sent_last_24h"),
        )
        .rename({"from_account": "account"})
    )
    received = (
        past.group_by("to_account")
        .agg(
            pl.len().alias("n_received"),
            pl.col("amount_paid").sum().alias("amount_received"),
            pl.col("from_account").n_unique().alias("distinct_in"),
            pl.col("timestamp").max().alias("last_received"),
        )
        .rename({"to_account": "account"})
    )

    joined = (
        sent.join(received, on="account", how="full", coalesce=True)
        .with_columns(
            pl.col("n_sent").fill_null(0),
            pl.col("n_received").fill_null(0),
            pl.col("amount_sent").fill_null(0.0),
            pl.col("amount_received").fill_null(0.0),
            pl.col("distinct_out").fill_null(0),
            pl.col("distinct_in").fill_null(0),
            pl.col("sent_last_24h").fill_null(0),
        )
        .with_columns(
            pl.max_horizontal("last_sent", "last_received").alias("last_seen"),
        )
        .collect()
    )

    return {
        row["account"]: AccountState(
            account=row["account"],
            n_sent=int(row["n_sent"]),
            n_received=int(row["n_received"]),
            amount_sent=float(row["amount_sent"]),
            amount_received=float(row["amount_received"]),
            distinct_out=int(row["distinct_out"]),
            distinct_in=int(row["distinct_in"]),
            last_seen=row["last_seen"],
            last_sent=row["last_sent"],
            sent_last_24h=int(row["sent_last_24h"]),
            materialised_at=as_of,
        )
        for row in joined.iter_rows(named=True)
    }


def to_model_row(
    *,
    sender: AccountState,
    receiver: AccountState,
    timestamp: dt.datetime,
    amount_paid: float,
    amount_received: float,
    from_bank: str,
    to_bank: str,
    payment_currency_code: float = 0.0,
) -> dict[str, float]:
    """Assemble one scoring row from two stored states plus the fresh transfer.

    The transaction's own fields are computed here rather than looked up,
    because they arrive with the request and have no history.
    """
    import math

    return {
        # from the two stored states
        "sender_n_sent_before": float(sender.n_sent),
        "sender_amount_sent_before": float(sender.amount_sent),
        "sender_distinct_out_before": float(sender.distinct_out),
        "sender_sent_last_24h": float(sender.sent_last_24h),
        # Null when the account has never sent. XGBoost treats NaN as missing
        # and learns a direction for it, which is what training saw too.
        "sender_seconds_since_last_send": (
            (timestamp - sender.last_sent).total_seconds()
            if sender.last_sent is not None
            else float("nan")
        ),
        "receiver_n_received_before": float(receiver.n_received),
        "receiver_amount_received_before": float(receiver.amount_received),
        "receiver_distinct_in_before": float(receiver.distinct_in),
        # +1 keeps this finite for an account with no history yet
        "in_out_ratio_before": (receiver.n_received + 1) / (sender.n_sent + 1),
        # from the request itself
        "hour": float(timestamp.hour),
        "weekday": float(timestamp.isoweekday()),
        "log_amount": math.log1p(amount_paid),
        "amount_ratio": (amount_received / amount_paid) if amount_paid > 0 else 1.0,
        "is_same_bank": float(from_bank == to_bank),
        "payment_currency_code": float(payment_currency_code),
    }
