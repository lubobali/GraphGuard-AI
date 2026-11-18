"""Set up the Lakekeeper REST catalog (S5.6c). Idempotent: safe to run again.

    just lakekeeper-init

1. Bootstrap the server (accept its terms; first run only).
2. Create the `graphguard` warehouse on our S3 bucket, prefix `lakehouse/`, with
   credential vending AND remote signing OFF: every client uses its own S3 key
   (the one in .secrets/aws.env, limited by IAM to `lakehouse/`). S5.6d turns on
   identities and permissions; until then Lakekeeper is reachable from 127.0.0.1 only.

The S3 key is sent to Lakekeeper once, which stores it encrypted in its own
database (LAKEKEEPER__PG_ENCRYPTION_KEY) to validate storage and write metadata.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from graphguard.lakehouse.storage import AwsEnv, read_aws_env

LAKEKEEPER_URL = os.environ.get("GRAPHGUARD_LAKEKEEPER_URL", "http://127.0.0.1:8181")
WAREHOUSE = "graphguard"
KEY_PREFIX = "lakehouse"


def _call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{LAKEKEEPER_URL}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})


def warehouse_request(env: AwsEnv) -> dict:
    """The warehouse definition. Pure, so the security-relevant flags are testable."""
    return {
        "warehouse-name": WAREHOUSE,
        "storage-profile": {
            "type": "s3",
            "bucket": env.bucket,
            "key-prefix": KEY_PREFIX,
            "region": env.region,
            "flavor": "aws",
            "sts-enabled": False,
            "remote-signing-enabled": False,
        },
        "storage-credential": {
            "type": "s3",
            "credential-type": "access-key",
            "aws-access-key-id": env.access_key_id,
            "aws-secret-access-key": env.secret_access_key,
        },
    }


def existing_warehouse_id() -> str | None:
    status, body = _call("GET", "/management/v1/warehouse")
    if status != 200:
        raise RuntimeError(f"listing warehouses failed: HTTP {status}")
    for w in body.get("warehouses", []):
        if w.get("name") == WAREHOUSE:
            return w.get("id") or w.get("warehouse-id")
    return None


def main() -> int:
    env = read_aws_env()
    if env is None:
        print("AWS not configured: fill .secrets/aws.env first (docs/runbooks/aws-setup.md)")
        return 1

    status, body = _call("POST", "/management/v1/bootstrap", {"accept-terms-of-use": True})
    if status in (200, 204):
        print("bootstrapped")
    elif "bootstrap" in json.dumps(body).lower() or status == 400:
        print("already bootstrapped")
    else:
        print(f"bootstrap failed: HTTP {status} {body}")
        return 1

    if wid := existing_warehouse_id():
        print(f"warehouse '{WAREHOUSE}' already exists ({wid})")
        return 0
    status, body = _call("POST", "/management/v1/warehouse", warehouse_request(env))
    if status not in (200, 201):
        # The body can echo the request; print only the error type and message.
        err = body.get("error", body)
        print(f"warehouse creation failed: HTTP {status} {err.get('type')}: {err.get('message')}")
        return 1
    print(
        f"warehouse '{WAREHOUSE}' created on s3://{env.bucket}/{KEY_PREFIX}/ "
        f"({body.get('warehouse-id')})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
