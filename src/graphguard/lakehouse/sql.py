"""DuckDB over the lakehouse (S5.6b): SQL on the Iceberg tables, read-only.

    just sql "select count(*) from silver_transactions"

Each SQL table is a view named after it (`silver.transactions` ->
`silver_transactions`). The test window is never exposed: not `sealed`, and not
bronze either, whose raw rows include the test window (FINDING-011, S5.6d). Memory is
capped at 512 MB with a spill directory, because this box's budget is shared
with Ray, MLflow and LuBot production.

**Ties.** Training counts history by sorting on time and keeping source order
for transfers in the same minute: the second of two same-minute transfers counts
the first as "before". `history_before` reproduces that with an ordering key of
(timestamp, source_row). A plain strictly-earlier-in-time ASOF join disagrees on
every tie; `strict_time_history_before` exists only so a test can show that.
"""

from __future__ import annotations

import sys
from urllib.parse import urlparse

import duckdb
import polars as pl
from pyiceberg.catalog import Catalog

from graphguard.config import REPO_ROOT
from graphguard.lakehouse.tables import GOLD_FEATURES, GOLD_LABELS, SILVER_TX

MEMORY_LIMIT = "512MB"
THREADS = 2
EXTENSION_DIR = REPO_ROOT / ".tools" / "duckdb_extensions"
SPILL_DIR = REPO_ROOT / "lakehouse" / "tmp" / "duckdb"
# What `just sql` shows. Bronze is left out on purpose: it is the raw CSV, test
# window included, and the `reader` identity may not read it (governance.py).
SQL_TABLES = (SILVER_TX, GOLD_FEATURES, GOLD_LABELS)


def view_name(table: str) -> str:
    return table.replace(".", "_")


def connect(catalog: Catalog) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB with one view per tracked lakehouse table."""
    SPILL_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET extension_directory='{EXTENSION_DIR}'")
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    con.execute(f"SET threads={THREADS}")
    con.execute(f"SET temp_directory='{SPILL_DIR}'")
    con.execute("INSTALL iceberg; LOAD iceberg")

    props = catalog.properties
    if "s3.access-key-id" in props:
        con.execute("INSTALL httpfs; LOAD httpfs")
        opts = [
            "TYPE s3",
            f"KEY_ID '{props['s3.access-key-id']}'",
            f"SECRET '{props['s3.secret-access-key']}'",
            f"REGION '{props.get('s3.region', 'us-east-1')}'",
        ]
        if endpoint := props.get("s3.endpoint"):  # a test S3 server
            u = urlparse(endpoint)
            opts += [f"ENDPOINT '{u.netloc}'", "URL_STYLE 'path'", f"USE_SSL {u.scheme == 'https'}"]
        con.execute(f"CREATE SECRET lakehouse ({', '.join(opts)})")

    for name in SQL_TABLES:
        location = catalog.load_table(name).metadata_location
        con.execute(f"CREATE VIEW {view_name(name)} AS SELECT * FROM iceberg_scan('{location}')")
    return con


def attach_catalog_for_writes(
    con: duckdb.DuckDBPyConnection, catalog: Catalog, alias: str = "lk"
) -> str:
    """ATTACH the Lakekeeper REST catalog so DuckDB can write (INSERT, MERGE).

    DuckDB logs in as the same identity as `catalog` (OAuth2 client credentials
    against Dex), so Lakekeeper applies that identity's permissions to DuckDB too.
    It still uses its own S3 secret (ACCESS_DELEGATION_MODE 'none') until
    credential vending is on, and that key opens every table's files -- so only
    code that must write uses this, and `just sql` keeps to its views.
    """
    uri = catalog.properties.get("uri")
    if not uri:
        raise ValueError("not a REST catalog: DuckDB writes need Lakekeeper")
    credential = catalog.properties.get("credential")
    if not credential:
        raise ValueError("the catalog has no identity: open it with open_catalog(<identity>)")
    client_id, client_secret = credential.split(":", 1)
    con.execute(
        f"CREATE OR REPLACE SECRET {alias}_login (TYPE iceberg, "
        f"CLIENT_ID '{client_id}', CLIENT_SECRET '{client_secret}', "
        f"OAUTH2_SERVER_URI '{catalog.properties['oauth2-server-uri']}', "
        f"OAUTH2_SCOPE '{catalog.properties.get('scope', 'openid')}')"
    )
    con.execute(
        f"ATTACH '{catalog.properties['warehouse']}' AS {alias} "
        f"(TYPE iceberg, ENDPOINT '{uri}', SECRET {alias}_login, "
        "ACCESS_DELEGATION_MODE 'none')"
    )
    return alias


_HISTORY = """
WITH tx AS (
    SELECT timestamp, from_account, to_account, amount_paid,
           {order_key} AS ord, row_number() OVER (ORDER BY timestamp, source_row) AS pos
    FROM silver_transactions
),
sent AS (
    SELECT from_account AS account, ord,
           count(*) OVER w AS n, sum(amount_paid) OVER w AS amount
    FROM tx WINDOW w AS (PARTITION BY from_account ORDER BY pos ROWS UNBOUNDED PRECEDING)
),
received AS (
    SELECT to_account AS account, ord, count(*) OVER w AS n
    FROM tx WINDOW w AS (PARTITION BY to_account ORDER BY pos ROWS UNBOUNDED PRECEDING)
)
SELECT t.timestamp, t.from_account, t.to_account, t.amount_paid,
       coalesce(s.n, 0)        AS sender_n_sent_before,
       coalesce(s.amount, 0.0) AS sender_amount_sent_before,
       coalesce(r.n, 0)        AS receiver_n_received_before
FROM tx t
ASOF LEFT JOIN sent s     ON t.from_account = s.account AND t.ord > s.ord
ASOF LEFT JOIN received r ON t.to_account   = r.account AND t.ord > r.ord
ORDER BY t.pos
"""


def history_before(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """Per silver transaction: the sender's and receiver's history before it,
    with training's tie semantics (time, then source order)."""
    return con.sql(
        _HISTORY.format(order_key="row_number() OVER (ORDER BY timestamp, source_row)")
    ).pl()


def strict_time_history_before(con: duckdb.DuckDBPyConnection) -> pl.DataFrame:
    """The tempting but wrong version: strictly earlier in time. Disagrees on ties."""
    return con.sql(_HISTORY.format(order_key="timestamp")).pl()


def main() -> int:
    from graphguard.lakehouse.catalog import open_catalog

    if len(sys.argv) < 2:
        print(
            'usage: just sql "select ..."   views: ' + ", ".join(view_name(t) for t in SQL_TABLES)
        )
        return 2
    print(connect(open_catalog("reader")).sql(sys.argv[1]).pl())
    return 0


if __name__ == "__main__":
    sys.exit(main())
