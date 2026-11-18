"""Redis users for the online store (S5b.1): one per client, only the commands it uses.

    just redis-secrets     # generate passwords (once) and the ACL file Redis loads

The store's code uses five commands -- PING, HGETALL, HSET, SCAN, DEL (pipelines are
plain command batches) -- plus SELECT for the tests' own database. So:

    scorer   read accounts:           PING HGETALL          on gg:acct:*
    loader   fill and prune:          PING HGETALL HSET SCAN DEL   on gg:acct:*
    tests    the same, test keys:     ... + SELECT          on test-*
    default  OFF (an unauthenticated client can do nothing)

Nobody gets scripting (EVAL/FUNCTION: RediShell, CVE-2025-49844), admin commands,
KEYS, FLUSHALL, RESTORE or MIGRATE. `CLIENT SETINFO` is allowed because redis-py sends
it on connect. The ACL file holds SHA-256 hashes, never a password; the passwords live
in `.secrets/redis.env` (600), and the scorer's URL in a Kubernetes Secret.

Redis's ACL cannot confine a user to a database number, so `tests` is confined by key
pattern instead; SCAN (which lists key *names*) is keyless in Redis and therefore not
pattern-confined -- account ids are not secret, and no user can read another's values.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path

from graphguard.config import REPO_ROOT

SECRETS_DIR = REPO_ROOT / ".secrets"
ENV_FILE = SECRETS_DIR / "redis.env"
ACL_FILE = SECRETS_DIR / "redis-users.acl"
# The uid Redis runs as (compose `user:`). Not the image's 999: on this box uid 999 is
# another app's host user, so the file must not be owned by it. 10379 is unused.
REDIS_UID, REDIS_GID = 10379, 10379

READ = ("ping", "hgetall", "client|setinfo")
WRITE = (*READ, "hset", "scan", "del")
USERS: dict[str, tuple[tuple[str, ...], str]] = {
    "scorer": (READ, "gg:acct:*"),
    "loader": (WRITE, "gg:acct:*"),
    "tests": ((*WRITE, "select"), "test-*"),
}
NEVER = (
    "eval",
    "evalsha",
    "function",
    "script",
    "keys",
    "flushall",
    "flushdb",
    "restore",
    "migrate",
    "config",
    "debug",
    "module",
    "acl",
    "shutdown",
)


def password_var(user: str) -> str:
    if user not in USERS:
        raise ValueError(f"unknown Redis user {user!r}; one of {tuple(USERS)}")
    return f"GG_REDIS_{user.upper()}_PASSWORD"


def acl_lines(passwords: dict[str, str]) -> list[str]:
    """The ACL file's lines. Pure, so the security rules are testable."""
    lines = ["user default off resetpass resetkeys resetchannels -@all"]
    for user, (commands, pattern) in USERS.items():
        digest = hashlib.sha256(passwords[user].encode()).hexdigest()
        allowed = " ".join(f"+{c}" for c in commands)
        lines.append(
            f"user {user} on resetpass #{digest} resetkeys ~{pattern} resetchannels -@all {allowed}"
        )
    return lines


def _read_env(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )


def generate(secrets_dir: Path = SECRETS_DIR, chown: bool = True) -> list[Path]:
    """Create the passwords once (never overwritten) and (re)write the ACL file from
    them. Returns the files written."""
    env_file, acl_file = secrets_dir / ENV_FILE.name, secrets_dir / ACL_FILE.name
    written = []
    if not env_file.exists():
        fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("# Redis users (S5b.1). Never commit.\n")
            for user in USERS:
                f.write(f"{password_var(user)}={secrets.token_urlsafe(32)}\n")
        written.append(env_file)
    env = _read_env(env_file)
    passwords = {u: env[password_var(u)] for u in USERS}
    acl_file.write_text("\n".join(acl_lines(passwords)) + "\n")
    os.chmod(acl_file, 0o600)
    if chown:  # Redis runs as uid 999 in its container and must read the file
        os.chown(acl_file, REDIS_UID, REDIS_GID)
    written.append(acl_file)
    return written


def password(user: str, secrets_dir: Path = SECRETS_DIR) -> str:
    """A Redis user's password from `.secrets/redis.env`. Missing -> an error, never a
    silent connection without auth."""
    env_file = secrets_dir / ENV_FILE.name
    if not env_file.exists():
        raise FileNotFoundError(f"{env_file} missing: run `just redis-secrets`")
    env = _read_env(env_file)
    var = password_var(user)
    if not env.get(var):
        raise KeyError(f"{var} missing from {env_file}")
    return env[var]


POD_REDIS = "10.42.0.1:6380"  # the k3s pod bridge (cni0) on the host


def k8s_secret_manifest() -> str:
    """The scorer's Redis URL as a Kubernetes Secret, for `kubectl apply -f -` on stdin
    (the password never appears in a command line or a file outside .secrets/)."""
    import base64
    import json
    from urllib.parse import quote

    url = f"redis://scorer:{quote(password('scorer'), safe='')}@{POD_REDIS}/0"
    return json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "type": "Opaque",
            "metadata": {
                "name": "graphguard-redis",
                "namespace": "graphguard",
                "labels": {"app.kubernetes.io/part-of": "graphguard"},
            },
            "data": {"url": base64.b64encode(url.encode()).decode()},
        }
    )


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["k8s-secret"]:
        print(k8s_secret_manifest())
    else:
        for p in generate():
            print(f"wrote {p.relative_to(REPO_ROOT)}")
