"""GraphSAGE encoder plus an edge scorer.

**Why edges, not nodes.** The evaluation harness scores transactions, so the
model must produce one number per transaction. The encoder learns an embedding
per account from its neighbourhood; the scorer then combines the payer's
embedding, the payee's embedding and the transaction's own features into a
single logit.

**Why GraphSAGE and not GCN.** SAGE is inductive: it learns an aggregation
function over neighbours rather than an embedding table, so it can score an
account it never saw in training. That is not a nicety -- in production a new
customer appears every day, and a transductive model would have nothing to say
about them.

Node features are structural and computed from the snapshot itself, so a node
that appears for the first time still has features (all zeros for a cold
account, which is honest: nothing is known about it yet).
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.nn import SAGEConv

NODE_FEATURE_DIM = 6


def node_features(
    edge_index: torch.Tensor, edge_attr: torch.Tensor, num_nodes: int
) -> torch.Tensor:
    """Structural features per node, all computed from the snapshot itself.

    Out/in degree, out/in value, and distinct counterparties in each direction.
    Distinct counterparties matter separately from raw degree: paying the same
    supplier fifty times is one relationship, while paying fifty accounts once
    each is a fan-out. Raw degree cannot tell those apart, and the difference is
    exactly the laundering shape.

    Given to the GNN deliberately. XGBoost received the equivalent history as
    explicit columns, so withholding it here would make the comparison a
    contest of feature engineering rather than of model class.

    Log-scaled, because degree spans 0 to 169,756 (FINDING-002) and a raw count
    would dominate every other signal.
    """
    x = torch.zeros((num_nodes, NODE_FEATURE_DIM), dtype=torch.float32)
    if edge_index.numel() == 0:
        return x

    src, dst = edge_index[0], edge_index[1]
    amount = edge_attr[:, 0]

    x[:, 0].scatter_add_(0, src, torch.ones_like(amount))  # out-degree
    x[:, 1].scatter_add_(0, dst, torch.ones_like(amount))  # in-degree
    x[:, 2].scatter_add_(0, src, amount)  # value out
    x[:, 3].scatter_add_(0, dst, amount)  # value in

    # Distinct counterparties. Pairs are deduplicated by encoding (src, dst) as
    # a single integer, which is exact as long as the encoding cannot collide.
    pair_id = src * num_nodes + dst
    unique_pairs = torch.unique(pair_id)
    u_src, u_dst = unique_pairs // num_nodes, unique_pairs % num_nodes
    ones = torch.ones(u_src.shape[0], dtype=torch.float32)
    x[:, 4].scatter_add_(0, u_src, ones)  # distinct accounts paid
    x[:, 5].scatter_add_(0, u_dst, ones)  # distinct accounts paid by

    return torch.log1p(x)


class EdgeScorer(nn.Module):
    """Two SAGE layers, then an MLP over (payer, payee, transaction)."""

    def __init__(self, in_channels: int, hidden: int, edge_dim: int, dropout: float = 0.2):
        super().__init__()
        self.conv1 = SAGEConv(in_channels, hidden)
        self.conv2 = SAGEConv(hidden, hidden)
        self.dropout = dropout

        self.head = nn.Sequential(
            nn.Linear(hidden * 2 + edge_dim, hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, 1),
        )

    def encode(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        h = F.relu(self.conv1(x, edge_index))
        h = F.dropout(h, p=self.dropout, training=self.training)
        return self.conv2(h, edge_index)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        pairs: torch.Tensor,
        edge_feats: torch.Tensor,
    ) -> torch.Tensor:
        """`pairs` is [num_scored, 2] of (payer_index, payee_index)."""
        h = self.encode(x, edge_index)
        combined = torch.cat([h[pairs[:, 0]], h[pairs[:, 1]], edge_feats], dim=1)
        return self.head(combined).squeeze(-1)
