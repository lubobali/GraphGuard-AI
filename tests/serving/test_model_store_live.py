"""The two model keys are least-privilege, proven on the REAL bucket (S5.7).

Runs once both keys exist in .secrets/ (docs/runbooks/models.md); skips elsewhere (CI).
A denial is only proof when the object exists, so the lakehouse check uses a real table
metadata file (S3 answers AccessDenied for a missing key too when listing is denied).
"""

import pytest

from graphguard.config import REPO_ROOT
from graphguard.serving import model_store as ms

SECRETS = REPO_ROOT / ".secrets"
READER, PUBLISHER = SECRETS / "models-reader-aws.env", SECRETS / "models-publisher-aws.env"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (READER.exists() and PUBLISHER.exists()), reason="model keys not set"),
]
VERSION = "xgb-ab9ee07e6bd8"  # the first published production model


def _client(path):
    return ms.client(ms._env_file(path))


def _code(call):
    from botocore.exceptions import ClientError

    try:
        call()
    except ClientError as e:
        return e.response["Error"]["Code"]
    return "OK"


@pytest.fixture(scope="module")
def lakehouse_key():
    from graphguard.lakehouse.catalog import open_catalog

    loc = open_catalog("reader").load_table("silver.transactions").metadata_location
    assert loc.startswith(f"s3://{ms.BUCKET}/lakehouse/")
    return loc.split(f"s3://{ms.BUCKET}/", 1)[1]


def _model_key(name="model.json"):
    return f"{ms.PREFIX}/{VERSION}/{name}"


def test_the_reader_reads_models_and_nothing_else(lakehouse_key):
    s3 = _client(READER)
    assert _code(lambda: s3.get_object(Bucket=ms.BUCKET, Key=_model_key())) == "OK"
    assert _code(lambda: s3.get_object(Bucket=ms.BUCKET, Key=lakehouse_key)) == "AccessDenied"
    assert _code(lambda: s3.list_objects_v2(Bucket=ms.BUCKET, Prefix="models/")) == "AccessDenied"
    put = lambda: s3.put_object(Bucket=ms.BUCKET, Key="models/_probe/r", Body=b"x", IfNoneMatch="*")  # noqa: E731
    assert _code(put) == "AccessDenied"


def test_the_publisher_cannot_overwrite_delete_or_reach_the_lakehouse(lakehouse_key):
    s3 = _client(PUBLISHER)
    key = _model_key()
    no_header = lambda: s3.put_object(Bucket=ms.BUCKET, Key=key, Body=b"x")  # noqa: E731
    assert _code(no_header) == "AccessDenied"  # the policy demands If-None-Match
    with_header = lambda: s3.put_object(Bucket=ms.BUCKET, Key=key, Body=b"x", IfNoneMatch="*")  # noqa: E731
    assert _code(with_header) == "PreconditionFailed"  # and S3 refuses an existing key
    assert _code(lambda: s3.delete_object(Bucket=ms.BUCKET, Key=key)) == "AccessDenied"
    assert _code(lambda: s3.get_object(Bucket=ms.BUCKET, Key=lakehouse_key)) == "AccessDenied"


def test_the_published_model_is_the_one_in_models_production(tmp_path):
    import hashlib

    manifest = ms.fetch_verified(
        _client(READER), VERSION,
        hashlib.sha256(_client(READER).get_object(
            Bucket=ms.BUCKET, Key=_model_key("manifest.json"))["Body"].read()).hexdigest(),
        tmp_path,
    )  # fmt: skip
    for name in ms.FILES:
        assert (tmp_path / name).read_bytes() == (
            REPO_ROOT / "models/production" / name
        ).read_bytes()
    assert manifest["version"] == VERSION
