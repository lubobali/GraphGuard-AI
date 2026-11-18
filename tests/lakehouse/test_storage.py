"""Where the lakehouse's credentials come from, and that they never leak."""

import pytest

from graphguard.lakehouse.storage import read_aws_env, s3_properties

pytestmark = pytest.mark.unit


def test_empty_keys_mean_s3_is_not_configured(tmp_path):
    f = tmp_path / "aws.env"
    f.write_text(
        "AWS_ACCESS_KEY_ID=\nAWS_SECRET_ACCESS_KEY=\nAWS_REGION=us-east-1\nGRAPHGUARD_S3_BUCKET=b\n"
    )
    assert read_aws_env(f) is None


def test_filled_keys_become_iceberg_properties(tmp_path):
    f = tmp_path / "aws.env"
    f.write_text(
        "AWS_ACCESS_KEY_ID=AKIAEXAMPLE\nAWS_SECRET_ACCESS_KEY=sekrit\nAWS_REGION=us-east-1\nGRAPHGUARD_S3_BUCKET=b\n"
    )
    env = read_aws_env(f)
    props = s3_properties(env)
    assert props["s3.access-key-id"] == "AKIAEXAMPLE"
    assert props["s3.region"] == "us-east-1"
    assert env.bucket == "b"


def test_the_secret_never_appears_in_repr(tmp_path):
    f = tmp_path / "aws.env"
    f.write_text(
        "AWS_ACCESS_KEY_ID=AKIAEXAMPLE\nAWS_SECRET_ACCESS_KEY=sekrit\nAWS_REGION=us-east-1\nGRAPHGUARD_S3_BUCKET=b\n"
    )
    assert "sekrit" not in repr(read_aws_env(f))
