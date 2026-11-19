"""Who a lakehouse job is (S5.6d): one Dex machine identity per job.

    builder  writes bronze, silver, gold and sealed (`just lakehouse-build`)
    trainer  reads silver and gold, never sealed     (`just build-artifacts`)
    reader   reads bronze, silver, gold, never sealed (`just sql`, `just store-load`)
    admin    bootstrap and grants only               (`just lakekeeper-init`)

Each job logs in to Dex with the OAuth2 client-credentials flow and shows the
token to Lakekeeper, which decides what it may do (`governance.py`). Dex says
*who*; Lakekeeper says *what*.

Secrets live in `.secrets/` (600, gitignored), generated on the box by
`generate_secrets()` and never printed: `.secrets/identity-<name>.env` per job, and
`.secrets/dex.env` with all of them, because Dex must know every client.

Honest limit: every job runs as root on one box, so a job *could* read another
job's file. The boundary holds for a process that has only its own credentials;
per-job Unix users are S5.8 work.
"""

from __future__ import annotations

import base64
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from graphguard.config import REPO_ROOT
from graphguard.config import secrets_dir as _secrets_dir

IDENTITIES = ("admin", "builder", "trainer", "reader")
SECRETS_DIR = REPO_ROOT / ".secrets"
DEX_URL = os.environ.get("GRAPHGUARD_DEX_URL", "http://127.0.0.1:5556/dex")
TOKEN_URL = f"{DEX_URL}/token"
# The issuer is Dex's name on graphguard-net: Lakekeeper (in Docker) checks tokens
# against it. Jobs on the host only call the token endpoint, so they never need it.
ISSUER = "http://graphguard-dex:5556/dex"
SCOPE = "openid"


def client_id(name: str) -> str:
    if name not in IDENTITIES:
        raise ValueError(f"unknown identity {name!r}; one of {IDENTITIES}")
    return f"gg-{name}"


def _secret_env_name(name: str) -> str:
    return f"GG_{name.upper()}_SECRET"


@dataclass(frozen=True)
class Identity:
    name: str
    client_id: str
    secret: str = field(repr=False)


def _read_env(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def identity_file(name: str, secrets_dir: Path | None = None) -> Path:
    client_id(name)  # validates the name
    return (secrets_dir or _secrets_dir()) / f"identity-{name}.env"


def read_identity(name: str, secrets_dir: Path | None = None) -> Identity:
    path = identity_file(name, secrets_dir)
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `just identity-secrets` first")
    env = _read_env(path)
    return Identity(name=name, client_id=env["GG_CLIENT_ID"], secret=env["GG_CLIENT_SECRET"])


def _write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def generate_secrets(secrets_dir: Path = SECRETS_DIR) -> list[Path]:
    """Create any missing secret files (600). Never overwrites: a secret that
    exists stays, so re-running is safe. Returns the files it created.

    Files: identity-<name>.env per identity, dex.env (Dex's DB password and every
    client secret), openfga.env (its datastore URL and preshared key),
    lakekeeper-authz.env (only the OpenFGA key), and governance.env (the two DB
    passwords and the OpenFGA key, for setup).
    """
    created: list[Path] = []
    secrets_dir.mkdir(mode=0o700, exist_ok=True)

    client_secrets = {}
    for name in IDENTITIES:
        path = identity_file(name, secrets_dir)
        if path.exists():
            client_secrets[name] = read_identity(name, secrets_dir).secret
            continue
        client_secrets[name] = secrets.token_urlsafe(32)
        _write_private(
            path,
            f"# Dex client for the `{name}` lakehouse identity (S5.6d). Never commit.\n"
            f"GG_CLIENT_ID={client_id(name)}\nGG_CLIENT_SECRET={client_secrets[name]}\n",
        )
        created.append(path)

    gov_path = secrets_dir / "governance.env"
    if gov_path.exists():
        gov = _read_env(gov_path)
    else:
        gov = {
            "DEX_DB_PASSWORD": secrets.token_urlsafe(24),
            "OPENFGA_DB_PASSWORD": secrets.token_urlsafe(24),
            "OPENFGA_PRESHARED_KEY": secrets.token_urlsafe(32),
        }
        _write_private(
            gov_path,
            "# S5.6d: database passwords and the OpenFGA key. Never commit.\n"
            + "".join(f"{k}={v}\n" for k, v in gov.items()),
        )
        created.append(gov_path)

    dex_path = secrets_dir / "dex.env"
    if not dex_path.exists():
        lines = [f"DEX_DB_PASSWORD={gov['DEX_DB_PASSWORD']}"]
        lines += [f"{_secret_env_name(n)}={client_secrets[n]}" for n in IDENTITIES]
        _write_private(
            dex_path, "# Dex's environment (S5.6d). Never commit.\n" + "\n".join(lines) + "\n"
        )
        created.append(dex_path)

    fga_path = secrets_dir / "openfga.env"
    if not fga_path.exists():
        _write_private(
            fga_path,
            "# OpenFGA's environment (S5.6d). Never commit.\n"
            "OPENFGA_DATASTORE_ENGINE=postgres\n"
            "OPENFGA_DATASTORE_URI=postgres://openfga:"
            f"{urllib.parse.quote(gov['OPENFGA_DB_PASSWORD'], safe='')}"
            "@graphguard-mlflow-db:5432/openfga?sslmode=disable\n"
            "OPENFGA_AUTHN_METHOD=preshared\n"
            f"OPENFGA_AUTHN_PRESHARED_KEYS={gov['OPENFGA_PRESHARED_KEY']}\n",
        )
        created.append(fga_path)

    # Lakekeeper gets only the key it needs, not the rest of governance.env.
    lk_path = secrets_dir / "lakekeeper-authz.env"
    if not lk_path.exists():
        _write_private(
            lk_path,
            "# Lakekeeper's key to OpenFGA (S5.6d). Never commit.\n"
            f"LAKEKEEPER__OPENFGA__API_KEY={gov['OPENFGA_PRESHARED_KEY']}\n",
        )
        created.append(lk_path)
    return created


class TokenError(RuntimeError):
    """Dex refused the login. Carries the status, never the secret."""


def fetch_token(identity: Identity, token_url: str = TOKEN_URL) -> str:
    """Log in to Dex as `identity` (client credentials) and return the access token."""
    basic = base64.b64encode(f"{identity.client_id}:{identity.secret}".encode()).decode()
    req = urllib.request.Request(
        token_url,
        method="POST",
        data=urllib.parse.urlencode({"grant_type": "client_credentials", "scope": SCOPE}).encode(),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())["access_token"]
    except urllib.error.HTTPError as e:
        raise TokenError(f"Dex refused {identity.client_id}: HTTP {e.code}") from None


def pyiceberg_auth(identity: Identity, token_url: str = TOKEN_URL) -> dict[str, str]:
    """RestCatalog properties that make PyIceberg log in as `identity` itself
    (and refresh the token when it expires)."""
    return {
        "credential": f"{identity.client_id}:{identity.secret}",
        "oauth2-server-uri": token_url,
        "scope": SCOPE,
    }
