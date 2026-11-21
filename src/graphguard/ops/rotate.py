"""Rotate every secret generated on the box, one kind at a time (S5b.6).

    just rotate-pg <role>       mlflow_app | lakekeeper | dex | openfga | lakehouse | superuser
    just rotate-identities      the four Dex client secrets
    just rotate-openfga         the OpenFGA preshared key (OpenFGA <-> Lakekeeper)
    just rotate-redis           the three Redis users, scorer rolled with zero downtime

Each one: make the new secret, apply it where it is checked, update the files its
holder reads (in place: bind mounts keep seeing them), restart only that GraphGuard
container, then **prove** the holder works with the new secret — and put everything back
if it does not. New Postgres passwords travel as SCRAM verifiers, so the plain password
never reaches a command line or a database log. Nothing here touches anything but
GraphGuard's own containers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote

from graphguard.config import REPO_ROOT
from graphguard.ops import secrets_registry as reg

SECRETS = REPO_ROOT / ".secrets"
COMPOSE = ["docker", "compose", "--env-file", str(SECRETS / "mlflow.env")]


# --- pure helpers (tested) -----------------------------------------------------------------
def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def scram_verifier(password: str, salt: bytes | None = None, iterations: int = 4096) -> str:
    """Postgres's SCRAM-SHA-256 verifier for `password` (RFC 5802 / 7677): what
    `ALTER ROLE ... PASSWORD` stores. Sending this instead of the password keeps the
    password itself out of the server, its logs and every command line."""
    salt = salt or secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", "sha256").digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", "sha256").digest()
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def alter_role_sql(role: str, verifier: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", role) or "'" in verifier:
        raise ValueError("unsafe role name or verifier")
    return f"ALTER ROLE \"{role}\" PASSWORD '{verifier}';\n"


def with_url_password(url: str, password: str) -> str:
    """Swap the password inside `scheme://user:password@host/...`."""
    encoded = quote(password, safe="")
    new, n = re.subn(
        r"^([a-z+]+://[^:/@]+:)[^@]*(@)", lambda m: m.group(1) + encoded + m.group(2), url
    )
    if n != 1:
        raise ValueError("no password in that URL")
    return new


def pgpass_with_password(line: str, password: str) -> str:
    host, port, db, user, _ = line.strip().split(":", 4)
    return f"{host}:{port}:{db}:{user}:{password}"


def pgpass_set(text: str, db: str, user: str, password: str) -> str:
    """Change only the line for (db, user); every other line stays (pure, tested)."""
    out, hit = [], 0
    for line in text.splitlines():
        parts = line.split(":", 4)
        if len(parts) == 5 and parts[2] == db and parts[3] == user:
            line, hit = pgpass_with_password(line, password), hit + 1
        out.append(line)
    if hit != 1:
        raise ValueError(f"pgpass: {hit} lines for {db}/{user}, want exactly 1")
    return "\n".join(out) + "\n"


# --- the box ------------------------------------------------------------------------------
def _env(name: str) -> dict[str, str]:
    out = {}
    for line in (SECRETS / name).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _snapshot(files: list[str]) -> dict[str, str]:
    return {f: (SECRETS / f).read_text() for f in files}


def _restore(snap: dict[str, str]) -> None:
    for f, text in snap.items():
        p = SECRETS / f
        with open(p, "r+") as h:  # in place: same inode, same owner
            h.truncate(0)
            h.write(text)


def _alter_role(role: str, password: str) -> None:
    from graphguard.ops.backup import PG_CONTAINER, superuser_env

    subprocess.run(
        ["docker", "exec", "-i", "-e", "PGPASSWORD", PG_CONTAINER,
         "sh", "-c", 'psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres'],
        input=alter_role_sql(role, scram_verifier(password)), text=True,
        env=superuser_env(), check=True, capture_output=True,
    )  # fmt: skip


def _recreate(service: str) -> None:
    subprocess.run(
        [*COMPOSE, "up", "-d", "--no-deps", "--force-recreate", "--wait", service],
        cwd=REPO_ROOT, check=True, capture_output=True,
    )  # fmt: skip


def _restart(service: str) -> None:
    subprocess.run([*COMPOSE, "restart", service], cwd=REPO_ROOT, check=True, capture_output=True)


def _until(check: Callable[[], object], what: str, seconds: int = 90) -> None:
    last: Exception | None = None
    for _ in range(seconds):
        try:
            check()
            return
        except Exception as e:  # noqa: BLE001 (any failure means "not yet")
            last = e
            time.sleep(1)
    raise RuntimeError(f"{what} did not come back: {type(last).__name__}: {last}")


# --- health checks: the holder really works with the new secret -------------------------
def mlflow_ok() -> None:
    from graphguard.ops.mlflow_auth import call, credentials

    auth = credentials("admin") if (SECRETS / "mlflow-admin.env").exists() else None
    got = call("GET", "/api/2.0/mlflow/experiments/search?max_results=1", None, auth)
    assert "experiments" in got


def catalog_ok() -> None:
    from graphguard.lakehouse.catalog import open_catalog

    cat = open_catalog("reader")
    assert cat.load_table("silver.transactions").scan(limit=1).to_arrow().num_rows == 1


def dex_ok() -> None:
    from graphguard.lakehouse.identity import IDENTITIES, fetch_token, read_identity

    for name in IDENTITIES:
        assert fetch_token(read_identity(name))


def lakehouse_role_ok() -> None:
    import sqlalchemy

    from graphguard.lakehouse.catalog import default_uri

    with sqlalchemy.create_engine(default_uri()).connect() as c:
        assert c.execute(sqlalchemy.text("select 1")).scalar() == 1


def superuser_ok() -> None:
    from graphguard.ops.backup import _psql

    assert _psql("postgres", "select 1") == "1"


# --- Postgres roles -----------------------------------------------------------------------
@dataclass(frozen=True)
class RolePlan:
    pg_role: str  # the role's name in Postgres
    files: list[str]  # the .secrets/ files its holder reads
    write: Callable[[str], None]  # put the new password into those files
    restart: Callable[[], None]  # make the holder read them
    check: Callable[[], None]  # prove the holder works


def _pgpass_update(db: str, user: str, pw: str) -> None:
    with open(SECRETS / "mlflow-pgpass", "r+") as h:  # in place: owned by MLflow's uid
        text = h.read()
        h.seek(0)
        h.truncate(0)
        h.write(pgpass_set(text, db, user, pw))


def _write_mlflow_app(pw: str) -> None:
    reg.set_env_values(SECRETS / "mlflow-app.env", {"MLFLOW_APP_DB_PASSWORD": pw})
    _pgpass_update("mlflow", "mlflow_app", pw)


def _write_mlflow_auth(pw: str) -> None:
    _pgpass_update("mlflow_auth", "mlflow_auth", pw)


def _write_lakekeeper(pw: str) -> None:
    env = _env("lakekeeper.env")
    keys = ("LAKEKEEPER__PG_DATABASE_URL_READ", "LAKEKEEPER__PG_DATABASE_URL_WRITE")
    reg.set_env_values(SECRETS / "lakekeeper.env", {k: with_url_password(env[k], pw) for k in keys})


def _write_dex_db(pw: str) -> None:
    reg.set_env_values(SECRETS / "governance.env", {"DEX_DB_PASSWORD": pw})
    reg.set_env_values(SECRETS / "dex.env", {"DEX_DB_PASSWORD": pw})


def _write_openfga_db(pw: str) -> None:
    reg.set_env_values(SECRETS / "governance.env", {"OPENFGA_DB_PASSWORD": pw})
    url = with_url_password(_env("openfga.env")["OPENFGA_DATASTORE_URI"], pw)
    reg.set_env_values(SECRETS / "openfga.env", {"OPENFGA_DATASTORE_URI": url})


def _roll_consumer() -> None:
    """The consumer pod reads stream-db.env from its Secret: refresh it, restart the pod."""
    from graphguard.stream.k8s import secret_manifest, shadow_secret_manifest

    kubectl = ["k3s", "kubectl"]
    for manifest in (secret_manifest(), shadow_secret_manifest()):
        subprocess.run([*kubectl, "apply", "-f", "-"], input=manifest, text=True,
                       check=True, capture_output=True)  # fmt: skip
    for name in ("graphguard-consumer", "graphguard-shadow"):  # both read stream-db.env
        deploy = ["-n", "graphguard", f"deploy/{name}"]
        subprocess.run([*kubectl, "rollout", "restart", *deploy], check=True, capture_output=True)
        subprocess.run([*kubectl, "rollout", "status", *deploy, "--timeout=180s"], check=True,
                       capture_output=True)  # fmt: skip


def stream_db_ok() -> None:
    from graphguard.stream import db

    with db.connect(secrets_dir=SECRETS) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1")


def _plan(role: str) -> RolePlan:
    none = lambda: None  # noqa: E731
    plans = {
        "mlflow_app": lambda: RolePlan(
            "mlflow_app", ["mlflow-app.env", "mlflow-pgpass"], _write_mlflow_app,
            lambda: _restart("mlflow"), mlflow_ok),
        "mlflow_auth": lambda: RolePlan(
            "mlflow_auth", ["mlflow-pgpass"], _write_mlflow_auth,
            lambda: _restart("mlflow"), mlflow_ok),
        "lakekeeper": lambda: RolePlan(
            "lakekeeper", ["lakekeeper.env"], _write_lakekeeper,
            lambda: _recreate("lakekeeper"), catalog_ok),
        "dex": lambda: RolePlan(
            "dex", ["governance.env", "dex.env"], _write_dex_db, lambda: _recreate("dex"), dex_ok),
        "openfga": lambda: RolePlan(
            "openfga", ["governance.env", "openfga.env"], _write_openfga_db,
            lambda: _recreate("openfga"), catalog_ok),
        "lakehouse": lambda: RolePlan(
            _env("lakehouse.env")["LAKEHOUSE_DB_USER"], ["lakehouse.env"],
            lambda pw: reg.set_env_values(SECRETS / "lakehouse.env", {"LAKEHOUSE_DB_PASSWORD": pw}),
            none, lakehouse_role_ok),
        "stream_app": lambda: RolePlan(
            "stream_app", ["stream-db.env"],
            lambda pw: reg.set_env_values(SECRETS / "stream-db.env", {"STREAM_DB_PASSWORD": pw}),
            _roll_consumer, stream_db_ok),
        "superuser": lambda: RolePlan(
            _env("mlflow.env")["MLFLOW_DB_USER"], ["mlflow.env"],
            lambda pw: reg.set_env_values(SECRETS / "mlflow.env", {"MLFLOW_DB_PASSWORD": pw}),
            none, superuser_ok),
    }  # fmt: skip
    if role not in plans:
        raise SystemExit(f"unknown role {role}; one of {', '.join(plans)}")
    return plans[role]()


def rotate_pg(role: str) -> None:
    plan = _plan(role)
    pg_role, files, write, restart, check = (
        plan.pg_role,
        plan.files,
        plan.write,
        plan.restart,
        plan.check,
    )
    snap = _snapshot(files)
    old = _old_pg_password(role)
    pw = new_secret(24)
    try:
        # The superuser's own change: ALTER first with the old password still in the file.
        _alter_role(pg_role, pw)
        write(pw)
        restart()
        _until(check, f"{role} after rotation")
    except Exception:
        print(f"rotate-pg {role}: FAILED — putting the old password back", file=sys.stderr)
        _restore(snap)
        _alter_role(pg_role, old)
        restart()
        raise
    reg.record(*files)
    print(f"rotate-pg {role}: ok ({', '.join(files)})")


def _old_pg_password(role: str) -> str:
    return {
        "mlflow_app": lambda: _env("mlflow-app.env")["MLFLOW_APP_DB_PASSWORD"],
        "mlflow_auth": lambda: next(
            ln.split(":", 4)[4]
            for ln in (SECRETS / "mlflow-pgpass").read_text().splitlines()
            if ln.split(":")[2:4] == ["mlflow_auth", "mlflow_auth"]
        ),
        "lakekeeper": lambda: re.search(
            r"://[^:]+:([^@]*)@", _env("lakekeeper.env")["LAKEKEEPER__PG_DATABASE_URL_WRITE"]
        ).group(1),
        "dex": lambda: _env("governance.env")["DEX_DB_PASSWORD"],
        "openfga": lambda: _env("governance.env")["OPENFGA_DB_PASSWORD"],
        "lakehouse": lambda: _env("lakehouse.env")["LAKEHOUSE_DB_PASSWORD"],
        "stream_app": lambda: _env("stream-db.env")["STREAM_DB_PASSWORD"],
        "superuser": lambda: _env("mlflow.env")["MLFLOW_DB_PASSWORD"],
    }[role]()


# --- Dex client secrets -----------------------------------------------------------------
def rotate_identities() -> None:
    from graphguard.lakehouse.identity import (
        IDENTITIES,
        Identity,
        TokenError,
        _secret_env_name,
        client_id,
        fetch_token,
    )

    files = ["dex.env", *[f"identity-{n}.env" for n in IDENTITIES]]
    snap = _snapshot(files)
    old = {n: _env(f"identity-{n}.env")["GG_CLIENT_SECRET"] for n in IDENTITIES}
    new = {n: new_secret() for n in IDENTITIES}
    try:
        for n in IDENTITIES:
            reg.set_env_values(SECRETS / f"identity-{n}.env", {"GG_CLIENT_SECRET": new[n]})
        reg.set_env_values(SECRETS / "dex.env", {_secret_env_name(n): new[n] for n in IDENTITIES})
        _recreate("dex")
        _until(dex_ok, "Dex logins with the new secrets")
        for n in IDENTITIES:  # and the old ones are refused
            try:
                fetch_token(Identity(n, client_id(n), old[n]))
            except TokenError:
                continue
            raise RuntimeError(f"Dex still accepts the old {n} secret")
    except Exception:
        print("rotate-identities: FAILED — putting the old secrets back", file=sys.stderr)
        _restore(snap)
        _recreate("dex")
        raise
    reg.record(*files)
    print(f"rotate-identities: ok ({len(IDENTITIES)} new secrets, old ones refused)")


# --- OpenFGA preshared key ----------------------------------------------------------------
def rotate_openfga() -> None:
    files = ["governance.env", "openfga.env", "lakekeeper-authz.env"]
    snap = _snapshot(files)
    key = new_secret()
    try:
        reg.set_env_values(SECRETS / "governance.env", {"OPENFGA_PRESHARED_KEY": key})
        reg.set_env_values(SECRETS / "openfga.env", {"OPENFGA_AUTHN_PRESHARED_KEYS": key})
        reg.set_env_values(SECRETS / "lakekeeper-authz.env", {"LAKEKEEPER__OPENFGA__API_KEY": key})
        _recreate("openfga")
        _recreate("lakekeeper")
        _until(catalog_ok, "a governed catalog read with the new OpenFGA key")
    except Exception:
        print("rotate-openfga: FAILED — putting the old key back", file=sys.stderr)
        _restore(snap)
        _recreate("openfga")
        _recreate("lakekeeper")
        raise
    reg.record(*files)
    print("rotate-openfga: ok")


# --- Redis --------------------------------------------------------------------------------
RAYSERVICE = REPO_ROOT / "k8s" / "rayservice.yaml"
REV_KEY = "graphguard.ai/redis-secret-rev"


def bump_rev(text: str, rev: str) -> str:
    """Set the scorer pod annotation that forces a zero-downtime RayService upgrade."""
    new, n = re.subn(rf'({re.escape(REV_KEY)}: )"[^"]*"', rf'\g<1>"{rev}"', text)
    if n != 1:
        raise ValueError(f"{REV_KEY} not found exactly once in rayservice.yaml")
    return new


def _write_acl(passwords: dict[str, str | list[str]]) -> None:
    from graphguard.serving.redis_acl import ACL_FILE, acl_lines

    with open(ACL_FILE, "r+") as h:  # in place: the container's bind mount sees it
        h.truncate(0)
        h.write("\n".join(acl_lines(passwords)) + "\n")


def _redis_ping(user: str, password: str) -> None:
    from urllib.parse import urlsplit

    import redis

    from graphguard.serving.store import REDIS_BASE

    base = urlsplit(REDIS_BASE)
    host, port = base.hostname, base.port
    assert redis.Redis(
        host=host, port=port, username=user, password=password, socket_timeout=3
    ).ping()


def _redis_refused(user: str, password: str) -> bool:
    try:
        _redis_ping(user, password)
    except Exception:  # noqa: BLE001
        return True
    return False


def _store_load() -> None:
    subprocess.run([str(REPO_ROOT / ".tools/bin/just"), "store-load"], cwd=REPO_ROOT, check=True)


def _roll_scorer(rev: str) -> None:
    from graphguard.serving.redis_acl import k8s_secret_manifest

    subprocess.run(["k3s", "kubectl", "apply", "-f", "-"], input=k8s_secret_manifest(), text=True,
                   check=True, capture_output=True)  # fmt: skip
    RAYSERVICE.write_text(bump_rev(RAYSERVICE.read_text(), rev))
    subprocess.run(
        ["k3s", "kubectl", "apply", "-f", str(RAYSERVICE)], check=True, capture_output=True
    )
    _until(_scorer_rolled(rev), "the scorer on the new Redis password", seconds=900)


def _scorer_rolled(rev: str) -> Callable[[], None]:
    def check() -> None:
        out = subprocess.run(
            ["k3s", "kubectl", "get", "pods", "-n", "graphguard", "-o", "json"],
            check=True, capture_output=True, text=True,
        ).stdout  # fmt: skip
        pods = json.loads(out)["items"]
        heads = [
            p for p in pods if p["metadata"].get("labels", {}).get("ray.io/node-type") == "head"
        ]
        assert heads and all(
            p["metadata"].get("annotations", {}).get(REV_KEY) == rev
            and p["status"].get("phase") == "Running"
            and all(c.get("ready") for c in p["status"].get("containerStatuses", []))
            for p in heads
        )
        status = subprocess.run(
            ["k3s", "kubectl", "get", "rayservice", "graphguard-scorer", "-n", "graphguard", "-o",
             "jsonpath={.status.serviceStatus}"], check=True, capture_output=True, text=True,
        ).stdout  # fmt: skip
        assert status == "Running"

    return check


def rotate_redis() -> None:
    from graphguard.serving.redis_acl import ENV_FILE, USERS, password_var

    users = list(USERS)
    files = ["redis.env", "redis-users.acl", *[f"redis-{u}.env" for u in users]]
    snap = _snapshot(files)
    old = {u: _env("redis.env")[password_var(u)] for u in users}
    new = {u: new_secret() for u in users}
    rev = time.strftime("%Y%m%d%H%M%S")
    # 1. both passwords valid; one Redis restart; refill
    _write_acl({u: [old[u], new[u]] for u in users})
    _restart("redis")
    _until(lambda: _redis_ping("tests", new["tests"]), "Redis with both passwords")
    _store_load()
    # 2. every client to the new password: files, then the scorer (zero-downtime upgrade)
    reg.set_env_values(ENV_FILE, {password_var(u): new[u] for u in users})
    for u in users:
        reg.set_env_values(SECRETS / f"redis-{u}.env", {password_var(u): new[u]})
    _roll_scorer(rev)
    # 3. only the new password; second restart; refill with it
    _write_acl(new)
    _restart("redis")
    _until(lambda: _redis_ping("tests", new["tests"]), "Redis with the new passwords")
    _store_load()
    refused = [u for u in users if not _redis_refused(u, old[u])]
    if refused:
        _restore(snap)
        raise RuntimeError(f"Redis still accepts the old password for {refused}")
    reg.record(*files)
    print("rotate-redis: ok (old passwords refused, scorer rolled)")


def main(argv: list[str]) -> int:
    kind = argv[1] if len(argv) > 1 else ""
    if kind == "pg" and len(argv) > 2:
        rotate_pg(argv[2])
    elif kind == "identities":
        rotate_identities()
    elif kind == "openfga":
        rotate_openfga()
    elif kind == "redis":
        rotate_redis()
    else:
        print(f"usage: {argv[0]} pg <role>|identities|openfga|redis")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
