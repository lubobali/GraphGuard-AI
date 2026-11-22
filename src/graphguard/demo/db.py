"""The demo database (S7.1): roles, tables, the load.

    python -m graphguard.demo.db setup     # = just demo-setup (roles + database + tables)

Database `demo`, separate from `stream`, so a stream reset cannot reach it. Three roles,
least privilege each (ADR 0008):

    demo_owner   owns and loads the tables            host only (just demo-build)
    demo_reader  SELECT on the demo tables, nothing   the read API (S7.6), tests
    demo_writer  INSERT into verdicts, nothing else   the API's verdict endpoint (D7)

Passwords: `.secrets/demo-db.env` (registered; `just rotate-pg demo_owner|demo_reader|
demo_writer`). Access lines: `pg_access` (SERVICES + EXTRA_ROLES).
"""

from __future__ import annotations

import io
import json
import os
import secrets
import sys
from urllib.parse import quote

import polars as pl

from graphguard.config import REPO_ROOT
from graphguard.config import secrets_dir as _secrets_dir

DB = "demo"
OWNER, READER, WRITER = "demo_owner", "demo_reader", "demo_writer"
ROLES = (OWNER, READER, WRITER)
ENV_FILE = "demo-db.env"
HOST = "127.0.0.1:5434"
VAR = {OWNER: "DEMO_OWNER_PASSWORD", READER: "DEMO_READER_PASSWORD", WRITER: "DEMO_WRITER_PASSWORD"}

# The queue table's columns, in load order (names = the build's frame).
TX_COLUMNS = {
    "event_id": "bigint PRIMARY KEY",
    "event_time": "timestamp NOT NULL",
    "from_bank": "text NOT NULL",
    "from_account": "text NOT NULL",
    "to_bank": "text NOT NULL",
    "to_account": "text NOT NULL",
    "amount_received": "double precision NOT NULL",
    "receiving_currency": "text NOT NULL",
    "amount_paid": "double precision NOT NULL",
    "payment_currency": "text NOT NULL",
    "payment_format": "text NOT NULL",
    "score": "double precision NOT NULL",
    "cold_policy": "text NOT NULL",
    "rules": "text[] NOT NULL",
    "alert": "boolean NOT NULL",
    "model_version": "text NOT NULL",
    "features": "double precision[] NOT NULL",
    "priority": "double precision NOT NULL",
    "rank": "bigint NOT NULL UNIQUE",
    "percentile": "double precision NOT NULL",
    "from_bank_name": "text",
    "from_name": "text",
    "to_bank_name": "text",
    "to_name": "text",
}
# Rebuilt by every load (verdicts is not: the audit trail outlives rebuilds).
LOADED = ("transactions", "accounts", "truth", "capacity", "explanations", "subgraphs")
TABLES = (*LOADED, "verdicts", "build_info")  # what demo_reader may SELECT

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS transactions ("
    + ", ".join(f"{c} {t}" for c, t in TX_COLUMNS.items())
    + ");\n"
    + """
CREATE INDEX IF NOT EXISTS transactions_from ON transactions (from_account, event_time);
CREATE INDEX IF NOT EXISTS transactions_to ON transactions (to_account, event_time);
CREATE INDEX IF NOT EXISTS transactions_time ON transactions (event_time);
CREATE TABLE IF NOT EXISTS accounts (
    bank_id     bigint NOT NULL,
    account     text NOT NULL,
    bank_name   text NOT NULL,
    entity_name text NOT NULL,
    PRIMARY KEY (bank_id, account)
);
-- The answer key, apart from the queue (ADR 0008): only the curve and its own tab read it.
CREATE TABLE IF NOT EXISTS truth (
    event_id      bigint PRIMARY KEY,
    is_laundering boolean NOT NULL
);
-- S7.2: the ring each transaction belongs to (gold.rings -- train + validation only).
ALTER TABLE truth ADD COLUMN IF NOT EXISTS pattern_id integer;
ALTER TABLE truth ADD COLUMN IF NOT EXISTS pattern_type text;
ALTER TABLE truth ADD COLUMN IF NOT EXISTS hop integer;
-- Investigators' verdicts (D7): append-only audit trail; survives every rebuild.
CREATE TABLE IF NOT EXISTS verdicts (
    id        bigserial PRIMARY KEY,
    event_id  bigint NOT NULL,
    verdict   text NOT NULL CHECK (verdict IN ('escalate', 'close')),
    note      text NOT NULL DEFAULT '' CHECK (length(note) <= 2000),
    at        timestamptz NOT NULL DEFAULT now()
);
-- S7.3: the slider's numbers -- four rankings x k = 1..5,000 (counts, never money).
CREATE TABLE IF NOT EXISTS capacity (
    ranking       text NOT NULL,
    k             integer NOT NULL,
    caught        integer NOT NULL,
    missed        integer NOT NULL,
    precision     double precision NOT NULL,
    recall        double precision NOT NULL,
    rings_caught  integer NOT NULL,
    rings_touched integer NOT NULL,
    rings_total   integer NOT NULL,
    PRIMARY KEY (ranking, k)
);
-- S7.4: exact SHAP (log-odds) for the queue's top 20,000, and the three plain reasons.
CREATE TABLE IF NOT EXISTS explanations (
    event_id  bigint PRIMARY KEY,
    base      double precision NOT NULL,
    contribs  double precision[] NOT NULL,
    reasons   text[] NOT NULL
);
-- S7.5: the ring as of each top alert (money-flow view, 72 h, capped). No labels.
CREATE TABLE IF NOT EXISTS subgraphs (
    event_id  bigint PRIMARY KEY,
    graph     jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS build_info (
    id   smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    info jsonb NOT NULL
);
"""
)

