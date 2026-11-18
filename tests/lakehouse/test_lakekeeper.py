"""The warehouse's storage settings (S5.6c, S5.6d part 2): checked without a server."""

import pytest

from graphguard.lakehouse.lakekeeper import (
    KEY_PREFIX,
    VENDED_KEY_SECONDS,
    storage_profile,
    warehouse_request,
)
from graphguard.lakehouse.storage import VendingEnv

pytestmark = pytest.mark.unit

ROLE = "arn:aws:iam::000000000000:role/graphguard-lakekeeper-vending"
ENV = VendingEnv(access_key_id="AKIAEXAMPLE", secret_access_key="sekrit", role_arn=ROLE)


def test_jobs_get_vended_short_lived_keys():
    profile = storage_profile(ENV)
    assert profile["sts-enabled"] is True
    assert profile["sts-role-arn"] == profile["assume-role-arn"] == ROLE
    assert VENDED_KEY_SECONDS == profile["sts-token-validity-seconds"] <= 3600


def test_remote_signing_stays_off():
    # DuckDB cannot use it, and vended keys already scope each table.
    assert storage_profile(ENV)["remote-signing-enabled"] is False


def test_the_warehouse_lives_under_the_lakehouse_prefix_only():
    profile = storage_profile(ENV, bucket="b")
    assert profile["bucket"] == "b" and profile["key-prefix"] == KEY_PREFIX == "lakehouse"


def test_lakekeeper_holds_its_own_key_and_the_secret_is_not_in_reprs():
    cred = warehouse_request(ENV)["storage-credential"]
    assert cred["aws-access-key-id"] == "AKIAEXAMPLE"
    assert "sekrit" not in repr(ENV)
