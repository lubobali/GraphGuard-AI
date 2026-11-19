"""The backup key cannot destroy history, proven on the REAL bucket (S5b.3).

A stolen box key may add backups and hide them behind delete markers, but every
version stays for 30 days: deleting a version, shortening or bypassing the lock,
or changing the bucket's rules is denied. Runs once `.secrets/backup-aws.env`
exists (docs/runbooks/backups.md); a misconfigured key FAILS, it does not skip.

Each run leaves one ~20-byte object version under `tests/`, locked for 30 days
and removed by the lifecycle rule afterwards — that is the point.
"""

import datetime as dt
import uuid

import pytest

from graphguard.ops import backup as bk

ENV_FILE = bk.SECRETS / "backup-aws.env"
BUCKET = "graphguard-backups-0dcd18"
OTHER_BUCKET = "graphguard-lakehouse-0dcd18"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not ENV_FILE.exists(), reason="backup key not configured (backups.md)"),
]


@pytest.fixture(scope="module")
def s3():
    import boto3

    env = bk._read_env(ENV_FILE)
    return boto3.client(
        "s3",
        region_name=env.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
    )


@pytest.fixture(scope="module")
def version(s3):
    """A fresh object written with the key: (key, version id)."""
    key = f"tests/{uuid.uuid4().hex}"
    r = s3.put_object(Bucket=BUCKET, Key=key, Body=b"graphguard lock probe")
    return key, r["VersionId"]


def _denied(call):
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError) as e:
        call()
    assert e.value.response["Error"]["Code"] in {"AccessDenied", "AccessDeniedException"}


def test_the_key_can_write_and_new_objects_are_locked_30_days(s3):
    key = f"tests/{uuid.uuid4().hex}"
    s3.put_object(Bucket=BUCKET, Key=key, Body=b"graphguard lock probe")
    head = s3.head_object(Bucket=BUCKET, Key=key)
    assert head["ObjectLockMode"] == "GOVERNANCE"
    days = (head["ObjectLockRetainUntilDate"] - dt.datetime.now(dt.UTC)).days
    assert 29 <= days <= 30


def test_the_bucket_keeps_its_lock_versioning_and_cleanup(s3):
    lock = s3.get_object_lock_configuration(Bucket=BUCKET)["ObjectLockConfiguration"]
    assert lock["ObjectLockEnabled"] == "Enabled"
    assert lock["Rule"]["DefaultRetention"] == {"Mode": "GOVERNANCE", "Days": 30}
    assert s3.get_bucket_versioning(Bucket=BUCKET)["Status"] == "Enabled"
    (rule,) = s3.get_bucket_lifecycle_configuration(Bucket=BUCKET)["Rules"]
    assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] >= 31  # never before the lock ends
    assert "Expiration" not in rule or "Days" not in rule["Expiration"]  # live backups never expire
    assert "Transitions" not in rule


def test_old_versions_cannot_even_be_read(s3, version):
    # restic never needs a version id; a stolen key cannot browse history either.
    key, vid = version
    from botocore.exceptions import ClientError

    with pytest.raises(ClientError) as e:
        s3.head_object(Bucket=BUCKET, Key=key, VersionId=vid)
    assert e.value.response["Error"]["Code"] in {"403", "AccessDenied"}


def test_deleting_a_version_is_denied(s3, version):
    key, vid = version
    _denied(lambda: s3.delete_object(Bucket=BUCKET, Key=key, VersionId=vid))


def test_bypassing_the_lock_is_denied(s3, version):
    key, vid = version
    _denied(
        lambda: s3.delete_object(
            Bucket=BUCKET, Key=key, VersionId=vid, BypassGovernanceRetention=True
        )
    )


def test_shortening_the_lock_is_denied(s3, version):
    key, vid = version
    soon = dt.datetime.now(dt.UTC) + dt.timedelta(days=1)
    _denied(
        lambda: s3.put_object_retention(
            Bucket=BUCKET,
            Key=key,
            VersionId=vid,
            Retention={"Mode": "GOVERNANCE", "RetainUntilDate": soon},
            BypassGovernanceRetention=True,
        )
    )


def test_a_plain_delete_only_adds_a_marker(s3, version):
    key, _ = version
    # allowed (restic removes its lock files); on a versioned bucket it hides, never erases
    assert s3.delete_object(Bucket=BUCKET, Key=key)["DeleteMarker"] is True


@pytest.mark.parametrize(
    "change",
    [
        lambda s3: s3.put_bucket_lifecycle_configuration(
            Bucket=BUCKET,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "x",
                        "Status": "Enabled",
                        "Filter": {},
                        "NoncurrentVersionExpiration": {"NoncurrentDays": 1},
                    }
                ]
            },
        ),
        lambda s3: s3.put_object_lock_configuration(
            Bucket=BUCKET,
            ObjectLockConfiguration={
                "ObjectLockEnabled": "Enabled",
                "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 1}},
            },
        ),
        lambda s3: s3.delete_bucket_policy(Bucket=BUCKET),
    ],
    ids=["lifecycle", "lock-config", "bucket-policy"],
)
def test_changing_the_buckets_rules_is_denied(s3, change):
    _denied(lambda: change(s3))


def test_the_key_reaches_no_other_bucket(s3):
    _denied(lambda: s3.list_objects_v2(Bucket=OTHER_BUCKET, MaxKeys=1))