GRANTS = f"""
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO {READER}, {WRITER};
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {READER}, {WRITER};
GRANT SELECT ON {", ".join(TABLES)} TO {READER};
GRANT INSERT ON verdicts TO {WRITER};
GRANT USAGE ON SEQUENCE verdicts_id_seq TO {WRITER};
"""


# --- passwords ----------------------------------------------------------------------------
def _env(secrets_dir=None) -> dict[str, str]:
    path = (secrets_dir or _secrets_dir()) / ENV_FILE
    return dict(ln.split("=", 1) for ln in path.read_text().splitlines() if "=" in ln)


def password(role: str, secrets_dir=None) -> str:
    return _env(secrets_dir)[VAR[role]]


def dsn(role: str, where: str = HOST, secrets_dir=None) -> str:
    return f"postgresql://{role}:{quote(password(role, secrets_dir), safe='')}@{where}/{DB}"


def connect(role: str = READER, where: str = HOST, secrets_dir=None):
    import psycopg2

    return psycopg2.connect(dsn(role, where, secrets_dir), connect_timeout=5)


def _ensure_passwords() -> dict[str, str]:
    path = REPO_ROOT / ".secrets" / ENV_FILE
    have = _env(REPO_ROOT / ".secrets") if path.exists() else {}
    missing = {VAR[r]: secrets.token_urlsafe(24) for r in ROLES if VAR[r] not in have}
    if missing:
        body = "# The demo database's roles (S7.1). Never commit.\n" + "".join(
            f"{k}={v}\n" for k, v in {**have, **missing}.items()
        )
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(body)
        os.replace(tmp, path)
    return {r: _env(REPO_ROOT / ".secrets")[VAR[r]] for r in ROLES}


