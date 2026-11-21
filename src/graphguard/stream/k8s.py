"""The consumer pod's Secret (S6.6), for `kubectl apply -f -` on stdin.

    python -m graphguard.stream.k8s secret | k3s kubectl apply -f -

Three files, mounted at /var/run/graphguard (the pod's CREDENTIALS_DIRECTORY): the
consumer's Kafka login, the `stream` Redis user's password (as `redis.env`, the name the
store reads), and the `stream_app` Postgres password. Nothing else from `.secrets/`.
"""

from __future__ import annotations

import base64
import json
import sys

from graphguard.config import REPO_ROOT

SECRETS = REPO_ROOT / ".secrets"
NAME, NS = "graphguard-stream", "graphguard"
# key in the Secret (= file name in the pod) -> file in .secrets/
FILES = {"kafka-consumer.env": "kafka-consumer.env", "redis.env": "redis-stream.env",
         "stream-db.env": "stream-db.env"}  # fmt: skip


def secret_manifest(secrets_dir=SECRETS) -> str:
    data = {key: base64.b64encode((secrets_dir / src).read_bytes()).decode()
            for key, src in FILES.items()}  # fmt: skip
    return json.dumps({"apiVersion": "v1", "kind": "Secret", "type": "Opaque",
                       "metadata": {"name": NAME, "namespace": NS}, "data": data})  # fmt: skip


if __name__ == "__main__":
    if sys.argv[1:] == ["secret"]:
        print(secret_manifest())
    else:
        print(f"usage: {sys.argv[0]} secret")
        sys.exit(2)
