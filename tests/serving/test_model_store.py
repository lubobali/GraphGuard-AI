"""The model on S3 is immutable and verified before it serves (S5.7). Fake S3 (moto)."""

import json

import boto3
import pytest
from moto import mock_aws

from graphguard.serving import model_store as ms

pytestmark = pytest.mark.unit


@pytest.fixture
def s3():
    with mock_aws():
        c = boto3.client("s3", region_name="us-east-1")
        c.create_bucket(Bucket=ms.BUCKET)
        yield c


@pytest.fixture
def bundle(tmp_path):
    d = tmp_path / "bundle"
    d.mkdir()
    (d / "model.json").write_text('{"trees": [1, 2, 3]}')
    (d / "metadata.json").write_text('{"trained_on": "fixture"}')
    return d


def test_the_version_is_the_content():
    a = ms.version_of({"model.json": "aa", "metadata.json": "bb"})
    assert a == ms.version_of({"metadata.json": "bb", "model.json": "aa"})  # order-free
    assert a != ms.version_of({"model.json": "ab", "metadata.json": "bb"})
    assert a.startswith("xgb-") and len(a) == 16


def test_publish_then_fetch_round_trips_byte_for_byte(s3, bundle, tmp_path):
    version, msha = ms.publish(s3, bundle, {"git_sha": "abc"})
    out = tmp_path / "out"
    manifest = ms.fetch_verified(s3, version, msha, out)
    assert manifest["git_sha"] == "abc"
    for name in ms.FILES:
        assert (out / name).read_bytes() == (bundle / name).read_bytes()


def test_publishing_the_same_bytes_again_is_a_no_op(s3, bundle):
    first = ms.publish(s3, bundle, {"git_sha": "abc"})
    assert ms.publish(s3, bundle, {"git_sha": "later"}) == first  # the first record stands


def test_an_existing_version_is_never_overwritten(s3, bundle):
    version, _ = ms.publish(s3, bundle)
    key = f"{ms.PREFIX}/{version}/model.json"
    with pytest.raises(ms.ModelVerificationError, match="different bytes"):
        ms._put_once(s3, key, b"tampered")
    assert (
        s3.get_object(Bucket=ms.BUCKET, Key=key)["Body"].read()
        == (bundle / "model.json").read_bytes()
    )


def test_a_wrong_pinned_hash_refuses(s3, bundle, tmp_path):
    version, _ = ms.publish(s3, bundle)
    with pytest.raises(ms.ModelVerificationError, match="pinned"):
        ms.fetch_verified(s3, version, "0" * 64, tmp_path / "x")


def test_a_tampered_file_refuses(s3, bundle, tmp_path):
    version, msha = ms.publish(s3, bundle)
    # an attacker with bucket access swaps the model (bypassing our conditional writes)
    s3.put_object(Bucket=ms.BUCKET, Key=f"{ms.PREFIX}/{version}/model.json", Body=b"{}")
    with pytest.raises(ms.ModelVerificationError, match="model.json does not match"):
        ms.fetch_verified(s3, version, msha, tmp_path / "x")


def test_a_missing_file_or_manifest_refuses(s3, bundle, tmp_path):
    version, msha = ms.publish(s3, bundle)
    s3.delete_object(Bucket=ms.BUCKET, Key=f"{ms.PREFIX}/{version}/metadata.json")
    with pytest.raises(ms.ModelVerificationError, match="metadata.json missing"):
        ms.fetch_verified(s3, version, msha, tmp_path / "x")
    with pytest.raises(ms.ModelVerificationError, match="no manifest"):
        ms.fetch_verified(s3, "xgb-000000000000", msha, tmp_path / "y")


def test_a_manifest_for_another_version_refuses(s3, bundle, tmp_path):
    version, _ = ms.publish(s3, bundle)
    raw = s3.get_object(Bucket=ms.BUCKET, Key=f"{ms.PREFIX}/{version}/manifest.json")["Body"].read()
    body = ms.manifest_bytes(json.loads(raw))  # still says the ORIGINAL version

    s3.put_object(Bucket=ms.BUCKET, Key=f"{ms.PREFIX}/xgb-ffffffffffff/manifest.json", Body=body)
    with pytest.raises(ms.ModelVerificationError, match="does not describe"):
        ms.fetch_verified(s3, "xgb-ffffffffffff", ms.sha256(body), tmp_path / "x")
