"""Every secret GraphGuard owns, who holds it, how it rotates, and a check (S5b.6).

The registry is public on purpose: names, holders and rotation methods, never values.
The dates of the last rotation live in `private/secrets/ledger.json`.

`just secrets-status` fails when a secret is overdue, a file in `.secrets/` is not in
the registry (an untracked secret), a registered file is missing, or a file's mode or
owner is not what it should be. `just secret-set <name>` types a console key into the
box with hidden input — keys are never pasted into chat.
"""

from __future__ import annotations

import datetime as dt
import getpass
import json
import os
import re
import stat
import sys
from dataclasses import dataclass

from graphguard.config import REPO_ROOT

SECRETS = REPO_ROOT / ".secrets"
LEDGER = REPO_ROOT / "private" / "secrets" / "ledger.json"
CONSOLE_DAYS = 365  # cloud-console keys: kept by decision (S5b.6 slim), reviewed yearly
BOX_DAYS = 180  # generated on the box, rotated by `just rotate-*`


@dataclass(frozen=True)
class Secret:
    holder: str
    rotation: str  # the command or the place to rotate it
    max_age_days: int | None  # None: not rotatable in place (recorded why)
    owner_uid: int = 0  # who must own the file (a container reads it)


S = Secret
REGISTRY: dict[str, Secret] = {
    # Cloud-console keys (Lubo, in the console; typed in with `just secret-set`).
    "aws.env": S("nobody live (S5.6b SQL-catalog rollback)", "AWS IAM console", CONSOLE_DAYS),
    "lakekeeper-aws.env": S(
        "Lakekeeper (vending)", "AWS IAM console, two-key overlap", CONSOLE_DAYS
    ),
    "backup-aws.env": S("backup timer", "AWS IAM console, two-key overlap", CONSOLE_DAYS),
    "models-publisher-aws.env": S(
        "just model-publish (host)", "AWS IAM console, two-key overlap", CONSOLE_DAYS
    ),
    "models-reader-aws.env": S(
        "scorer (via k8s Secret graphguard-model)", "AWS IAM console, two-key overlap", CONSOLE_DAYS
    ),
    "hetzner-readonly.env": S(
        "edge watchdog", "Hetzner console: new token, delete old", CONSOLE_DAYS
    ),
    "kaggle.json": S("bootstrap download", "Kaggle account settings", CONSOLE_DAYS),
    "backup-restic-password": S(
        "backup timer + Lubo's manager", "restic key add / key remove", CONSOLE_DAYS
    ),
    # Generated on the box.
    "mlflow.env": S("Postgres superuser (admin, backups)", "just rotate-pg superuser", BOX_DAYS),
    "mlflow-app.env": S("MLflow (role mlflow_app)", "just rotate-pg mlflow_app", BOX_DAYS),
    "mlflow-auth.ini": S(
        "MLflow login config (holds no secret after the first start)",
        "just mlflow-auth-setup rewrites it",
        None,
        owner_uid=10001,
    ),
    "mlflow-server.env": S("MLflow (CSRF key)", "just rotate-mlflow-users", BOX_DAYS),
    "mlflow-admin.env": S("Lubo, MLflow UI", "just rotate-mlflow-users (admin: UI)", BOX_DAYS),
    "mlflow-trainer.env": S("build-artifacts (gg-trainer)", "just rotate-mlflow-users", BOX_DAYS),
    "mlflow-research.env": S(
        "Phase 2-4 scripts, tracking tests", "just rotate-mlflow-users", BOX_DAYS
    ),
    "mlflow-pgpass": S(
        "MLflow (PGPASSFILE)", "just rotate-pg mlflow_app", BOX_DAYS, owner_uid=10001
    ),
    "lakehouse.env": S("stale SQL catalog (role lakehouse)", "just rotate-pg lakehouse", BOX_DAYS),
    "lakekeeper.env": S(
        "Lakekeeper (DB URLs + encryption key)",
        "just rotate-pg lakekeeper (the encryption key: never in place, needs re-encryption)",
        BOX_DAYS,
    ),
    "governance.env": S(
        "setup: Dex/OpenFGA DB passwords, OpenFGA key",
        "just rotate-pg dex|openfga, rotate-openfga",
        BOX_DAYS,
    ),
    "dex.env": S(
        "Dex (DB password, client secrets)", "just rotate-pg dex, rotate-identities", BOX_DAYS
    ),
    "openfga.env": S(
        "OpenFGA (DB URL, preshared key)", "just rotate-pg openfga, rotate-openfga", BOX_DAYS
    ),
    "lakekeeper-authz.env": S("Lakekeeper -> OpenFGA key", "just rotate-openfga", BOX_DAYS),
    "identity-admin.env": S("lakekeeper-init", "just rotate-identities", BOX_DAYS),
    "identity-builder.env": S("lakehouse-build (gg-builder)", "just rotate-identities", BOX_DAYS),
    "identity-trainer.env": S("build-artifacts (gg-trainer)", "just rotate-identities", BOX_DAYS),
    "identity-reader.env": S(
        "store-load, sql, notebook (gg-reader)", "just rotate-identities", BOX_DAYS
    ),
    "redis.env": S("all Redis users (admin copy)", "just rotate-redis", BOX_DAYS),
    "redis-scorer.env": S("scorer (via k8s Secret)", "just rotate-redis", BOX_DAYS),
    "redis-loader.env": S("store-load", "just rotate-redis", BOX_DAYS),
    "redis-tests.env": S("live tests", "just rotate-redis", BOX_DAYS),
    "redis-users.acl": S("Redis (hashes only)", "just rotate-redis", BOX_DAYS, owner_uid=10379),
}


