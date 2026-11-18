"""Lakehouse test fixtures: every catalog test runs on local disk AND on S3.

S3 is an external service, so in unit tests it is faked (moto's in-process S3
server) -- the project rule is "mock only external things". The real bucket is
exercised by the live tests in test_s3_live.py, which need .secrets/aws.env.
"""

import socket

import boto3
import pytest
from moto.server import ThreadedMotoServer

from graphguard.lakehouse.catalog import open_catalog

FAKE_BUCKET = "graphguard-test-bucket"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def fake_s3():
    port = _free_port()
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port, verbose=False)
    server.start()
    endpoint = f"http://127.0.0.1:{port}"
    boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    ).create_bucket(Bucket=FAKE_BUCKET)
    yield {
        "s3.endpoint": endpoint,
        "s3.access-key-id": "test",
        "s3.secret-access-key": "test",
        "s3.region": "us-east-1",
    }
    server.stop()


@pytest.fixture(params=["local", "s3"])
def cat(request, tmp_path):
    uri = f"sqlite:///{tmp_path}/catalog.db"
    if request.param == "local":
        return open_catalog(uri=uri, warehouse=f"file://{tmp_path}/wh")
    s3 = request.getfixturevalue("fake_s3")
    return open_catalog(uri=uri, warehouse=f"s3://{FAKE_BUCKET}/{tmp_path.name}/lakehouse", s3=s3)
