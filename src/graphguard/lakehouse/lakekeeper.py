"""Set up the Lakekeeper REST catalog. Idempotent: safe to run again.

    just lakekeeper-init     # bootstrap, warehouse, namespaces, tables, grants
    just lakekeeper-export   # save every table's metadata location (rollback point)

S5.6c ran Lakekeeper with no login. Since S5.6d every call carries a Dex token:
`init` runs as the `admin` identity, which bootstraps the server as its operator,
creates the `graphguard` warehouse on our S3 bucket (prefix `lakehouse/`),
creates the namespaces, **registers** any table missing from the catalog from
the export file (no data is copied: Iceberg tables are files on S3, and a
catalog only points at their current metadata), and applies the access policy
in `governance.py`.

**Credential vending (S5.6d part 2).** The warehouse holds Lakekeeper's own key
(`.secrets/lakekeeper-aws.env`, IAM user `graphguard-lakekeeper`), whose only
permission is to assume the role `graphguard-lakekeeper-vending`. Lakekeeper assumes
it for its own reads and writes, and again -- with a session policy narrowed to one
table -- for every key it vends. Remote signing stays off: DuckDB cannot use it.
The key is stored encrypted in Lakekeeper's database (LAKEKEEPER__PG_ENCRYPTION_KEY).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from graphguard.config import REPO_ROOT
from graphguard.lakehouse import governance
from graphguard.lakehouse.identity import IDENTITIES, fetch_token, read_identity
from graphguard.lakehouse.storage import (
    LAKEHOUSE_BUCKET,
    LAKEHOUSE_REGION,
    VendingEnv,
    read_vending_env,
)

LAKEKEEPER_URL = os.environ.get("GRAPHGUARD_LAKEKEEPER_URL", "http://127.0.0.1:8181")
WAREHOUSE = "graphguard"
KEY_PREFIX = "lakehouse"
EXPORT_FILE = REPO_ROOT / "lakehouse" / "catalog-export.json"


class LakekeeperError(RuntimeError):
    pass


def call(
    method: str, path: str, body: dict | None = None, token: str | None = None
) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{LAKEKEEPER_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, (json.loads(raw) if raw else {})
        except json.JSONDecodeError:
            return e.code, {"error": {"message": raw[:200].decode(errors="replace")}}


def _err(body: dict) -> str:
    """Error type and message only: a body can echo the request (and its key)."""
    e = body.get("error", body)
    return f"{e.get('type')}: {e.get('message')}" if isinstance(e, dict) else str(e)[:200]


VENDED_KEY_SECONDS = 3600


def storage_profile(
    vending: VendingEnv, bucket: str = LAKEHOUSE_BUCKET, region: str = LAKEHOUSE_REGION
) -> dict:
    """Pure, so the security-relevant flags are testable."""
    return {
        "type": "s3",
        "bucket": bucket,
        "key-prefix": KEY_PREFIX,
        "region": region,
        "flavor": "aws",
        "sts-enabled": True,
        "assume-role-arn": vending.role_arn,
        "sts-role-arn": vending.role_arn,
        "sts-token-validity-seconds": VENDED_KEY_SECONDS,
        "remote-signing-enabled": False,
    }


def storage_credential(vending: VendingEnv) -> dict:
    return {
        "type": "s3",
        "credential-type": "access-key",
        "aws-access-key-id": vending.access_key_id,
        "aws-secret-access-key": vending.secret_access_key,
    }


def warehouse_request(vending: VendingEnv) -> dict:
    return {
        "warehouse-name": WAREHOUSE,
        "storage-profile": storage_profile(vending),
        "storage-credential": storage_credential(vending),
    }


def existing_warehouse_id(token: str | None = None) -> str | None:
    status, body = call("GET", "/management/v1/warehouse", token=token)
    if status != 200:
        raise LakekeeperError(f"listing warehouses failed: HTTP {status} {_err(body)}")
    for w in body.get("warehouses", []):
        if w.get("name") == WAREHOUSE:
            return w.get("id") or w.get("warehouse-id")
    return None


def whoami(token: str) -> dict:
    """The catalog user behind `token`. A machine user exists only after its first
    catalog call, so this makes one (GET /config) before asking."""
    call("GET", f"/catalog/v1/config?warehouse={WAREHOUSE}", token=token)
    status, body = call("GET", "/management/v1/whoami", token=token)
    if status != 200:
        raise LakekeeperError(f"whoami failed: HTTP {status} {_err(body)}")
    return body


def _bootstrap(token: str) -> str:
    status, body = call(
        "POST",
        "/management/v1/bootstrap",
        {"accept-terms-of-use": True, "is-operator": True},
        token=token,
    )
    if status in (200, 204):
        return "bootstrapped (admin is the operator)"
    if status == 400 or "bootstrap" in _err(body).lower():
        return "already bootstrapped"
    raise LakekeeperError(f"bootstrap failed: HTTP {status} {_err(body)}")


def _ensure_warehouse(token: str, vending: VendingEnv) -> str:
    """Create the warehouse, or bring an existing one's storage to the vending setup
    (idempotent: the same profile and credential every time)."""
    if wid := existing_warehouse_id(token):
        body = {
            "storage-profile": storage_profile(vending),
            "storage-credential": storage_credential(vending),
        }
        status, resp = call("POST", f"/management/v1/warehouse/{wid}/storage", body, token=token)
        if status not in (200, 204):
            raise LakekeeperError(f"storage update failed: HTTP {status} {_err(resp)}")
        return wid
    status, body = call("POST", "/management/v1/warehouse", warehouse_request(vending), token=token)
    if status not in (200, 201):
        raise LakekeeperError(f"warehouse creation failed: HTTP {status} {_err(body)}")
    return body["warehouse-id"]


def _admin_catalog():
    from graphguard.lakehouse.catalog import open_catalog

    return open_catalog("admin")


def export(path: Path = EXPORT_FILE) -> dict:
    """Every table's current metadata location and snapshot id, written to `path`."""
    from graphguard.lakehouse.catalog import open_rest_catalog

    who = os.environ.get("GRAPHGUARD_EXPORT_AS", "admin")
    catalog = open_rest_catalog(None if who == "none" else who)
    out = {}
    for ns in catalog.list_namespaces():
        for ident in catalog.list_tables(ns):
            t = catalog.load_table(ident)
            snap = t.current_snapshot()
            out[".".join(ident)] = {
                "metadata_location": t.metadata_location,
                "snapshot_id": snap.snapshot_id if snap else None,
            }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


