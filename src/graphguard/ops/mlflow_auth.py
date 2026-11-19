"""MLflow's login (S5b.7): who may read and write the experiment record.

MLflow's built-in `basic-auth` app, users kept in their own database `mlflow_auth`
(own role, in `pg_access.SERVICES`, so it is access-controlled, backed up and drilled
like every other database). Anonymous requests are refused; a new user can see nothing
until granted (`default_permission = NO_PERMISSIONS`).

    admin     Lubo, the UI (he reads it with `just mlflow-admin-password` in his own terminal)
    trainer   the build-artifacts job (gg-trainer), handed its file by systemd
    research  the Phase 2-4 training / tuning scripts and the tracking tests (root)

Nobody but admin holds MANAGE on the real experiment, so no job can delete runs or
change permissions. Grants are data below; `just mlflow-auth-setup` applies them.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request

from graphguard.config import REPO_ROOT
from graphguard.ops import secrets_registry as reg

SECRETS = REPO_ROOT / ".secrets"
URL = "http://127.0.0.1:5010"
INI = SECRETS / "mlflow-auth.ini"
PGPASS = SECRETS / "mlflow-pgpass"
MLFLOW_UID = 10001
AUTH_DB = "mlflow_auth"
USERS = ("trainer", "research")
# (experiment name, user) -> permission. MANAGE (delete, grant) stays with admin, except
# on the scratch experiment the tracking tests own.
GRANTS: dict[tuple[str, str], str] = {
    ("graphguard", "trainer"): "EDIT",
    ("graphguard", "research"): "EDIT",
    ("graphguard-tests", "research"): "MANAGE",
}


def ini_text(admin_password: str | None) -> str:
    """The auth config (pure, tested). The admin password is present only for the very
    first start, which creates the admin user; afterwards the file holds no secret."""
    lines = [
        "[mlflow]",
        "default_permission = NO_PERMISSIONS",
        f"database_uri = postgresql+psycopg2://{AUTH_DB}@mlflow-db:5432/{AUTH_DB}",
        "admin_username = admin",
        "authorization_function = mlflow.server.auth:authenticate_request_basic_auth",
        "grant_default_workspace_access = false",
    ]
    if admin_password:
        lines.insert(4, f"admin_password = {admin_password}")
    return "\n".join(lines) + "\n"


def user_file(user: str) -> str:
    return f"mlflow-{user}.env"


def _write_in_place(path, text: str, uid: int = 0) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as f:
        f.truncate(0)
        f.write(text)
    os.chmod(path, 0o600)
    os.chown(path, uid, uid)


def _env(name: str) -> dict[str, str]:
    p = SECRETS / name
    if not p.exists():
        return {}
    return dict(
        line.split("=", 1) for line in p.read_text().splitlines() if "=" in line and line[0] != "#"
    )


def credentials(user: str) -> tuple[str, str]:
    e = _env(user_file(user))
    return e["MLFLOW_TRACKING_USERNAME"], e["MLFLOW_TRACKING_PASSWORD"]


# --- REST as admin ------------------------------------------------------------------------
def call(method: str, path: str, body: dict | None, auth: tuple[str, str] | None) -> dict:
    req = urllib.request.Request(
        f"{URL}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )  # fmt: skip
    if auth:
        token = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        return json.loads(raw) if raw else {}


def _experiment_id(name: str, admin) -> str:
    got = call(
        "GET", f"/api/2.0/mlflow/experiments/get-by-name?experiment_name={name}", None, admin
    )
    return got["experiment"]["experiment_id"]


def apply_users_and_grants(admin: tuple[str, str]) -> None:
    for user in USERS:
        username, pw = credentials(user)
        try:
            call(
                "POST",
                "/api/2.0/mlflow/users/create",
                {"username": username, "password": pw},
                admin,
            )
        except urllib.error.HTTPError as e:
            if e.code not in (400, 409):  # exists already: keep it, set the password below
                raise
            call("PATCH", "/api/2.0/mlflow/users/update-password",
                 {"username": username, "password": pw}, admin)  # fmt: skip
    # MLflow 3.17's permission API (v3): one grant per (user, resource).
    for (exp, user), perm in GRANTS.items():
        body = {"username": user, "resource_type": "experiment",
                "resource_id": _experiment_id(exp, admin), "permission": perm}  # fmt: skip
        try:
            call("POST", "/api/3.0/mlflow/users/permissions/grant", body, admin)
        except urllib.error.HTTPError as e:
            if e.code not in (400, 409):  # granted before: replace it
                raise
            revoke = {k: body[k] for k in ("username", "resource_type", "resource_id")}
            call("POST", "/api/3.0/mlflow/users/permissions/revoke", revoke, admin)
            call("POST", "/api/3.0/mlflow/users/permissions/grant", body, admin)


def permission(user: str, exp: str, admin: tuple[str, str]) -> str:
    q = f"username={user}&resource_type=experiment&resource_id={_experiment_id(exp, admin)}"
    return call("GET", f"/api/3.0/mlflow/users/permissions/get?{q}", None, admin)["permission"]


# --- setup (once) -------------------------------------------------------------------------
def _new_user_files() -> None:
    for user in ("admin", *USERS):
        if not (SECRETS / user_file(user)).exists():
            _write_in_place(
                SECRETS / user_file(user),
                f"# MLflow login `{user}` (S5b.7). Never commit.\n"
                f"MLFLOW_TRACKING_USERNAME={user}\n"
                f"MLFLOW_TRACKING_PASSWORD={secrets.token_urlsafe(24)}\n",
            )


def _server_key() -> None:
    """MLflow's CSRF key (its login forms refuse to work without a static one)."""
    path = SECRETS / "mlflow-server.env"
    if not path.exists():
        _write_in_place(
            path,
            "# MLflow's Flask secret key, for CSRF protection (S5b.7). Never commit.\n"
            f"MLFLOW_FLASK_SERVER_SECRET_KEY={secrets.token_urlsafe(32)}\n",
        )


