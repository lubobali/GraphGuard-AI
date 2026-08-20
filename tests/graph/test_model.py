"""The GNN must be inductive and must score edges, not nodes.

Inductive matters operationally: in production the model scores accounts it
never saw during training. A model that can only score known accounts is
useless the moment a new customer appears.
"""

import pytest
import torch

from graphguard.graph.model import EdgeScorer, node_features


@pytest.mark.unit
def test_node_features_have_one_row_per_node():
    edge_index = torch.tensor([[0, 1], [1, 2]])
    edge_attr = torch.tensor([[1.0], [2.0]])
    f = node_features(edge_index, edge_attr, num_nodes=3)
    assert f.shape[0] == 3


@pytest.mark.unit
def test_out_degree_is_captured():
    # node 0 sends twice, node 1 once
    edge_index = torch.tensor([[0, 0, 1], [1, 2, 2]])
    edge_attr = torch.ones((3, 1))
    f = node_features(edge_index, edge_attr, num_nodes=3)
    assert f[0, 0] > f[1, 0]


@pytest.mark.unit
def test_isolated_node_gets_zeros_not_nan():
    """A cold account has no edges. Its features must be finite."""
    edge_index = torch.tensor([[0], [1]])
    edge_attr = torch.ones((1, 1))
    f = node_features(edge_index, edge_attr, num_nodes=3)
    assert torch.isfinite(f).all()
    assert f[2].abs().sum() == 0


@pytest.mark.unit
def test_model_scores_one_value_per_edge():
    model = EdgeScorer(in_channels=4, hidden=8, edge_dim=2)
    x = torch.randn(5, 4)
    edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]])
    pairs = torch.tensor([[0, 1], [2, 3]])
    edge_feats = torch.randn(2, 2)
    out = model(x, edge_index, pairs, edge_feats)
    assert out.shape == (2,)


@pytest.mark.unit
def test_model_handles_a_node_it_never_trained_on():
    """Inductive: a brand new node index must not error."""
    model = EdgeScorer(in_channels=4, hidden=8, edge_dim=2)
    x = torch.randn(6, 4)  # node 5 is new and isolated
    edge_index = torch.tensor([[0, 1], [1, 2]])
    pairs = torch.tensor([[5, 0]])
    out = model(x, edge_index, pairs, torch.randn(1, 2))
    assert out.shape == (1,)
    assert torch.isfinite(out).all()


@pytest.mark.unit
def test_model_is_deterministic_for_a_fixed_seed():
    """Same seed must give the same weights, and the same output in eval mode.

    eval() matters: dropout is deliberately random during training, so two
    identically-initialised models would disagree in train mode by design.
    What must be reproducible is the initialisation and the inference path.
    """
    torch.manual_seed(0)
    a = EdgeScorer(4, 8, 2).eval()
    torch.manual_seed(0)
    b = EdgeScorer(4, 8, 2).eval()
    x = torch.randn(4, 4)
    ei = torch.tensor([[0, 1], [1, 2]])
    pairs = torch.tensor([[0, 1]])
    ef = torch.zeros(1, 2)
    assert torch.allclose(a(x, ei, pairs, ef), b(x, ei, pairs, ef))