def register_missing(catalog, exported: dict) -> list[str]:
    """Register every exported table the catalog does not have. No data moves."""
    registered = []
    for name, entry in sorted(exported.items()):
        if catalog.table_exists(name):
            continue
        catalog.register_table(name, entry["metadata_location"])
        registered.append(name)
    return registered


def namespace_ids(catalog) -> dict[str, str]:
    return {
        ns[0]: catalog.load_namespace_properties(ns)["namespace_id"]
        for ns in catalog.list_namespaces()
    }


def init() -> int:
    vending = read_vending_env()
    if vending is None:
        print(
            "Lakekeeper's key missing: fill .secrets/lakekeeper-aws.env (runbooks/aws-vending.md)"
        )
        return 1
    admin_token = fetch_token(read_identity("admin"))
    print(_bootstrap(admin_token))
    wid = _ensure_warehouse(admin_token, vending)
    print(
        f"warehouse '{WAREHOUSE}' on s3://{LAKEHOUSE_BUCKET}/{KEY_PREFIX}/ ({wid}), "
        f"vending {VENDED_KEY_SECONDS // 60}-minute keys"
    )

    catalog = _admin_catalog()  # creates the namespaces as admin
    if EXPORT_FILE.exists():
        done = register_missing(catalog, json.loads(EXPORT_FILE.read_text()))
        print(f"registered {len(done)} table(s) from {EXPORT_FILE.name}: {done or 'none missing'}")

    # Each identity's first authenticated call provisions its catalog user.
    user_ids = {}
    for name in IDENTITIES:
        user_ids[name] = whoami(fetch_token(read_identity(name)))["id"]
    calls = governance.grant_requests(
        governance.grant_plan(), user_ids, wid, namespace_ids(catalog)
    )
    for path, body in calls:
        status, resp = call("POST", path, body, token=admin_token)
        if status not in (200, 204):
            raise LakekeeperError(f"grant failed on {path}: HTTP {status} {_err(resp)}")
    print(f"policy applied: {len(governance.grant_plan())} grants on {len(calls)} targets")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["export"]:
        out = export()
        print(f"exported {len(out)} tables to {EXPORT_FILE}")
        return 0
    if argv[:1] == ["secrets"]:
        from graphguard.lakehouse.identity import generate_secrets

        made = generate_secrets()
        print("created: " + (", ".join(p.name for p in made) or "nothing (all exist)"))
        return 0
    try:
        return init()
    except LakekeeperError as e:
        print(e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