# --- the check --------------------------------------------------------------------------
def problems(
    files: dict[str, tuple[int, int]],  # name -> (mode bits, owner uid)
    ledger: dict[str, str],
    today: dt.date,
    registry: dict[str, Secret] = REGISTRY,
) -> list[str]:
    """Everything wrong with the secrets, from plain facts (pure, tested)."""
    out = [
        f"untracked secret: {n} (add it to the registry)"
        for n in sorted(set(files) - set(registry))
    ]
    for name, sec in registry.items():
        if name not in files:
            out.append(f"missing: {name}")
            continue
        mode, uid = files[name]
        if mode != 0o600:
            out.append(f"{name}: mode {oct(mode)}, want 0o600")
        if uid != sec.owner_uid:
            out.append(f"{name}: owner uid {uid}, want {sec.owner_uid}")
        if sec.max_age_days is None:
            continue
        if name not in ledger:
            out.append(f"{name}: no rotation date recorded")
        elif (today - dt.date.fromisoformat(ledger[name])).days > sec.max_age_days:
            out.append(
                f"{name}: last rotated {ledger[name]}, older than {sec.max_age_days} d"
                f" ({sec.rotation})"
            )
    return out


def scan() -> dict[str, tuple[int, int]]:
    out = {}
    for p in SECRETS.iterdir():
        st = p.stat()
        out[p.name] = (stat.S_IMODE(st.st_mode), st.st_uid)
    return out


def load_ledger() -> dict[str, str]:
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {}


def record(*names: str, when: dt.date | None = None) -> None:
    """Note that these secrets were rotated (today)."""
    ledger = load_ledger()
    for n in names:
        if n not in REGISTRY:
            raise KeyError(f"{n} is not in the registry")
        ledger[n] = (when or dt.date.today()).isoformat()
    LEDGER.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(dict(sorted(ledger.items())), indent=2) + "\n")
    LEDGER.chmod(0o600)


def init_ledger() -> None:
    """Seed missing dates from each file's modification time (its creation, here)."""
    ledger = load_ledger()
    for n in REGISTRY:
        p = SECRETS / n
        if n not in ledger and p.exists():
            record(n, when=dt.date.fromtimestamp(p.stat().st_mtime))


# --- typing a console key in --------------------------------------------------------------
AWS_ID = re.compile(r"^AKIA[0-9A-Z]{16}$")
AWS_SECRET = re.compile(r"^[A-Za-z0-9/+]{40}$")
HETZNER = re.compile(r"^[A-Za-z0-9]{64}$")


def set_env_values(path, values: dict[str, str]) -> None:
    """Replace or add `KEY=value` lines, keeping every other line, IN PLACE (same inode,
    so a container's bind mount sees the change) and 600."""
    lines = path.read_text().splitlines() if path.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in values:
            lines[i] = f"{key}={values[key]}"
            seen.add(key)
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as f:
        f.truncate(0)
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)


def _ask(prompt: str, pattern: re.Pattern) -> str:
    value = getpass.getpass(f"{prompt} (hidden): ").strip()
    if not pattern.match(value):
        raise SystemExit(f"that does not look like a {prompt}; nothing written")
    return value


def secret_set(name: str) -> None:
    if name in {"backup-aws.env", "lakekeeper-aws.env", "aws.env", "models-publisher-aws.env",
                "models-reader-aws.env"}:  # fmt: skip
        values = {
            "AWS_ACCESS_KEY_ID": _ask("AWS access key id", AWS_ID),
            "AWS_SECRET_ACCESS_KEY": _ask("AWS secret access key", AWS_SECRET),
        }
        if name.startswith("models-"):
            values["AWS_REGION"] = "us-east-1"
    elif name == "hetzner-readonly.env":
        values = {"HETZNER_TOKEN": _ask("Hetzner API token", HETZNER)}
    else:
        raise SystemExit(f"secret-set handles console keys only, not {name}")
    set_env_values(SECRETS / name, values)
    record(name)
    print(f"{name} written (600), rotation date recorded. Nothing was printed.")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "set":
        secret_set(argv[2])
        return 0
    if cmd == "init-ledger":
        init_ledger()
        return 0
    found = problems(scan(), load_ledger(), dt.date.today())
    print(f"secrets: {len(REGISTRY)} registered, {len(found)} problem(s)")
    for p in found:
        print("  PROBLEM:", p)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
