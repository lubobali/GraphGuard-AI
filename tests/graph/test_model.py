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


@pytest.mark.unit
def test_distinct_counterparties_differ_from_raw_degree():
    """Two payments to the same account is one counterparty, not two."""
    # node 0 pays node 1 twice; node 2 pays nodes 1 and 3 once each
    edge_index = torch.tensor([[0, 0, 2, 2], [1, 1, 1, 3]])
    edge_attr = torch.ones((4, 1))
    f = node_features(edge_index, edge_attr, num_nodes=4)
    out_deg, distinct_out = f[:, 0], f[:, 4]
    assert out_deg[0] == out_deg[2]  # both sent twice
    assert distinct_out[0] < distinct_out[2]  # but 0 reached fewer accounts


@pytest.mark.unit
def test_distinct_in_counts_unique_payers():
    edge_index = torch.tensor([[0, 0, 1], [2, 2, 2]])
    edge_attr = torch.ones((3, 1))
    f = node_features(edge_index, edge_attr, num_nodes=3)
    assert f[2, 5] > 0  # node 2 received from two distinct payers


@pytest.mark.unit
def test_feature_width_matches_the_declared_dim():
    from graphguard.graph.model import NODE_FEATURE_DIM

    f = node_features(torch.tensor([[0], [1]]), torch.ones((1, 1)), num_nodes=2)
    assert f.shape[1] == NODE_FEATURE_DIM


@pytest.mark.unit
def test_disabling_the_graph_zeroes_the_node_embeddings():
    """The ablation must actually remove the graph, not just relabel it."""
    model = EdgeScorer(in_channels=6, hidden=8, edge_dim=2, use_graph=False).eval()
    x = torch.randn(4, 6)
    edge_index = torch.tensor([[0, 1], [1, 2]])
    assert model.encode(x, edge_index).abs().sum() == 0


@pytest.mark.unit
def test_disabled_graph_still_produces_scores():
    model = EdgeScorer(in_channels=6, hidden=8, edge_dim=2, use_graph=False).eval()
    out = model(
        torch.randn(4, 6), torch.tensor([[0, 1], [1, 2]]), torch.tensor([[0, 1]]), torch.randn(1, 2)
    )
    assert out.shape == (1,) and torch.isfinite(out).all()
