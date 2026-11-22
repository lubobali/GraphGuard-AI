"""The ring as of the alert (S7.5): nothing after it, money-flow hops, hubs capped."""

import datetime as dt
import json

import polars as pl
import pytest

from graphguard.demo import subgraph as G

pytestmark = pytest.mark.unit

T = dt.datetime(2022, 9, 7, 12, 0)


def _edges(rows):
    """rows: (source_row, minutes before T (negative = before), from, to)."""
    return pl.DataFrame(
        {
            "source_row": [r[0] for r in rows],
            "timestamp": [T + dt.timedelta(minutes=r[1]) for r in rows],
            "from_bank": ["1"] * len(rows),
            "from_account": [r[2] for r in rows],
            "to_bank": ["1"] * len(rows),
            "to_account": [r[3] for r in rows],
            "amount_paid": [100.0 + r[0] for r in rows],
            "payment_currency": ["Euro"] * len(rows),
            "payment_format": ["ACH"] * len(rows),
        }
    )


@pytest.fixture
def index():
    rows = [
        (1, -120, "U2", "U1"),  # upstream 2
        (2, -60, "U1", "S"),  # upstream 1 (who paid the sender)
        (3, -30, "R", "D1"),  # downstream 1 ... before the alert
        (4, -20, "D1", "S"),  # downstream 2: a loop back to the sender
        (5, 0, "X", "S"),  # same minute, EARLIER in source order -> included
        (10, 0, "S", "R"),  # the alert
        (11, 0, "Y", "S"),  # same minute, LATER in source order -> excluded
        (12, 5, "S", "Z"),  # after the alert -> excluded
        (13, -10, "S", "S"),  # self-transfer -> left out
        (14, -5000, "W", "S"),  # outside the 72 h window -> excluded
    ]
    return G.EdgeIndex(_edges(rows))


def test_only_what_came_before_the_alert(index):
    g = G.subgraph(index, alert_id=10, cap=6)
    ids = {e["id"] for e in g["edges"]}
    assert 10 in ids and 5 in ids  # the alert, and the same-minute earlier one
    assert not ids & {11, 12, 13, 14}


def test_money_flow_hops_and_the_loop_are_kept(index):
    g = G.subgraph(index, alert_id=10, cap=6)
    role = {e["id"]: e["role"] for e in g["edges"]}
    assert role[10] == "alert" and role[2] == "upstream" and role[1] == "upstream 2"
    assert role[3] == "downstream" and role[4] == "downstream 2"  # D1 -> S closes the loop
    seeds = {n["id"]: n["seed"] for n in g["nodes"] if n["seed"]}
    assert seeds == {"1:S": "sender", "1:R": "receiver"}


def test_a_hub_is_capped_and_the_rest_counted():
    rows = [(i, -i, f"P{i}", "S") for i in range(1, 21)] + [(100, 0, "S", "R")]
    g = G.subgraph(G.EdgeIndex(_edges(rows)), alert_id=100, cap=6)
    payers = [e for e in g["edges"] if e["to"] == "1:S" and e["role"] == "upstream"]
    assert len(payers) == 6 and sorted(e["id"] for e in payers) == [1, 2, 3, 4, 5, 6]  # recent
    (more,) = [m for m in g["more"] if m["node"] == "1:S" and m["direction"] == "in"]
    assert more["count"] == 14


def test_the_graph_is_deterministic_and_carries_no_label(index):
    a = json.dumps(G.subgraph(index, alert_id=10, cap=6), sort_keys=True)
    b = json.dumps(G.subgraph(index, alert_id=10, cap=6), sort_keys=True)
    assert a == b and "laundering" not in a and "pattern" not in a
