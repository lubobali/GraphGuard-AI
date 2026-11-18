"""Open the Iceberg catalog.

Since S5.6c the catalog is **Lakekeeper**, an Iceberg REST catalog on 127.0.0.1:8181
(`graphguard` warehouse on our S3 bucket). Clients bring their own S3 key -- vending
and remote signing are off until S5.6d adds identities.

The PyIceberg SQL catalog (its `lakehouse` Postgres database) was S5.6a's catalog.
It still opens with `GRAPHGUARD_CATALOG=sql` as the rollback, but it no longer sees
new commits, so it goes stale after the first build through Lakekeeper. Tests pass a
SQLite URI to get a throwaway SQL catalog; the table logic is catalog-agnostic.

Credentials come from `.secrets/lakehouse.env` (gitignored, 600), never from code.
"""

from __future__ import annotations

import os
from pathlib import Path

from pyiceberg.catalog import Catalog
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.catalog.sql import SqlCatalog

from graphguard.config import REPO_ROOT
from graphguard.lakehouse.storage import read_aws_env, s3_properties

NAMESPACES = ("bronze", "silver", "gold", "sealed")
CATALOG_NAME = "graphguard"
SECRETS_FILE = REPO_ROOT / ".secrets" / "lakehouse.env"
DEFAULT_WAREHOUSE = f"file://{REPO_ROOT / 'lakehouse' / 'warehouse'}"
POSTGRES_HOSTPORT = os.environ.get("GRAPHGUARD_LAKEHOUSE_PG", "127.0.0.1:5434")
LAKEKEEPER_CATALOG_URI = (
    os.environ.get("GRAPHGUARD_LAKEKEEPER_URL", "http://127.0.0.1:8181") + "/catalog"
)
LAKEKEEPER_WAREHOUSE = "graphguard"


def _read_env_file(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def default_uri() -> str:
    """The real catalog: the `lakehouse` database in GraphGuard's Postgres."""
    if uri := os.environ.get("GRAPHGUARD_LAKEHOUSE_URI"):
        return uri
    env = _read_env_file(SECRETS_FILE)
    user, pw, db = env["LAKEHOUSE_DB_USER"], env["LAKEHOUSE_DB_PASSWORD"], env["LAKEHOUSE_DB_NAME"]
    return f"postgresql+psycopg2://{user}:{pw}@{POSTGRES_HOSTPORT}/{db}"


def default_warehouse() -> tuple[str, dict[str, str]]:
    """S3 once `.secrets/aws.env` is filled in (S5.6b); local disk until then.

    `GRAPHGUARD_LAKEHOUSE_WAREHOUSE` overrides both, e.g. to force local.
    """
    if override := os.environ.get("GRAPHGUARD_LAKEHOUSE_WAREHOUSE"):
        return override, {}
    env = read_aws_env()
    if env is None:
        return DEFAULT_WAREHOUSE, {}
    return f"s3://{env.bucket}/lakehouse", s3_properties(env)


def open_catalog(
    uri: str | None = None, warehouse: str | None = None, s3: dict[str, str] | None = None
) -> Catalog:
    """Open the catalog and make sure the four namespaces exist.

    No arguments: Lakekeeper (or the SQL catalog with GRAPHGUARD_CATALOG=sql).
    A `uri`: a SQL catalog there -- what tests use. `s3` carries PyIceberg `s3.*`
    properties when the warehouse is on S3.
    """
    if uri is None and os.environ.get("GRAPHGUARD_CATALOG", "rest") == "rest":
        catalog: Catalog = open_rest_catalog()
    else:
        if warehouse is None:
            warehouse, s3 = default_warehouse()
        if warehouse.startswith("file://"):
            Path(warehouse.removeprefix("file://")).mkdir(parents=True, exist_ok=True)
        catalog = SqlCatalog(
            CATALOG_NAME, uri=uri or default_uri(), warehouse=warehouse, **(s3 or {})
        )
    for ns in NAMESPACES:
        catalog.create_namespace_if_not_exists(ns)
    return catalog


def open_rest_catalog() -> RestCatalog:
    """The Lakekeeper catalog, with our own S3 key (client-managed access)."""
    env = read_aws_env()
    if env is None:
        raise RuntimeError("Lakekeeper's warehouse is on S3: fill .secrets/aws.env first")
    return RestCatalog(
        CATALOG_NAME,
        uri=LAKEKEEPER_CATALOG_URI,
        warehouse=LAKEKEEPER_WAREHOUSE,
        **{"header.X-Iceberg-Access-Delegation": "client-managed"},
        **s3_properties(env),
    )
