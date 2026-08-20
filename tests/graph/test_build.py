"""The transaction graph must never contain an edge from the future.

Leakage contract rule 2: the graph at time T contains only edges before T.
Building the graph over the full history and then splitting is leakage even
though the split looks correct -- and it is invisible, because the split file
still says the right thing.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.graph.build import build_snapshot, snapshot_index

T0 = dt.datetime(2022, 9, 1)


def _tx(day, frm, to, amount=100.0):
    return {
        "timestamp": T0 + dt.timedelta(days=day),
        "from_account": frm,
        "to_account": to,
        "amount_paid": amount,
        "is_laundering": 0,
    }


FRAME = pl.DataFrame(
    [_tx(0, "A", "B"), _tx(1, "B", "C"), _tx(2, "C", "A"), _tx(5, "A", "D")]
).lazy()


@pytest.mark.unit
def test_snapshot_excludes_edges_at_or_after_the_cutoff():
    g = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=2))
    assert g.num_edges == 2  # days 0 and 1 only


@pytest.mark.unit
def test_no_edge_timestamp_reaches_the_cutoff():
    cutoff = T0 + dt.timedelta(days=2)
    g = build_snapshot(FRAME, as_of=cutoff)
    assert g.edge_time.max().item() < cutoff.timestamp()


@pytest.mark.unit
def test_every_account_seen_so_far_becomes_a_node():
    g = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=2))
    # A, B from day 0; C from day 1
    assert g.num_nodes == 3


@pytest.mark.unit
def test_edge_index_points_at_the_right_nodes():
    g = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=2))
    a, b = g.node_ids.index("A"), g.node_ids.index("B")
    src, dst = g.edge_index[0].tolist(), g.edge_index[1].tolist()
    assert (a, b) in list(zip(src, dst, strict=True))


@pytest.mark.unit
def test_empty_history_produces_an_empty_graph_not_a_crash():
    """The first day of data has no past. That must be handled, not raised."""
    g = build_snapshot(FRAME, as_of=T0)
    assert g.num_edges == 0
    assert g.num_nodes == 0


@pytest.mark.unit
def test_growing_the_cutoff_only_adds_edges():
    small = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=2))
    large = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=6))
    assert large.num_edges > small.num_edges


@pytest.mark.unit
def test_snapshot_index_assigns_a_day_bucket():
    idx = snapshot_index(FRAME).collect().sort("timestamp")
    assert idx["snapshot"].to_list() == [0, 1, 2, 5]


@pytest.mark.unit
def test_node_ids_are_stable_for_the_same_cutoff():
    """Two builds at the same cutoff must map accounts to the same indices."""
    first = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=3))
    second = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=3))
    assert first.node_ids == second.node_ids


@pytest.mark.unit
def test_extra_accounts_become_nodes_without_edges():
    """A brand new account being scored still needs a node index."""
    g = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=2), extra_accounts=["Z"])
    assert "Z" in g.node_ids
    assert g.num_edges == 2  # unchanged


@pytest.mark.unit
def test_extra_accounts_already_present_are_not_duplicated():
    g = build_snapshot(FRAME, as_of=T0 + dt.timedelta(days=2), extra_accounts=["A"])
    assert g.node_ids.count("A") == 1


@pytest.mark.unit
def test_extra_accounts_work_when_there_is_no_history_at_all():
    g = build_snapshot(FRAME, as_of=T0, extra_accounts=["A", "B"])
    assert g.num_nodes == 2
    assert g.num_edges == 0
