"""Where the lakehouse's files live, and the credentials to reach them.

Local disk or GraphGuard's own S3 bucket. Since S5.6d part 2, jobs hold **no S3 key**:
Lakekeeper vends each one a short-lived key (AWS STS, 1 hour) scoped to the table it
loaded, read-only unless the job may write. PyIceberg puts that key in the table's
`io.properties`, so every helper here takes a table's properties, never the
catalog's.

The only long-lived key is Lakekeeper's own (`.secrets/lakekeeper-aws.env`, IAM user
`graphguard-lakekeeper`), and all it can do is assume the vending role. The S5.6b key
in `.secrets/aws.env` remains only for the SQL-catalog rollback and is meant to be
deleted. Keys never appear in code, logs or repr().

One set of credentials is turned into the three dialects the engines speak:
PyIceberg properties, Polars storage options, and a PyArrow filesystem.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from pyarrow import fs as pafs

from graphguard.config import REPO_ROOT

AWS_ENV_FILE = REPO_ROOT / ".secrets" / "aws.env"
VENDING_ENV_FILE = REPO_ROOT / ".secrets" / "lakekeeper-aws.env"
# Not secrets: the bucket name is in the docs. Overridable for tests.
LAKEHOUSE_BUCKET = os.environ.get("GRAPHGUARD_S3_BUCKET", "graphguard-lakehouse-0dcd18")
LAKEHOUSE_REGION = os.environ.get("GRAPHGUARD_S3_REGION", "us-east-1")


@dataclass(frozen=True)
class AwsEnv:
    access_key_id: str
    secret_access_key: str = field(repr=False)
    region: str
    bucket: str


def read_aws_env(path: Path = AWS_ENV_FILE) -> AwsEnv | None:
    """The bucket credentials, or None while they are not filled in yet."""
    if not path.exists():
        return None
    env = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    if not env.get("AWS_ACCESS_KEY_ID") or not env.get("AWS_SECRET_ACCESS_KEY"):
        return None
    return AwsEnv(
        access_key_id=env["AWS_ACCESS_KEY_ID"],
        secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        region=env.get("AWS_REGION", "us-east-1"),
        bucket=env["GRAPHGUARD_S3_BUCKET"],
    )


@dataclass(frozen=True)
class VendingEnv:
    """Lakekeeper's own key: it can only assume `role_arn`, the vending role."""

    access_key_id: str
    secret_access_key: str = field(repr=False)
    role_arn: str


def read_vending_env(path: Path = VENDING_ENV_FILE) -> VendingEnv | None:
    if not path.exists():
        return None
    env = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    if not env.get("AWS_ACCESS_KEY_ID") or not env.get("GRAPHGUARD_VENDING_ROLE_ARN"):
        return None
    return VendingEnv(
        access_key_id=env["AWS_ACCESS_KEY_ID"],
        secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        role_arn=env["GRAPHGUARD_VENDING_ROLE_ARN"],
    )


def s3_properties(env: AwsEnv) -> dict[str, str]:
    """PyIceberg catalog properties for the real bucket."""
    return {
        "s3.access-key-id": env.access_key_id,
        "s3.secret-access-key": env.secret_access_key,
        "s3.region": env.region,
    }


def polars_storage_options(props: dict[str, str]) -> dict[str, str] | None:
    """The same credentials in the form Polars' native Iceberg/Parquet reader wants."""
    if "s3.access-key-id" not in props:
        return None
    opts = {
        "aws_access_key_id": props["s3.access-key-id"],
        "aws_secret_access_key": props["s3.secret-access-key"],
        "aws_region": props.get("s3.region", "us-east-1"),
    }
    if token := props.get("s3.session-token"):  # a vended, short-lived key
        opts["aws_session_token"] = token
    if endpoint := props.get("s3.endpoint"):  # a test S3 server
        opts["aws_endpoint_url"] = endpoint
        opts["aws_allow_http"] = "true"
    return opts


def filesystem(uri: str, props: dict[str, str]) -> tuple[pafs.FileSystem, str]:
    """A PyArrow filesystem and the path inside it, for a file:// or s3:// URI."""
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        endpoint = props.get("s3.endpoint")
        s3 = pafs.S3FileSystem(
            access_key=props.get("s3.access-key-id"),
            secret_key=props.get("s3.secret-access-key"),
            session_token=props.get("s3.session-token"),
            region=props.get("s3.region", "us-east-1"),
            endpoint_override=urlparse(endpoint).netloc if endpoint else None,
            scheme=urlparse(endpoint).scheme if endpoint else "https",
        )
        return s3, f"{parsed.netloc}{parsed.path}"
    return pafs.LocalFileSystem(), parsed.path if parsed.scheme == "file" else uri


def to_uri(fs: pafs.FileSystem, path: str) -> str:
    """Inverse of `filesystem`: a path inside a filesystem back to a full URI."""
    return f"s3://{path}" if isinstance(fs, pafs.S3FileSystem) else f"file://{path}"
