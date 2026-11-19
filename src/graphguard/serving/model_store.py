"""The model on S3, immutable and verified (S5.7).

    s3://graphguard-lakehouse-0dcd18/models/xgboost/<version>/
        model.json  metadata.json  manifest.json

**Version = content.** `<version>` is `xgb-` + 12 hex of the hash of the model files'
hashes, so the same bytes always get the same version and a second publish is a no-op.
Files go up with `If-None-Match: *` (and an S3-checked SHA-256): AWS refuses to overwrite
an existing version, and the publisher's IAM policy refuses any write without that header.
The manifest goes up last, so a version without a manifest is an unfinished publish and
never loads.

**Pinned in git.** The scorer is given the version AND the manifest's SHA-256
(`k8s/rayservice.yaml`). `fetch_verified` checks the manifest against that hash and every
file against the manifest, and raises on any difference -- the replica never serves.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

BUCKET = "graphguard-lakehouse-0dcd18"
PREFIX = "models/xgboost"
FILES = ("model.json", "metadata.json")
MANIFEST = "manifest.json"


class ModelVerificationError(RuntimeError):
    """The bundle on S3 is not the one git pinned. The scorer must not start."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def version_of(file_hashes: dict[str, str]) -> str:
    """Content address of the model files (pure, tested)."""
    joined = "".join(f"{name}:{file_hashes[name]}\n" for name in sorted(file_hashes))
    return "xgb-" + sha256(joined.encode())[:12]


def manifest_bytes(manifest: dict) -> bytes:
    """Canonical JSON: the hash of a manifest never depends on key order."""
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()


def build_manifest(
    bundle_dir: Path, extra: dict | None = None
) -> tuple[str, dict, dict[str, bytes]]:
    blobs = {name: (bundle_dir / name).read_bytes() for name in FILES}
    files = {name: {"sha256": sha256(b), "size": len(b)} for name, b in blobs.items()}
    version = version_of({n: f["sha256"] for n, f in files.items()})
    manifest = {"version": version, "files": files, **(extra or {})}
    return version, manifest, blobs


def _key(version: str, name: str) -> str:
    return f"{PREFIX}/{version}/{name}"


def _exists(s3, key: str) -> bytes | None:
    from botocore.exceptions import ClientError

    try:
        return s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    except ClientError as e:
        # No ListBucket permission: a missing object answers 403, not 404.
        if e.response["Error"]["Code"] in {"NoSuchKey", "404", "AccessDenied", "403"}:
            return None
        raise


def _put_once(s3, key: str, body: bytes) -> None:
    """Upload only if the key does not exist; S3 checks the SHA-256 on arrival."""
    from botocore.exceptions import ClientError

    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    try:
        s3.put_object(Bucket=BUCKET, Key=key, Body=body, IfNoneMatch="*",
                      ChecksumAlgorithm="SHA256", ChecksumSHA256=digest)  # fmt: skip
    except ClientError as e:
        if e.response["Error"]["Code"] not in {"PreconditionFailed", "412"}:
            raise
        # Already there: fine only if it holds exactly these bytes.
        if _exists(s3, key) != body:
            raise ModelVerificationError(f"{key} exists with different bytes") from None


def publish(s3, bundle_dir: Path, extra: dict | None = None) -> tuple[str, str]:
    """Publish the bundle; returns (version, manifest sha256) -- the two lines to pin."""
    version, manifest, blobs = build_manifest(bundle_dir, extra)
    if (existing := _exists(s3, _key(version, MANIFEST))) is not None:
        return version, sha256(existing)  # same model already published: keep its record
    for name, body in blobs.items():
        _put_once(s3, _key(version, name), body)
    body = manifest_bytes(manifest)
    _put_once(s3, _key(version, MANIFEST), body)  # last: the version is now complete
    return version, sha256(body)


def fetch_verified(s3, version: str, manifest_sha256: str, dest: Path) -> dict:
    """Download a version into `dest` and prove it is the pinned one, or raise."""
    raw = _exists(s3, _key(version, MANIFEST))
    if raw is None:
        raise ModelVerificationError(f"model {version}: no manifest on S3 (unfinished publish?)")
    if sha256(raw) != manifest_sha256:
        raise ModelVerificationError(f"model {version}: manifest hash differs from the pinned one")
    manifest = json.loads(raw)
    if manifest.get("version") != version or set(manifest["files"]) != set(FILES):
        raise ModelVerificationError(f"model {version}: manifest does not describe this version")
    dest.mkdir(parents=True, exist_ok=True)
    for name, want in manifest["files"].items():
        body = _exists(s3, _key(version, name))
        if body is None:
            raise ModelVerificationError(f"model {version}: {name} missing")
        if len(body) != want["size"] or sha256(body) != want["sha256"]:
            raise ModelVerificationError(f"model {version}: {name} does not match its manifest")
        (dest / name).write_bytes(body)
    return manifest


def client(env: dict[str, str] | None = None):
    """An S3 client from AWS_* variables (the scorer's Kubernetes Secret, or a file)."""
    import boto3

    env = env if env is not None else dict(os.environ)
    return boto3.client(
        "s3",
        region_name=env.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
    )


def _env_file(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and line[0] != "#"
    )


def main(argv: list[str]) -> int:
    from graphguard.config import REPO_ROOT, secrets_dir

    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "publish":
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()  # fmt: skip
        meta = json.loads((REPO_ROOT / "models/production/metadata.json").read_text())
        extra = {"git_sha": sha, "trained_on": meta.get("trained_on"),
                 "published_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}  # fmt: skip
        s3 = client(_env_file(secrets_dir() / "models-publisher-aws.env"))
        version, msha = publish(s3, REPO_ROOT / "models/production", extra)
        print(f"published {version}")
        print("  pin in k8s/rayservice.yaml:")
        print(f"    GRAPHGUARD_MODEL_VERSION: {version}")
        print(f"    GRAPHGUARD_MODEL_SHA256: {msha}")
        return 0
    print(f"usage: {argv[0]} publish")
    return 2


if __name__ == "__main__":
    import sys

    sys.exit(main(sys.argv))
