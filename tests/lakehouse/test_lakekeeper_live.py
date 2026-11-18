"""The real Lakekeeper catalog, end to end (S5.6c), logged in as `builder` (S5.6d).

Needs the Lakekeeper container (127.0.0.1:8181) and the S3 key. CI has neither and
skips by an explicit flag, reason printed. Anywhere else an unreachable Lakekeeper
FAILS. Every test works in its own throwaway namespace, purged afterwards, so the
real tables are only ever read.
"""

import datetime as dt
import os
import uuid

import polars as pl
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1",
        reason="GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1 (no Lakekeeper in this environment)",
    ),
]


@pytest.fixture
def rest():
    from graphguard.lakehouse.catalog import open_rest_catalog

    return open_rest_catalog("builder")


@pytest.fixture
def scratch(rest):
    ns = f"scratch_{uuid.uuid4().hex[:8]}"
    rest.create_namespace(ns)
    yield ns
    for ident in rest.list_tables(ns):
        rest.purge_table(ident)
    rest.drop_namespace(ns)


def test_lakekeeper_is_healthy_and_serves_the_real_tables(rest):
    from graphguard.lakehouse.tables import TRACKED_TABLES

    for name in TRACKED_TABLES:
        assert rest.load_table(name).current_snapshot() is not None


def test_write_read_and_time_travel_through_the_catalog(rest, scratch):
    import pyarrow as pa

    t = rest.create_table(
        f"{scratch}.t",
        schema=pa.schema([("k", pa.int64()), ("v", pa.string())]),
        properties={"format-version": "2"},
    )
    t.append(pa.table({"k": [1, 2], "v": ["a", "b"]}))
    first = t.current_snapshot().snapshot_id
    t.append(pa.table({"k": [3], "v": ["c"]}))
    t = rest.load_table(f"{scratch}.t")
    assert t.scan().to_arrow().num_rows == 3
    assert t.scan(snapshot_id=first).to_arrow().num_rows == 2
    assert t.metadata.format_version == 2


def test_duckdb_merge_through_the_catalog_is_visible_to_pyiceberg(rest, scratch):
    from graphguard.lakehouse.sql import attach_catalog, connect

    con = connect(rest)
    lk = attach_catalog(con, rest)
    con.execute(
        f"CREATE TABLE {lk}.{scratch}.labels "
        "(source_row BIGINT, is_laundering INTEGER, label_known_at TIMESTAMP)"
    )
    con.execute(f"INSERT INTO {lk}.{scratch}.labels VALUES (1, 0, NULL), (2, 1, NULL)")
    before = rest.load_table(f"{scratch}.labels").current_snapshot().snapshot_id
    known = dt.datetime(2022, 9, 9, 10, 0)
    con.execute(
        f"MERGE INTO {lk}.{scratch}.labels AS t "
        f"USING (SELECT 2 AS source_row, TIMESTAMP '{known}' AS known) AS s "
        "ON t.source_row = s.source_row WHEN MATCHED THEN UPDATE SET label_known_at = s.known"
    )
    t = rest.load_table(f"{scratch}.labels")
    assert t.current_snapshot().snapshot_id != before  # MERGE made a new snapshot
    got = pl.from_arrow(t.scan().to_arrow()).sort("source_row")
    assert got["label_known_at"].to_list() == [None, known]  # PyIceberg honours DuckDB's deletes
    assert got.height == 2


def test_just_sql_views_never_expose_the_test_window_even_through_lakekeeper(rest):
    from graphguard.lakehouse.sql import connect

    views = {
        r[0]
        for r in connect(rest)
        .execute("select view_name from duckdb_views() where not internal")
        .fetchall()
    }
    assert views and not any("seal" in v or "bronze" in v for v in views)
    assert not {
        r[0]
        for r in connect(rest).execute("select database_name from duckdb_databases()").fetchall()
    } & {"lk"}
