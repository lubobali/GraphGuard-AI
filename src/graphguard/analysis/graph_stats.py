"""Basic shape of the transaction graph.

Accounts are nodes, transfers are directed edges. Degree is how many transfers
an account is involved in: out-degree is how many it sent, in-degree how many
it received.

Degree matters here because laundering shapes are degree anomalies. A fan-out
is one account with unusually high out-degree; a fan-in is high in-degree.
Knowing what ordinary degrees look like is what makes "unusual" measurable
rather than a feeling.
"""

from __future__ import annotations

import polars as pl


def degree_table(edges: pl.LazyFrame) -> pl.LazyFrame:
    """One row per account, with in-degree and out-degree.

    Accounts that only ever receive must still appear, so the two sides are
    joined outward rather than filtered to senders.
    """
    out_deg = (
        edges.group_by("from_account")
        .agg(pl.len().alias("out_degree"))
        .rename({"from_account": "account"})
    )
    in_deg = (
        edges.group_by("to_account")
        .agg(pl.len().alias("in_degree"))
        .rename({"to_account": "account"})
    )

    return (
        out_deg.join(in_deg, on="account", how="full", coalesce=True)
        .with_columns(
            pl.col("out_degree").fill_null(0),
            pl.col("in_degree").fill_null(0),
        )
        .with_columns((pl.col("in_degree") + pl.col("out_degree")).alias("degree"))
    )


def degree_summary(edges: pl.LazyFrame) -> dict:
    """Headline numbers describing the graph's shape."""
    d = degree_table(edges).collect()

    return {
        "n_accounts": d.height,
        "n_edges": int(d["out_degree"].sum()),
        "mean_degree": float(d["degree"].mean()),
        "median_degree": float(d["degree"].median()),
        "max_out_degree": int(d["out_degree"].max()),
        "max_in_degree": int(d["in_degree"].max()),
        "p99_degree": float(d["degree"].quantile(0.99)),
    }
