"""Data contracts for each stage of the feature pipeline.

A column that quietly changes type, or a null rate that jumps, does not fail
anything -- it just trains a slightly worse model, and nothing downstream says
so. These schemas turn that into a loud failure.

They are asserted as tests as well as applied at runtime, because a schema
nobody exercises drifts out of date and becomes decoration.
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl
from pandera.errors import SchemaError

# Account and bank identifiers have leading zeros ("010", "8000EBD30"). As
# integers they would collide, silently merging distinct accounts, so the type
# itself is part of the contract.
RawTransactions = pa.DataFrameSchema(
    {
        "timestamp": pa.Column(pl.Datetime, nullable=False),
        "from_bank": pa.Column(pl.String, nullable=False),
        "from_account": pa.Column(pl.String, nullable=False),
        "to_bank": pa.Column(pl.String, nullable=False),
        "to_account": pa.Column(pl.String, nullable=False),
        "amount_received": pa.Column(pl.Float64, pa.Check.ge(0), nullable=False),
        "amount_paid": pa.Column(pl.Float64, pa.Check.ge(0), nullable=False),
        "receiving_currency": pa.Column(pl.String, nullable=False),
        "payment_currency": pa.Column(pl.String, nullable=False),
        "payment_format": pa.Column(pl.String, nullable=False),
        "is_laundering": pa.Column(None, pa.Check.isin([0, 1]), nullable=False),
    },
    strict=False,  # extra columns are allowed; missing or wrong ones are not
    name="raw_transactions",
)

# History counts are the off-by-one risk: `cum_count() - 1` done wrong yields
# -1, which is impossible and would otherwise train silently.
# ge(0) also rejects NaN: every comparison against NaN is false, so a NaN row
# fails the check rather than sliding through. That is deliberate -- log(0) and
# 0/0 both produce NaN and a tree will happily train on it.
_non_negative = pa.Check.ge(0)

# Integer widths vary across the pipeline (Int8 from dt.hour(), UInt32 from
# cum_count), so integer columns are validated on their values rather than on
# an exact dtype. The string identifier columns above DO pin dtype, because
# that is where a wrong type silently merges distinct accounts.

Features = pa.DataFrameSchema(
    {
        "hour": pa.Column(None, pa.Check.in_range(0, 23), nullable=False),
        "weekday": pa.Column(None, pa.Check.in_range(1, 7), nullable=False),
        "log_amount": pa.Column(pl.Float64, _non_negative, nullable=False),
        "amount_ratio": pa.Column(pl.Float64, _non_negative, nullable=False),
        "is_cross_currency": pa.Column(None, pa.Check.isin([0, 1]), nullable=False),
        "is_self_transfer": pa.Column(None, pa.Check.isin([0, 1]), nullable=False),
        "is_same_bank": pa.Column(None, pa.Check.isin([0, 1]), nullable=False),
        "sender_n_sent_before": pa.Column(None, _non_negative, nullable=False),
        "sender_amount_sent_before": pa.Column(pl.Float64, _non_negative),
        "sender_distinct_out_before": pa.Column(None, _non_negative, nullable=False),
        "sender_sent_last_24h": pa.Column(None, _non_negative, nullable=False),
        "receiver_n_received_before": pa.Column(None, _non_negative, nullable=False),
        "receiver_amount_received_before": pa.Column(pl.Float64, _non_negative),
        "receiver_distinct_in_before": pa.Column(None, _non_negative, nullable=False),
        "in_out_ratio_before": pa.Column(pl.Float64, _non_negative, nullable=False),
        "is_laundering": pa.Column(None, pa.Check.isin([0, 1]), nullable=False),
    },
    strict=False,
    name="features",
)


def validate_raw_transactions(df: pl.DataFrame) -> pl.DataFrame:
    """Check the raw file matches its contract. Raises SchemaError if not."""
    return RawTransactions.validate(df)


def validate_features(df: pl.DataFrame) -> pl.DataFrame:
    """Check the feature frame matches its contract. Raises SchemaError if not."""
    return Features.validate(df)


__all__ = [
    "Features",
    "RawTransactions",
    "SchemaError",
    "validate_features",
    "validate_raw_transactions",
]