def _auth_db_password() -> str:
    for line in PGPASS.read_text().splitlines():
        if line.split(":")[2:4] == [AUTH_DB, AUTH_DB]:
            return line.split(":", 4)[4]
    pw = secrets.token_urlsafe(24)
    with open(PGPASS, "a") as f:  # in place: owned by MLflow's uid, bind-mounted
        f.write(f"mlflow-db:5432:{AUTH_DB}:{AUTH_DB}:{pw}\n")
    return pw


def _create_role_and_db(pw: str) -> None:
    from graphguard.ops.backup import PG_CONTAINER, superuser_env
    from graphguard.ops.rotate import scram_verifier

    sql = (
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{AUTH_DB}') THEN "
        f"CREATE ROLE {AUTH_DB} LOGIN; END IF; END $$;\n"
        f"ALTER ROLE {AUTH_DB} PASSWORD '{scram_verifier(pw)}';\n"
    )
    run = lambda script, stdin=None: subprocess.run(  # noqa: E731
        ["docker", "exec", "-i", "-e", "PGPASSWORD", PG_CONTAINER, "sh", "-c", script],
        input=stdin, text=True, env=superuser_env(), check=True, capture_output=True,
    )  # fmt: skip
    run('psql -q -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres', sql)
    query = f"select 1 from pg_database where datname='{AUTH_DB}'"
    exists = run(f'psql -At -U "$POSTGRES_USER" -d postgres -c "{query}"').stdout.strip()
    if exists != "1":
        run(f'createdb -U "$POSTGRES_USER" -O {AUTH_DB} {AUTH_DB}')
    run('psql -q -U "$POSTGRES_USER" -d postgres -c "SELECT pg_reload_conf()"')


def _recreate_mlflow() -> None:
    subprocess.run(
        ["docker", "compose", "--env-file", str(SECRETS / "mlflow.env"), "up", "-d", "--no-deps",
         "--force-recreate", "--wait", "mlflow"], cwd=REPO_ROOT, check=True, capture_output=True,
    )  # fmt: skip


def _wait_login(admin: tuple[str, str]) -> None:
    for _ in range(90):
        try:
            call("GET", "/api/2.0/mlflow/users/get?username=admin", None, admin)
            return
        except Exception:  # noqa: BLE001
            time.sleep(1)
    raise TimeoutError("admin cannot log in to MLflow")


def setup() -> None:
    from graphguard.ops import pg_access

    _new_user_files()
    _server_key()
    admin = credentials("admin")
    pg_access.main()  # pg_hba.conf with mlflow_auth (it is in SERVICES)
    _create_role_and_db(_auth_db_password())
    _write_in_place(INI, ini_text(admin[1]), uid=MLFLOW_UID)
    _recreate_mlflow()
    _wait_login(admin)
    apply_users_and_grants(admin)
    _write_in_place(INI, ini_text(None), uid=MLFLOW_UID)  # no secret left in the config
    reg.record(
        "mlflow-auth.ini",
        "mlflow-pgpass",
        "mlflow-server.env",
        *(user_file(u) for u in ("admin", *USERS)),
    )
    print("MLflow login on: admin, " + ", ".join(USERS) + "; anonymous refused")


def rotate_users() -> None:
    """New passwords for trainer and research (admin's: the UI or update-password)."""
    admin = credentials("admin")
    for user in USERS:
        pw = secrets.token_urlsafe(24)
        call(
            "PATCH",
            "/api/2.0/mlflow/users/update-password",
            {"username": user, "password": pw},
            admin,
        )
        reg.set_env_values(SECRETS / user_file(user), {"MLFLOW_TRACKING_PASSWORD": pw})
        call("GET", f"/api/2.0/mlflow/users/get?username={user}", None, credentials(user))
    # and a new CSRF key (signs nothing durable: only logs out open UI sessions)
    reg.set_env_values(SECRETS / "mlflow-server.env",
                       {"MLFLOW_FLASK_SERVER_SECRET_KEY": secrets.token_urlsafe(32)})  # fmt: skip
    _recreate_mlflow()
    _wait_login(admin)
    reg.record("mlflow-server.env", *(user_file(u) for u in USERS))
    print("rotate-mlflow-users: ok")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "setup":
        setup()
    elif cmd == "rotate":
        rotate_users()
    elif cmd == "admin-password":
        print(credentials("admin")[1])
    else:
        print(f"usage: {argv[0]} setup|rotate|admin-password")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
