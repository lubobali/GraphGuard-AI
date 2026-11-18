"""DuckDB over the lakehouse: SQL that agrees with the training path (S5.6b)."""

import datetime as dt

import polars as pl
import pytest

from graphguard.features.graph import build_account_history_features
from graphguard.lakehouse.sql import (
    SQL_TABLES,
    connect,
    history_before,
    strict_time_history_before,
)
from graphguard.lakehouse.tables import (
    BRONZE_TX,
    SILVER_TX,
    scan_in_source_order,
    write_bronze,
    write_gold_features,
    write_gold_labels,
    write_silver,
)

pytestmark = pytest.mark.unit

TRAIN_END = dt.datetime(2022, 9, 6)
VAL_END = dt.datetime(2022, 9, 8)
T = dt.datetime(2022, 9, 2, 10, 0)


def _tx(ts, frm, to, amount):
    return {
        "timestamp": ts,
        "from_bank": "1",
        "from_account": frm,
        "to_bank": "2",
        "to_account": to,
        "amount_received": amount,
        "receiving_currency": "US Dollar",
        "amount_paid": amount,
        "payment_currency": "US Dollar",
        "payment_format": "ACH",
        "is_laundering": 0,
    }


@pytest.fixture
def built(cat):
    rows = [
        _tx(T + dt.timedelta(hours=3), "A", "C", 5.0),  # source row 0, later in time
        _tx(T, "A", "B", 10.0),  # source row 1
        _tx(T, "A", "B", 20.0),  # source row 2: SAME minute as row 1
        _tx(T - dt.timedelta(hours=1), "B", "A", 7.0),  # source row 3, earliest
        _tx(T + dt.timedelta(days=1), "C", "A", 1.0),
        _tx(dt.datetime(2022, 9, 9), "A", "Z", 99.0),  # test window -> sealed
    ]
    write_bronze(cat, pl.DataFrame(rows).with_columns(pl.col("timestamp").cast(pl.Datetime("us"))))
    write_silver(cat, boundaries=(TRAIN_END, VAL_END))
    write_gold_features(cat, as_of=TRAIN_END)
    write_gold_labels(cat)
    return cat


def test_sql_row_counts_match_pyiceberg(built):
    con = connect(built)
    for name in SQL_TABLES:
        view = name.replace(".", "_")
        sql = con.execute(f"select count(*) from {view}").fetchone()[0]
        assert sql == built.load_table(name).scan().to_arrow().num_rows, name


def test_the_sealed_table_is_never_exposed_to_sql(built):
    views = {
        r[0]
        for r in connect(built)
        .execute("select view_name from duckdb_views() where not internal")
        .fetchall()
    }
    assert views and not any("seal" in v for v in views)


def test_bronze_is_not_exposed_because_it_holds_the_test_window(built):
    # FINDING-011: bronze is the raw CSV, test window included. A bronze view made
    # the sealed namespace pointless for anyone running SQL.
    con = connect(built)
    views = {
        r[0]
        for r in con.execute("select view_name from duckdb_views() where not internal").fetchall()
    }
    assert "bronze_transactions_raw" not in views
    assert built.load_table(BRONZE_TX).scan().to_arrow().num_rows > 0  # it exists; just not here


def test_no_sql_view_returns_a_row_from_the_test_window(built):
    con = connect(built)
    for name in SQL_TABLES:
        view = name.replace(".", "_")
        cols = {r[0] for r in con.execute(f"describe {view}").fetchall()}
        if "timestamp" in cols:
            n = con.execute(
                f"select count(*) from {view} where timestamp >= ?", [VAL_END]
            ).fetchone()[0]
            assert n == 0, view


def test_memory_is_capped(built):
    limit = connect(built).execute("select current_setting('memory_limit')").fetchone()[0]
    assert "MiB" in limit and float(limit.split()[0]) <= 512


def test_history_before_matches_the_training_features_including_ties(built):
    # Training sorts by time and keeps source order for ties, so the second of
    # two same-minute transfers counts the first as "before". DuckDB must agree.
    silver = scan_in_source_order(built, SILVER_TX)
    expected = (
        build_account_history_features(silver, as_of=VAL_END)
        .select(
            "timestamp",
            "from_account",
            "to_account",
            "amount_paid",
            "sender_n_sent_before",
            "sender_amount_sent_before",
            "receiver_n_received_before",
        )
        .collect()
    )
    got = history_before(connect(built))
    key = ["timestamp", "from_account", "to_account", "amount_paid"]
    j = expected.join(got, on=key, suffix="_sql")
    assert j.height == expected.height == got.height
    assert (j["sender_n_sent_before"] == j["sender_n_sent_before_sql"]).all()
    assert (j["receiver_n_received_before"] == j["receiver_n_received_before_sql"]).all()
    # floats: FINDING-009 -- exact order, but a different engine; stated tolerance
    assert (
        (j["sender_amount_sent_before"] - j["sender_amount_sent_before_sql"]).abs() <= 1e-9
    ).all()


@pytest.mark.regression
def test_a_strictly_earlier_in_time_join_disagrees_on_the_tie(built):
    # The trap: "ts > ts" (strict time) treats same-minute transfers as
    # simultaneous, so the 20.0 transfer sees 0 sends before it where training
    # sees 1. Kept as a test so nobody "simplifies" history_before into it.
    strict = strict_time_history_before(connect(built)).filter(pl.col("amount_paid") == 20.0)
    exact = history_before(connect(built)).filter(pl.col("amount_paid") == 20.0)
    assert exact["sender_n_sent_before"].item() == 1
    assert strict["sender_n_sent_before"].item() == 0
