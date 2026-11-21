"""Data contracts, one per lakehouse layer, asserted as tests (S5.6a).

Bronze and silver reuse the raw-transaction contract: silver is bronze with rows
removed, never with columns reshaped. Gold gets its own contracts, because a
negative count or a null account in gold goes straight into Redis and from there
into every score.
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from graphguard.features.schemas import RawTransactions

BronzeTransactions = RawTransactions
SilverTransactions = RawTransactions

_non_negative = pa.Check.ge(0)

GoldAccountFeatures = pa.DataFrameSchema(
    {
        "account": pa.Column(pl.String, nullable=False, unique=False),
        "as_of": pa.Column(pl.Datetime, nullable=False),
        "n_sent": pa.Column(pl.Int64, _non_negative, nullable=False),
        "n_received": pa.Column(pl.Int64, _non_negative, nullable=False),
        "amount_sent": pa.Column(pl.Float64, _non_negative, nullable=False),
        "amount_received": pa.Column(pl.Float64, _non_negative, nullable=False),
        "distinct_out": pa.Column(pl.Int64, _non_negative, nullable=False),
        "distinct_in": pa.Column(pl.Int64, _non_negative, nullable=False),
        "sent_last_24h": pa.Column(pl.Int64, _non_negative, nullable=False),
        # Null means "never": an account that has never sent has no last_sent.
        "last_seen": pa.Column(pl.Datetime, nullable=True),
        "last_sent": pa.Column(pl.Datetime, nullable=True),
    },
    strict=True,
    name="gold_account_features",
)

# One row per send in (as_of - 24h, as_of): the stream rolls the 24 h count forward from
# these, because a stored count cannot drop sends as they age (S6.2).
GoldRecentSends = pa.DataFrameSchema(
    {
        "account": pa.Column(pl.String, nullable=False),
        "timestamp": pa.Column(pl.Datetime, nullable=False),
        "as_of": pa.Column(pl.Datetime, nullable=False),
    },
    strict=True,
    name="gold_recent_sends",
)

GoldEdges = pa.DataFrameSchema(
    {
        "from_account": pa.Column(pl.String, nullable=False),
        "to_account": pa.Column(pl.String, nullable=False),
        "as_of": pa.Column(pl.Datetime, nullable=False),
    },
    strict=True,
    unique=["from_account", "to_account", "as_of"],
    name="gold_edges",
)

GoldLabels = pa.DataFrameSchema(
    {
        # The transaction key: the row's position in the source file.
        "source_row": pa.Column(pl.Int64, _non_negative, nullable=False, unique=True),
        "timestamp": pa.Column(pl.Datetime, nullable=False),
        "from_account": pa.Column(pl.String, nullable=False),
        "to_account": pa.Column(pl.String, nullable=False),
        "amount_paid": pa.Column(pl.Float64, _non_negative, nullable=False),
        "is_laundering": pa.Column(None, pa.Check.isin([0, 1]), nullable=False),
        # Set by Phase 6's label-delay policy. Null until then: unknown, not "immediately".
        "label_known_at": pa.Column(pl.Datetime, nullable=True),
    },
    strict=True,
    name="gold_labels",
)
