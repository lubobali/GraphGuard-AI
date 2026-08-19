"""Graph statistics must count what they claim to count.

Small hand-built graphs where the right answer is obvious by eye, so a wrong
implementation is caught rather than believed.
"""

import polars as pl
import pytest

from graphguard.analysis.graph_stats import degree_summary, degree_table

# A -> B, A -> C, D -> A
EDGES = pl.DataFrame(
    {
        "from_account": ["A", "A", "D"],
        "to_account": ["B", "C", "A"],
    }
).lazy()


@pytest.mark.unit
def test_out_degree_counts_sends():
    d = degree_table(EDGES).collect().sort("account")
    row = d.filter(pl.col("account") == "A").row(0, named=True)
    assert row["out_degree"] == 2


@pytest.mark.unit
def test_in_degree_counts_receives():
    d = degree_table(EDGES).collect()
    row = d.filter(pl.col("account") == "A").row(0, named=True)
    assert row["in_degree"] == 1


@pytest.mark.unit
def test_account_with_no_sends_still_appears():
    """B only receives. It must not be missing from the table."""
    d = degree_table(EDGES).collect()
    row = d.filter(pl.col("account") == "B").row(0, named=True)
    assert row["out_degree"] == 0
    assert row["in_degree"] == 1


@pytest.mark.unit
def test_every_account_appears_exactly_once():
    d = degree_table(EDGES).collect()
    assert sorted(d["account"].to_list()) == ["A", "B", "C", "D"]


@pytest.mark.unit
def test_summary_reports_totals():
    s = degree_summary(EDGES)
    assert s["n_accounts"] == 4
    assert s["n_edges"] == 3
    # 3 edges, 4 accounts -> mean total degree is 6/4
    assert s["mean_degree"] == pytest.approx(1.5)
    assert s["max_out_degree"] == 2
