"""Build the transaction graph as time-respecting snapshots.

Leakage contract rule 2: the graph at time T contains only edges before T.
Building one graph over the whole history and then splitting it is leakage even
though the split file still says the right thing -- the embeddings would carry
future structure into every earlier prediction, and nothing downstream would
show it.

**Snapshots, not one static graph.** Transactions are bucketed by day. A
transaction in day *d* is scored using a graph built only from days before *d*.
That is coarser than a fully continuous temporal model, and the coarseness is
stated rather than hidden: within a single day, a transaction does not see its
same-day neighbours. That direction is safe -- it withholds information rather
than leaking it.

Nodes are accounts, edges are transfers, direction is payer to payee.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import polars as pl
import torch


@dataclass(frozen=True)
class Snapshot:
    """A graph as of one instant. `node_ids[i]` is the account at index i."""

    node_ids: list[str]
    edge_index: torch.Tensor  # [2, num_edges], long
    edge_attr: torch.Tensor  # [num_edges, 1], log amount
    edge_time: torch.Tensor  # [num_edges], unix seconds

    @property
    def num_nodes(self) -> int:
        return len(self.node_ids)

    @property
    def num_edges(self) -> int:
        return int(self.edge_index.shape[1])


def snapshot_index(transactions: pl.LazyFrame, origin: dt.datetime | None = None) -> pl.LazyFrame:
    """Add a `snapshot` column: the day bucket a transaction belongs to."""
    start = origin or transactions.select(pl.col("timestamp").min()).collect().item()
    return transactions.with_columns(
        ((pl.col("timestamp") - pl.lit(start)).dt.total_days()).cast(pl.Int32).alias("snapshot")
    )


def build_snapshot(transactions: pl.LazyFrame, as_of: dt.datetime) -> Snapshot:
    """Graph of everything strictly before `as_of`.

    `as_of` is not optional and is not a filter applied afterwards: the frame is
    cut first, so no later edge can reach the node mapping either.
    """
    past = (
        transactions.filter(pl.col("timestamp") < as_of)
        .select("timestamp", "from_account", "to_account", "amount_paid")
        .sort("timestamp")
        .collect()
    )

    if past.height == 0:
        empty = torch.empty((2, 0), dtype=torch.long)
        return Snapshot([], empty, torch.empty((0, 1)), torch.empty(0))

    # Node ids in first-appearance order, so the mapping is deterministic.
    accounts = pl.concat(
        [
            past.select(pl.col("from_account").alias("a")),
            past.select(pl.col("to_account").alias("a")),
        ]
    )["a"]
    node_ids = list(dict.fromkeys(accounts.to_list()))
    index = {account: i for i, account in enumerate(node_ids)}

    src = torch.tensor([index[a] for a in past["from_account"].to_list()], dtype=torch.long)
    dst = torch.tensor([index[a] for a in past["to_account"].to_list()], dtype=torch.long)

    edge_attr = torch.tensor(
        past.select(pl.col("amount_paid").log1p()).to_numpy(), dtype=torch.float32
    )
    edge_time = torch.tensor(
        past.select(pl.col("timestamp").dt.timestamp("ms") / 1000).to_numpy().ravel(),
        dtype=torch.float64,
    )

    return Snapshot(node_ids, torch.stack([src, dst]), edge_attr, edge_time)