# --- setup --------------------------------------------------------------------------------
def setup() -> None:
    from graphguard.ops import secrets_registry as reg
    from graphguard.ops.rotate import scram_verifier
    from graphguard.stream.db import _superuser

    pws = _ensure_passwords()
    sql = "".join(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{r}') THEN "
        f"CREATE ROLE {r} LOGIN; END IF; END $$;\n"
        f"ALTER ROLE {r} PASSWORD '{scram_verifier(pws[r])}';\n"
        for r in ROLES
    )
    _superuser('psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres', sql)
    exists = _superuser(f'psql -At -U "$POSTGRES_USER" -d postgres -c '
                        f"\"select 1 from pg_database where datname='{DB}'\"").strip()  # fmt: skip
    if exists != "1":
        _superuser(f'createdb -U "$POSTGRES_USER" -O {OWNER} {DB}')
    _superuser(
        'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres',
        f"REVOKE ALL ON DATABASE {DB} FROM PUBLIC;\n"
        f"GRANT CONNECT ON DATABASE {DB} TO {OWNER}, {READER}, {WRITER};\n"
        "SELECT pg_reload_conf();\n",
    )
    with connect(OWNER, secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
        cur.execute(GRANTS)
    reg.record(ENV_FILE)


# --- the load -----------------------------------------------------------------------------
def _pg_array(values) -> str:
    def item(v):
        if isinstance(v, str):
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        return repr(float(v))

    return "{" + ",".join(item(v) for v in values) + "}"


def _csv(df: pl.DataFrame) -> io.StringIO:
    return io.StringIO("".join(_csv_parts(df)))


def _csv_parts(df: pl.DataFrame, rows: int = 100_000):
    """The load's CSV in slices (one string of a million rows cost hundreds of MB)."""
    for i, part in enumerate(df.iter_slices(rows)):
        yield _csv_text(part, header=i == 0)


def _csv_text(df: pl.DataFrame, header: bool) -> str:
    out = df
    for c, dtype in df.schema.items():
        if isinstance(dtype, pl.List) and dtype.inner.is_numeric():
            # fast path: numbers need no quoting ("{0.1,0.2}")
            joined = pl.col(c).cast(pl.List(pl.Utf8)).list.join(",")
            out = out.with_columns((pl.lit("{") + joined + pl.lit("}")).alias(c))
        elif isinstance(dtype, pl.List):
            out = out.with_columns(pl.col(c).map_elements(_pg_array, return_dtype=pl.Utf8).alias(c))
    return out.write_csv(
        float_precision=17, datetime_format="%Y-%m-%d %H:%M:%S", include_header=header
    )


def load(tables: dict[str, pl.DataFrame], info: dict) -> None:
    """Replace the data in ONE transaction (readers see the old copy until it commits).
    `verdicts` is never touched: the audit trail outlives every rebuild."""
    frames = {
        "transactions": tables["transactions"].select(list(TX_COLUMNS)),
        "accounts": tables["accounts"].select("bank_id", "account", "bank_name", "entity_name"),
        "capacity": tables["capacity"],
        "explanations": tables["explanations"],
        "subgraphs": tables["subgraphs"],
        "truth": tables["truth"].select(
            "event_id", "is_laundering", "pattern_id", "pattern_type", "hop"
        ),
    }
    with connect(OWNER, secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        # every loaded table (never verdicts: the audit trail outlives rebuilds)
        cur.execute(f"TRUNCATE {', '.join(LOADED)}, build_info")
        for name, df in frames.items():
            cols = ", ".join(df.columns)
            sql = f"COPY {name} ({cols}) FROM STDIN WITH (FORMAT csv)"
            for part in df.iter_slices(100_000):  # one slice at a time, no header
                cur.copy_expert(sql, io.StringIO(_csv_text(part, header=False)))
        cur.execute("INSERT INTO build_info (id, info) VALUES (1, %s)", (json.dumps(info),))
        cur.execute("ANALYZE transactions; ANALYZE accounts; ANALYZE truth")


def main(argv: list[str]) -> int:
    if (argv[1] if len(argv) > 1 else "") == "setup":
        setup()
        print(f"database {DB}: roles {', '.join(ROLES)}, tables ready")
        return 0
    print(f"usage: {argv[0]} setup")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
