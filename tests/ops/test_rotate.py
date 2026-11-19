"""Secret rotation (S5b.6): the pure parts. The real rotations are proven live on the box."""

import base64
import hashlib
import hmac

import pytest

from graphguard.ops import rotate as rot
from graphguard.serving.redis_acl import acl_lines

pytestmark = pytest.mark.unit


def test_the_scram_verifier_proves_the_password_and_hides_it():
    salt = b"0123456789abcdef"
    v = rot.scram_verifier("s3cret", salt=salt)
    mech, rest = v.split("$", 1)
    iters_salt, keys = rest.split("$")
    iters, b64salt = iters_salt.split(":")
    stored, server = (base64.b64decode(k) for k in keys.split(":"))
    assert mech == "SCRAM-SHA-256" and iters == "4096" and base64.b64decode(b64salt) == salt
    salted = hashlib.pbkdf2_hmac("sha256", b"s3cret", salt, 4096)
    assert stored == hashlib.sha256(hmac.new(salted, b"Client Key", "sha256").digest()).digest()
    assert server == hmac.new(salted, b"Server Key", "sha256").digest()
    assert "s3cret" not in v


def test_two_verifiers_of_one_password_differ_by_salt():
    assert rot.scram_verifier("x") != rot.scram_verifier("x")


@pytest.mark.parametrize("role", ['x"; DROP ROLE y; --', "Robert'", "UPPER"])
def test_alter_role_refuses_anything_but_a_plain_role_name(role):
    with pytest.raises(ValueError):
        rot.alter_role_sql(role, rot.scram_verifier("x"))


def test_alter_role_sends_only_the_verifier():
    sql = rot.alter_role_sql("dex", rot.scram_verifier("plain-pw"))
    assert sql.startswith('ALTER ROLE "dex" PASSWORD \'SCRAM-SHA-256$') and "plain-pw" not in sql


def test_url_password_is_swapped_and_encoded():
    url = "postgres://openfga:old@graphguard-mlflow-db:5432/openfga?sslmode=disable"  # noqa: E501 betterleaks:allow -- fake fixture
    assert rot.with_url_password(url, "n/w+") == (
        "postgres://openfga:n%2Fw%2B@graphguard-mlflow-db:5432/openfga?sslmode=disable"  # noqa: E501 betterleaks:allow -- fake fixture
    )
    with pytest.raises(ValueError):
        rot.with_url_password("postgres://host/db", "x")


def test_pgpass_keeps_everything_but_the_password():
    assert rot.pgpass_with_password("mlflow-db:5432:mlflow:mlflow_app:old\n", "new") == (
        "mlflow-db:5432:mlflow:mlflow_app:new"
    )


def test_the_scorer_rev_annotation_is_bumped_exactly_once():
    text = f'      annotations:\n        {rot.REV_KEY}: "1"\n'
    assert f'{rot.REV_KEY}: "2"' in rot.bump_rev(text, "2")
    with pytest.raises(ValueError):
        rot.bump_rev("nothing here", "2")


def test_the_manifest_carries_the_rev_annotation():
    rot.bump_rev(rot.RAYSERVICE.read_text(), "probe")  # raises if missing


def test_during_a_redis_rotation_a_user_has_both_passwords_and_nothing_more():
    pw = {"scorer": ["old", "new"], "loader": "l", "tests": "t"}
    (scorer,) = [line for line in acl_lines(pw) if line.startswith("user scorer")]
    digests = [w for w in scorer.split() if w.startswith("#")]
    assert len(digests) == 2 and "old" not in scorer and "new" not in scorer
    assert "+@all" not in scorer and "-@all" in scorer


def test_pgpass_changes_only_its_own_line():
    text = "h:5432:mlflow:mlflow_app:a\nh:5432:mlflow_auth:mlflow_auth:b\n"
    assert rot.pgpass_set(text, "mlflow_auth", "mlflow_auth", "new") == (
        "h:5432:mlflow:mlflow_app:a\nh:5432:mlflow_auth:mlflow_auth:new\n"
    )
    with pytest.raises(ValueError):
        rot.pgpass_set(text, "nope", "nope", "x")
