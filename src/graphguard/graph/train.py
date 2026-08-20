"""Train the GNN on day snapshots and score it through the same evaluate().

**How a day is processed.** For day *d*: build the graph from every transfer
before *d* began, add the day's own accounts as featureless nodes, then score
the day's transactions as edges over that past graph. The day's transactions
are never part of the message-passing graph, so a transaction cannot see itself
or its same-day neighbours.

**Neighbour sampling.** LinkNeighborLoader samples a small subgraph around each
scored pair rather than running message passing over the full graph. At 2.5M
edges a full-batch forward would not fit in the memory budget this box allows,
and sampling is what the plan calls for.

**Imbalance.** BCE with `pos_weight = n_negative / n_positive`, the same ratio
XGBoost got as `scale_pos_weight`. Chosen for parity rather than by default:
giving the GNN focal loss and the baseline a plain reweighting would make any
difference between them partly a difference of loss function, not of model.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import polars as pl
import torch
from torch_geometric.data import Data
from torch_geometric.loader import LinkNeighborLoader

from graphguard.graph.build import build_snapshot
from graphguard.graph.model import NODE_FEATURE_DIM, EdgeScorer, node_features

# Default edge features. The runner can pass a wider set -- see run_gnn, which
# hands the GNN exactly the columns the tabular baseline received, so that the
# comparison isolates what graph structure adds rather than measuring who got
# better feature engineering.
EDGE_FEATURE_COLUMNS = ("log_amount", "hour", "is_same_bank", "amount_ratio")


def _day_bounds(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime(day.year, day.month, day.day)
    return start, start + dt.timedelta(days=1)


def _pairs_and_features(
    day_df: pl.DataFrame, node_index: dict[str, int], edge_columns: tuple[str, ...]
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    src = torch.tensor([node_index[a] for a in day_df["from_account"].to_list()], dtype=torch.long)
    dst = torch.tensor([node_index[a] for a in day_df["to_account"].to_list()], dtype=torch.long)
    feats = torch.tensor(
        day_df.select(edge_columns).fill_null(0).cast(pl.Float32).to_numpy(),
        dtype=torch.float32,
    )
    labels = torch.tensor(day_df["is_laundering"].to_numpy(), dtype=torch.float32)
    return torch.stack([src, dst]), feats, labels


def _loader(
    snapshot,
    day_df: pl.DataFrame,
    batch_size: int,
    num_neighbors: list[int],
    shuffle: bool,
    edge_columns: tuple[str, ...],
):
    node_index = {a: i for i, a in enumerate(snapshot.node_ids)}
    pairs, feats, labels = _pairs_and_features(day_df, node_index, edge_columns)

    x = node_features(snapshot.edge_index, snapshot.edge_attr, snapshot.num_nodes)
    data = Data(x=x, edge_index=snapshot.edge_index)

    return (
        LinkNeighborLoader(
            data,
            num_neighbors=num_neighbors,
            edge_label_index=pairs,
            edge_label=torch.arange(pairs.shape[1], dtype=torch.long),  # row ids
            batch_size=batch_size,
            shuffle=shuffle,
        ),
        feats,
        labels,
    )


def run_epoch(
    model: EdgeScorer,
    history: pl.LazyFrame,
    targets: pl.LazyFrame,
    days: list[dt.date],
    *,
    optimizer=None,
    batch_size: int = 8192,
    num_neighbors: tuple[int, ...] = (15, 10),
    pos_weight: float = 1.0,
    max_rows_per_day: int | None = None,
    seed: int = 42,
    edge_columns: tuple[str, ...] = EDGE_FEATURE_COLUMNS,
) -> tuple[float, np.ndarray, np.ndarray]:
    """One pass over the given days. Trains if `optimizer` is given.

    `history` is what the graph is built from -- the full record, including
    earlier splits, because a validation row's past legitimately includes the
    training window. `targets` is what gets scored, and only that.

    Keeping them separate is not tidiness. A split boundary falls in the middle
    of a day here, so walking whole days over one frame would score training
    rows as if they were validation, and the length mismatch would be papered
    over by truncation rather than raised. Scores and labels would then be
    misaligned and every metric would be fiction.

    Returns (mean loss, scores, labels) aligned to `targets` in day then
    timestamp order.
    """
    training = optimizer is not None
    model.train(training)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight))

    all_scores: list[np.ndarray] = []
    all_labels: list[np.ndarray] = []
    losses: list[float] = []

    for day in days:
        start, end = _day_bounds(day)
        day_df = (
            targets.filter((pl.col("timestamp") >= start) & (pl.col("timestamp") < end))
            .sort("timestamp")
            .collect()
        )
        if day_df.height == 0:
            continue

        if training and max_rows_per_day and day_df.height > max_rows_per_day:
            # Keep every positive; subsample negatives. Training only -- the
            # evaluation path never subsamples, or the metric would be fiction.
            pos = day_df.filter(pl.col("is_laundering") == 1)
            neg = day_df.filter(pl.col("is_laundering") == 0).sample(
                n=max_rows_per_day - pos.height, seed=seed
            )
            day_df = pl.concat([pos, neg]).sort("timestamp")

        accounts = list(
            dict.fromkeys(day_df["from_account"].to_list() + day_df["to_account"].to_list())
        )
        snapshot = build_snapshot(history, as_of=start, extra_accounts=accounts)

        loader, feats, labels = _loader(
            snapshot,
            day_df,
            batch_size,
            list(num_neighbors),
            shuffle=training,
            edge_columns=edge_columns,
        )

        day_scores = np.zeros(day_df.height, dtype=np.float32)

        for batch in loader:
            rows = batch.edge_label  # original row ids for this batch
            pairs = batch.edge_label_index.T

            logits = model(batch.x, batch.edge_index, pairs, feats[rows])
            loss = loss_fn(logits, labels[rows])

            if training:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

            losses.append(float(loss.detach()))
            day_scores[rows.numpy()] = torch.sigmoid(logits.detach()).numpy()

        all_scores.append(day_scores)
        all_labels.append(labels.numpy())

    if not all_scores:
        return 0.0, np.array([]), np.array([])

    return (
        float(np.mean(losses)) if losses else 0.0,
        np.concatenate(all_scores),
        np.concatenate(all_labels),
    )


def make_model(hidden: int, dropout: float, seed: int, edge_dim: int | None = None) -> EdgeScorer:
    torch.manual_seed(seed)
    return EdgeScorer(
        in_channels=NODE_FEATURE_DIM,
        hidden=hidden,
        edge_dim=edge_dim if edge_dim is not None else len(EDGE_FEATURE_COLUMNS),
        dropout=dropout,
    )
