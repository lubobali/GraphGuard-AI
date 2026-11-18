"""Governance on the real catalog (S5.6d): logins and permissions, negative cases first.

Needs Dex (127.0.0.1:5556), Lakekeeper (127.0.0.1:8181) and the S3 key. CI has none
of them and skips by the explicit GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1 flag; anywhere
else an unreachable service FAILS. Writes happen only in throwaway tables.
"""

import base64
import json
import os
import time
import urllib.error
import urllib.request
import uuid

import pyarrow as pa
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1",
        reason="GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1 (no Dex/Lakekeeper in this environment)",
    ),
]

LK = "http://127.0.0.1:8181"
SEALED_TX = "sealed.transactions"


def _status(path: str, token: str | None) -> int:
    req = urllib.request.Request(f"{LK}{path}")
    if token is not None:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def _token(name: str) -> str:
    from graphguard.lakehouse.identity import fetch_token, read_identity

    return fetch_token(read_identity(name))


def _cat(name: str):
    from graphguard.lakehouse.catalog import open_rest_catalog

    return open_rest_catalog(name)


# --- who you are -------------------------------------------------------------

CONFIG = "/catalog/v1/config?warehouse=graphguard"


def test_no_token_is_refused():
    assert _status(CONFIG, None) == 401
    assert _status("/management/v1/warehouse", None) == 401


def test_garbage_token_is_refused():
    assert _status(CONFIG, "not-a-jwt") == 401


def test_a_token_signed_by_someone_else_is_refused():
    # Right issuer, right audience, valid shape -- but not signed by our Dex.
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    from graphguard.lakehouse.identity import ISSUER

    def b64(d: bytes) -> str:
        return base64.urlsafe_b64encode(d).rstrip(b"=").decode()

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    header = b64(json.dumps({"alg": "RS256", "typ": "JWT", "kid": "forged"}).encode())
    claims = {"iss": ISSUER, "aud": "gg-admin", "sub": "forged", "iat": now, "exp": now + 600}
    body = b64(json.dumps(claims).encode())
    sig = key.sign(f"{header}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    assert _status("/management/v1/warehouse", f"{header}.{body}.{b64(sig)}") == 401


def test_a_real_token_is_accepted():
    assert _status(CONFIG, _token("reader")) == 200


# --- what you may do ---------------------------------------------------------


@pytest.mark.parametrize("who", ["trainer", "reader"])
def test_trainer_and_reader_cannot_see_that_sealed_exists(who):
    from pyiceberg.exceptions import NoSuchTableError

    cat = _cat(who)
    assert "sealed" not in {ns[0] for ns in cat.list_namespaces()}
    # Not even "forbidden": the catalog does not confirm the table exists.
    with pytest.raises(NoSuchTableError):
        cat.load_table(SEALED_TX)


def test_builder_does_see_sealed_because_it_writes_it():
    assert _cat("builder").load_table(SEALED_TX).current_snapshot() is not None


@pytest.mark.parametrize("who", ["trainer", "reader"])
def test_trainer_and_reader_cannot_write(who):
    from pyiceberg.exceptions import ForbiddenError

    t = _cat(who).load_table("gold.labels")
    with pytest.raises(ForbiddenError):
        t.append(t.scan(limit=1).to_arrow())


@pytest.mark.parametrize("who", ["trainer", "reader"])
def test_trainer_and_reader_cannot_create_tables_or_namespaces(who):
    from pyiceberg.exceptions import ForbiddenError

    cat = _cat(who)
    with pytest.raises(ForbiddenError):
        cat.create_table(f"gold.t_{uuid.uuid4().hex[:8]}", schema=pa.schema([("k", pa.int64())]))
    with pytest.raises(ForbiddenError):
        cat.create_namespace(f"ns_{uuid.uuid4().hex[:8]}")


@pytest.mark.parametrize("who", ["trainer", "reader"])
def test_trainer_and_reader_read_silver_and_gold(who):
    cat = _cat(who)
    assert cat.load_table("gold.labels").scan(limit=5).to_arrow().num_rows == 5
    assert cat.load_table("silver.transactions").current_snapshot() is not None


def test_training_lineage_works_as_trainer_and_holds_no_secret():
    from graphguard.lakehouse.identity import read_identity
    from graphguard.lakehouse.lineage import training_lineage

    lineage = training_lineage(_cat("trainer"))
    assert all(
        k in lineage for k in ("snapshot.bronze.transactions_raw", "snapshot.silver.transactions")
    )
    secret = read_identity("trainer").secret
    assert secret not in json.dumps(lineage, default=str)


def test_builder_can_create_write_and_drop_in_its_layers():
    cat = _cat("builder")
    name = f"gold.scratch_{uuid.uuid4().hex[:8]}"
    t = cat.create_table(name, schema=pa.schema([("k", pa.int64())]))
    try:
        t.append(pa.table({"k": [1, 2]}))
        assert cat.load_table(name).scan().to_arrow().num_rows == 2
    finally:
        cat.purge_table(name)


def test_admin_operator_can_read_the_grants_and_trainer_cannot():
    from graphguard.lakehouse.lakekeeper import existing_warehouse_id

    wid = existing_warehouse_id(_token("admin"))
    assert _status(f"/management/v1/warehouse/{wid}/grants", _token("admin")) == 200
    assert _status(f"/management/v1/warehouse/{wid}/grants", _token("trainer")) in (403, 404)
