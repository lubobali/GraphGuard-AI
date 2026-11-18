"""Explore the lakehouse as the `reader` identity (S5.6e).

    just notebook        # opens on 127.0.0.1:2718 with a token; reach it over the SSH tunnel

A marimo notebook: plain Python, reviewed in git like any other code. It reads through
`sql_session`, so DuckDB logs in as `reader` with keys Lakekeeper vends per table:
silver and gold are readable, bronze is Forbidden and `sealed` does not exist. The
test window cannot be explored from here by mistake.
"""

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.sql import sql_session

    con = sql_session(open_catalog("reader"))
    mo.md(
        "# GraphGuard lakehouse\n"
        "Synthetic data: IBM AMLworld HI-Small. Signed in as **reader** "
        "(silver and gold; never the test window)."
    )
    return con, mo


@app.cell
def _(con, mo):
    schemas = con.sql(
        "select schema_name from duckdb_schemas() "
        "where database_name = 'lk' and schema_name not in ('information_schema', 'main') "
        "order by 1"
    ).pl()
    counts = con.sql(
        """
        select 'silver.transactions' as tbl, count(*) as n_rows from silver_transactions
        union all select 'gold.account_features_asof', count(*) from gold_account_features_asof
        union all select 'gold.labels', count(*) from gold_labels
        """
    ).pl()
    mo.vstack([mo.md("## What reader can see"), schemas, counts])
    return (counts,)


@app.cell
def _(con, mo):
    per_day = con.sql(
        """
        select cast(timestamp as date) as day,
               count(*) as transactions,
               sum(is_laundering) as laundering,
               round(100 * avg(is_laundering), 3) as pct_laundering
        from silver_transactions
        group by 1 order by 1
        """
    ).pl()
    mo.vstack([mo.md("## Laundering rate per day (train + validation only)"), per_day])
    return (per_day,)


@app.cell
def _(con, mo):
    senders = con.sql(
        """
        select from_account,
               count(*) as laundering_sends,
               round(sum(amount_paid), 2) as amount_paid,
               min(timestamp) as first_seen,
               max(timestamp) as last_seen
        from silver_transactions
        where is_laundering = 1
        group by 1 order by 2 desc limit 10
        """
    ).pl()
    mo.vstack([mo.md("## Accounts with the most labelled laundering sends"), senders])
    return (senders,)


@app.cell
def _(con, mo):
    # FINDING-010: "before" means time, then source order. Two sends in the same
    # minute: the second counts the first. Strictly-earlier-in-time does not.
    ties = con.sql(
        """
        with sends as (
            select from_account, timestamp, source_row
            from silver_transactions
            where from_account = (
                select from_account from silver_transactions
                group by from_account, timestamp having count(*) > 1
                order by from_account, timestamp limit 1
            )
        )
        select timestamp, source_row,
               row_number() over (order by timestamp, source_row) - 1 as sent_before_training_rule,
               count(*) over (order by timestamp range between unbounded preceding
                              and interval 1 microsecond preceding) as sent_before_strict_time
        from sends order by timestamp, source_row limit 12
        """
    ).pl()
    mo.vstack(
        [
            mo.md(
                "## Ties: training's rule vs strictly-earlier time\n"
                "Rows in the same minute disagree. Training uses the first column."
            ),
            ties,
        ]
    )
    return (ties,)


if __name__ == "__main__":
    app.run()
