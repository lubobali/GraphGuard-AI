"""The stream's own Postgres database (S6.6): decisions, the Kafka position, the outbox.

    python -m graphguard.stream.db setup     # role + database + tables (idempotent)
    python -m graphguard.stream.db reset     # empty the tables (a fresh replay; admin)

Database `stream`, role `stream_app` (in `pg_access.SERVICES`: SCRAM, its own database
only, backed up nightly). The consumer writes each micro-batch in ONE transaction:

    decisions         one row per transaction scored (event_id = source_row, the key);
                      score, rules, model version + hash, and the features it saw
    consumer_offsets  where to resume in Kafka -- moves only with the decisions
    labels            late verdicts from the `labels` topic (S6.9)
    outbox            what to publish (decisions, alerts, dead letters) -- written in the
                      same transaction, published after it, so a message never exists
                      without its row, nor a row without its message
    dead_letters      records that could not be scored (malformed, or too late to be exact)
"""

from __future__ import annotations

import secrets
import subprocess
import sys
from urllib.parse import quote

from graphguard.config import REPO_ROOT
from graphguard.config import secrets_dir as _secrets_dir

DB, ROLE = "stream", "stream_app"
ENV_FILE = "stream-db.env"
HOST_DSN = "127.0.0.1:5434"
POD_DSN = "10.42.0.1:5434"

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    event_id        bigint PRIMARY KEY,
    seq             bigint NOT NULL,
    event_time      timestamp NOT NULL,
    from_account    text NOT NULL,
    to_account      text NOT NULL,
    amount_paid     double precision NOT NULL,
    score           double precision NOT NULL,
    cold_policy     text NOT NULL,
    rules           text[] NOT NULL DEFAULT '{}',
    alert           boolean NOT NULL DEFAULT false,
    model_version   text NOT NULL,
    model_sha256    text NOT NULL,
    features        double precision[] NOT NULL,
    decided_at      timestamptz NOT NULL DEFAULT now()
);
-- S6.11: when Kafka received the transaction -> decision latency = decided_at - arrived_at.
ALTER TABLE decisions ADD COLUMN IF NOT EXISTS arrived_at timestamp;
CREATE TABLE IF NOT EXISTS feature_sets (
    version     text PRIMARY KEY,
    names       text[] NOT NULL
);
CREATE TABLE IF NOT EXISTS consumer_offsets (
    grp         text NOT NULL,
    topic       text NOT NULL,
    part        int NOT NULL,
    next_offset bigint NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (grp, topic, part)
);
CREATE TABLE IF NOT EXISTS outbox (
    id           bigserial PRIMARY KEY,
    topic        text NOT NULL,
    msg_key      text NOT NULL,
    payload      text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);
CREATE INDEX IF NOT EXISTS outbox_unpublished ON outbox (id) WHERE published_at IS NULL;
CREATE TABLE IF NOT EXISTS dead_letters (
    id           bigserial PRIMARY KEY,
    event_id     bigint,
    kafka_offset bigint NOT NULL,
    reason       text NOT NULL,
    raw          bytea,
    created_at   timestamptz NOT NULL DEFAULT now()
);
-- Late verdicts from the `labels` topic (S6.9): one per transaction, idempotent.
CREATE TABLE IF NOT EXISTS labels (
    event_id       bigint PRIMARY KEY,
    label          boolean NOT NULL,
    label_known_at timestamp NOT NULL,
    channel        text NOT NULL,
    kafka_offset   bigint NOT NULL,
    received_at    timestamptz NOT NULL DEFAULT now()
);
-- The challenger's scores on the champion's own inputs (S6.10). Decides nothing.
CREATE TABLE IF NOT EXISTS decisions_shadow (
    event_id        bigint PRIMARY KEY,
    score           double precision NOT NULL,
    champion_score  double precision NOT NULL,
    model_version   text NOT NULL,
    model_sha256    text NOT NULL,
    decided_at      timestamptz NOT NULL DEFAULT now()
);
-- A record redelivered after a crash must not become a second dead letter (S6.7).
CREATE UNIQUE INDEX IF NOT EXISTS dead_letters_once ON dead_letters (kafka_offset);
"""


def password(secrets_dir=None) -> str:
    path = (secrets_dir or _secrets_dir()) / ENV_FILE
    text = path.read_text()
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)[
        "STREAM_DB_PASSWORD"
    ]


def dsn(where: str = HOST_DSN, secrets_dir=None) -> str:
    return f"postgresql://{ROLE}:{quote(password(secrets_dir), safe='')}@{where}/{DB}"


def connect(where: str = HOST_DSN, secrets_dir=None):
    import psycopg2

    return psycopg2.connect(dsn(where, secrets_dir), connect_timeout=5)


def _new_password() -> str:
    path = REPO_ROOT / ".secrets" / ENV_FILE
    if path.exists():
        return password(REPO_ROOT / ".secrets")
    import os

    pw = secrets.token_urlsafe(24)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"# The stream's Postgres role (S6.6). Never commit.\nSTREAM_DB_PASSWORD={pw}\n")
    return pw


def _superuser(script: str, stdin: str | None = None) -> str:
    from graphguard.ops.backup import PG_CONTAINER, superuser_env

    return subprocess.run(
        ["docker", "exec", "-i", "-e", "PGPASSWORD", PG_CONTAINER, "sh", "-c", script],
        input=stdin, text=True, env=superuser_env(), check=True, capture_output=True,
    ).stdout  # fmt: skip


def setup() -> None:
    """Role + database (as superuser, local socket) and tables (as the role itself)."""
    from graphguard.ops import secrets_registry as reg
    from graphguard.ops.rotate import scram_verifier

    pw = _new_password()
    _superuser('psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres', (
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN "
        f"CREATE ROLE {ROLE} LOGIN; END IF; END $$;\n"
        f"ALTER ROLE {ROLE} PASSWORD '{scram_verifier(pw)}';\n"
    ))  # fmt: skip
    exists = _superuser(f'psql -At -U "$POSTGRES_USER" -d postgres -c '
                        f"\"select 1 from pg_database where datname='{DB}'\"").strip()  # fmt: skip
    if exists != "1":
        _superuser(f'createdb -U "$POSTGRES_USER" -O {ROLE} {DB}')
    _superuser('psql -q -U "$POSTGRES_USER" -d postgres -c "SELECT pg_reload_conf()"')
    with connect(secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute(SCHEMA)
    reg.record(ENV_FILE)


def reset() -> None:
    with connect(secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute(
            "TRUNCATE decisions, decisions_shadow, consumer_offsets, outbox, dead_letters, "
            "labels RESTART IDENTITY"
        )  # fmt: skip


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "setup":
        setup()
        print(f"database {DB}: role {ROLE}, tables ready")
        return 0
    if cmd == "reset":
        reset()
        print("stream tables emptied")
        return 0
    print(f"usage: {argv[0]} setup|reset")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
