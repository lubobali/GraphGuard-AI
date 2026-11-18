"""The warehouse definition must keep credential vending and remote signing off (S5.6c)."""

import pytest

from graphguard.lakehouse.lakekeeper import KEY_PREFIX, warehouse_request
from graphguard.lakehouse.storage import AwsEnv

pytestmark = pytest.mark.unit

ENV = AwsEnv(
    access_key_id="AKIAEXAMPLE", secret_access_key="sekrit", region="us-east-1", bucket="b"
)


def test_clients_bring_their_own_credentials_until_s5_6d():
    # Vending and signing are S5.6d's job, with identities and permissions. Until
    # then Lakekeeper must never hand out storage access to whoever asks.
    profile = warehouse_request(ENV)["storage-profile"]
    assert profile["sts-enabled"] is False
    assert profile["remote-signing-enabled"] is False


def test_the_warehouse_lives_under_the_lakehouse_prefix_only():
    profile = warehouse_request(ENV)["storage-profile"]
    assert profile["bucket"] == "b" and profile["key-prefix"] == KEY_PREFIX == "lakehouse"
