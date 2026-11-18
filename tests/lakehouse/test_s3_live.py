"""Least privilege on the REAL bucket, proven by expecting denials (S5.6b).

These talk to AWS, so they run only once `.secrets/aws.env` is filled in
(docs/runbooks/aws-setup.md). Until then they skip with that reason printed. Once
configured they always run: a misconfigured key FAILS, it does not skip.
"""

import uuid

import pytest

from graphguard.lakehouse.storage import read_aws_env

ENV = read_aws_env()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        ENV is None, reason="AWS not configured yet: fill .secrets/aws.env (runbooks/aws-setup.md)"
    ),
]


def _client(service):
    import boto3

    return boto3.client(
        service,
        region_name=ENV.region,
        aws_access_key_id=ENV.access_key_id,
        aws_secret_access_key=ENV.secret_access_key,
    )


def _denied(call):
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError) as e:
        call()
    assert e.value.response["Error"]["Code"] in {
        "AccessDenied",
        "AccessDeniedException",
        "AllAccessDisabled",
    }


def test_the_lakehouse_prefix_is_readable_writable_and_deletable():
    s3, key = _client("s3"), f"lakehouse/_probe/{uuid.uuid4().hex}"
    s3.put_object(Bucket=ENV.bucket, Key=key, Body=b"ok")
    assert s3.get_object(Bucket=ENV.bucket, Key=key)["Body"].read() == b"ok"
    s3.delete_object(Bucket=ENV.bucket, Key=key)


def test_writing_outside_the_prefix_is_denied():
    _denied(
        lambda: _client("s3").put_object(
            Bucket=ENV.bucket, Key=f"models/{uuid.uuid4().hex}", Body=b"x"
        )
    )


def test_listing_the_bucket_root_is_denied():
    _denied(lambda: _client("s3").list_objects_v2(Bucket=ENV.bucket))


def test_listing_every_bucket_in_the_account_is_denied():
    # The account also holds aws-job-streamer's buckets. This key must not even see them.
    _denied(lambda: _client("s3").list_buckets())


def test_iam_is_denied():
    _denied(lambda: _client("iam").list_users())
