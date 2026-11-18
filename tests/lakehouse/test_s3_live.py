"""Least privilege on the REAL bucket, proven by expecting denials (S5.6b, S5.6d).

Since S5.6d part 2 the only long-lived key is Lakekeeper's (IAM user
`graphguard-lakekeeper`). By itself it can do one thing: assume the vending role.
The role reaches `lakehouse/` and nothing else. These tests prove both halves.

They talk to AWS, so they run only once `.secrets/lakekeeper-aws.env` exists
(docs/runbooks/aws-vending.md); until then they skip with that reason printed.
Once configured they always run: a misconfigured key FAILS, it does not skip.
"""

import uuid

import pytest

from graphguard.lakehouse.storage import LAKEHOUSE_BUCKET, LAKEHOUSE_REGION, read_vending_env

ENV = read_vending_env()
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        ENV is None,
        reason="Lakekeeper's AWS key not configured: .secrets/lakekeeper-aws.env (aws-vending.md)",
    ),
]


def _user(service):
    import boto3

    return boto3.client(
        service,
        region_name=LAKEHOUSE_REGION,
        aws_access_key_id=ENV.access_key_id,
        aws_secret_access_key=ENV.secret_access_key,
    )


@pytest.fixture(scope="module")
def role_s3():
    """S3 as the vending role, the way Lakekeeper reaches the bucket itself."""
    import boto3

    c = _user("sts").assume_role(
        RoleArn=ENV.role_arn, RoleSessionName="gg-test", DurationSeconds=900
    )["Credentials"]
    return boto3.client(
        "s3",
        region_name=LAKEHOUSE_REGION,
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"],
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


# --- the key by itself: nothing but "assume the role" -----------------------


def test_the_key_alone_cannot_read_the_lakehouse():
    _denied(
        lambda: _user("s3").list_objects_v2(Bucket=LAKEHOUSE_BUCKET, Prefix="lakehouse/", MaxKeys=1)
    )


def test_the_key_alone_cannot_see_other_buckets_or_iam():
    # The account also holds aws-job-streamer's buckets. This key must not even see them.
    _denied(lambda: _user("s3").list_buckets())
    _denied(lambda: _user("iam").list_users())


# --- the role: lakehouse/ only ----------------------------------------------


def test_the_role_reads_writes_and_deletes_under_the_lakehouse_prefix(role_s3):
    key = f"lakehouse/_probe/{uuid.uuid4().hex}"
    role_s3.put_object(Bucket=LAKEHOUSE_BUCKET, Key=key, Body=b"ok")
    assert role_s3.get_object(Bucket=LAKEHOUSE_BUCKET, Key=key)["Body"].read() == b"ok"
    role_s3.delete_object(Bucket=LAKEHOUSE_BUCKET, Key=key)


def test_the_role_cannot_write_outside_the_prefix(role_s3):
    _denied(
        lambda: role_s3.put_object(
            Bucket=LAKEHOUSE_BUCKET, Key=f"models/{uuid.uuid4().hex}", Body=b"x"
        )
    )


def test_the_role_cannot_list_the_bucket_root_or_other_buckets(role_s3):
    _denied(lambda: role_s3.list_objects_v2(Bucket=LAKEHOUSE_BUCKET))
    _denied(lambda: role_s3.list_buckets())
