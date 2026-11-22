"""The live Postgres admits each role to its own database only (S5b.1).

Connects through the published port (127.0.0.1:5434), with each role's real password
from `.secrets/`. Needs GraphGuard's Postgres; CI has none and skips by the explicit
flag, reason printed.
"""

import os
from urllib.parse import unquote, urlsplit

import pytest

from graphguard.config import REPO_ROOT
from graphguard.ops.pg_access import SERVICES, roles_by_database

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1",
        reason="GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1 (no GraphGuard Postgres in this environment)",
    ),
]

SECRETS = REPO_ROOT / ".secrets"


def _env(name: str) -> dict[str, str]:
    return dict(
        ln.split("=", 1)
        for ln in (SECRETS / name).read_text().splitlines()
        if "=" in ln and not ln.startswith("#")
    )


def _passwords() -> dict[str, str]:
    lk = urlsplit(_env("lakekeeper.env")["LAKEKEEPER__PG_DATABASE_URL_WRITE"])
    gov = _env("governance.env")
    return {
        "mlflow_app": _env("mlflow-app.env")["MLFLOW_APP_DB_PASSWORD"],
        "lakekeeper": unquote(lk.password),
        "dex": gov["DEX_DB_PASSWORD"],
        "openfga": gov["OPENFGA_DB_PASSWORD"],
        "lakehouse": _env("lakehouse.env")["LAKEHOUSE_DB_PASSWORD"],
        "stream_app": _env("stream-db.env")["STREAM_DB_PASSWORD"],  # the stream (S6.6)
        "graphguard": _env("mlflow.env")["MLFLOW_DB_PASSWORD"],  # the superuser
        # the investigator demo (S7.1)
        **{
            r: _env("demo-db.env")[f"{r.upper()}_PASSWORD"]
            for r in ("demo_owner", "demo_reader", "demo_writer")
        },  # fmt: skip
        "mlflow_auth": next(  # MLflow's login store (S5b.7): its line in the pgpass file
            ln.split(":", 4)[4]
            for ln in (SECRETS / "mlflow-pgpass").read_text().splitlines()
            if ln.split(":")[2:4] == ["mlflow_auth", "mlflow_auth"]
        ),
    }


def _connects(role: str, db: str, pw: str) -> bool:
    import psycopg2

    try:
        psycopg2.connect(
            host="127.0.0.1", port=5434, user=role, password=pw, dbname=db, connect_timeout=5
        ).close()
        return True
    except psycopg2.OperationalError:
        return False


BY_DB = roles_by_database()
ROLES = sorted(set().union(*BY_DB.values()))
DATABASES = sorted(SERVICES)


@pytest.mark.parametrize("role", ROLES)
def test_each_role_reaches_exactly_its_own_databases(role):
    pw = _passwords()[role]
    reached = {db for db in DATABASES if _connects(role, db, pw)}
    assert reached == {db for db, roles in BY_DB.items() if role in roles}


def test_the_superuser_is_refused_over_the_network():
    pw = _passwords()["graphguard"]
    assert not any(_connects("graphguard", db, pw) for db in [*DATABASES, "postgres"])


def test_a_wrong_password_is_refused():
    assert not _connects("dex", "dex", "wrong")
