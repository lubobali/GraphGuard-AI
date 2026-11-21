"""Kafka's logins, topics and permissions, as code (S6.4).

    python -m graphguard.stream.kafka_admin secrets      # passwords, once (never rotated here)
    python -m graphguard.stream.kafka_admin bootstrap    # the admin login (container-local)
    python -m graphguard.stream.kafka_admin setup        # logins, topics, ACLs -- idempotent
    python -m graphguard.stream.kafka_admin status

One login per program, each with only what it does (the Redis and lakehouse pattern):

    replayer   write `transactions`
    consumer   read `transactions` (group graphguard-consumer); write decisions, alerts, the DLQ
    shadow     read `transactions` (group graphguard-shadow); write `decisions.shadow`
    monitor    describe only (lag)
    labeler    write `labels` -- late verdicts, from the label simulator (S6.9)
    admin      setup; a super user, used by nothing else

Change access only here, then `just kafka-setup`: ACLs the broker holds that are not listed
here are removed. The broker denies anything without an ACL (allow.everyone.if.no.acl.found
= false).
"""

from __future__ import annotations

import base64
import os
import secrets
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from graphguard.config import REPO_ROOT
from graphguard.config import secrets_dir as _secrets_dir

SECRETS = REPO_ROOT / ".secrets"
HOST_BOOTSTRAP = "127.0.0.1:9092"
POD_BOOTSTRAP = "10.42.0.1:9094"
CONTAINER = "graphguard-kafka"
USERS = ("admin", "replayer", "consumer", "shadow", "monitor", "labeler")
PARTITIONS = 1  # one total order: receiver-side features need it (ADR 0005)
ITERATIONS = 8192

_TOPIC = {
    # Retention by ARRIVAL time: the replay carries 2022 event times, and with CreateTime
    # Kafka would delete those records the moment they land. Event time is in the body.
    "message.timestamp.type": "LogAppendTime",
    "retention.ms": str(7 * 24 * 3600 * 1000),
    "segment.bytes": str(64 * 1024 * 1024),
    "cleanup.policy": "delete",
}
TOPICS: dict[str, dict[str, str]] = {
    name: dict(_TOPIC)
    for name in (
        "transactions",
        "decisions",
        "alerts",
        "transactions.dlq",
        "decisions.shadow",
        "labels",
    )  # fmt: skip
}

PRODUCER = {"enable.idempotence": True, "acks": "all", "max.in.flight.requests.per.connection": 5,
            "linger.ms": 5, "compression.type": "lz4"}  # fmt: skip


@dataclass(frozen=True)
class Acl:
    principal: str
    resource_type: str  # TOPIC | GROUP | CLUSTER
    name: str
    operation: str


def _grant(user: str, rtype: str, name: str, *ops: str) -> list[Acl]:
    return [Acl(f"User:{user}", rtype, name, op) for op in ops]


ACLS: tuple[Acl, ...] = tuple(
    _grant("replayer", "TOPIC", "transactions", "WRITE", "DESCRIBE")
    + _grant("consumer", "TOPIC", "transactions", "READ", "DESCRIBE")
    + _grant("consumer", "GROUP", "graphguard-consumer", "READ", "DESCRIBE")
    + [
        a
        for t in ("decisions", "alerts", "transactions.dlq")
        for a in _grant("consumer", "TOPIC", t, "WRITE", "DESCRIBE")
    ]  # fmt: skip
    + _grant("shadow", "TOPIC", "transactions", "READ", "DESCRIBE")
    + _grant("shadow", "GROUP", "graphguard-shadow", "READ", "DESCRIBE")
    + _grant("shadow", "TOPIC", "decisions.shadow", "WRITE", "DESCRIBE")
    + _grant("consumer", "TOPIC", "labels", "READ", "DESCRIBE")  # S6.9: stores late labels
    + _grant("labeler", "TOPIC", "labels", "WRITE", "DESCRIBE")  # S6.9: the label simulator
    + _grant("monitor", "TOPIC", "*", "DESCRIBE")
    + _grant("monitor", "GROUP", "*", "DESCRIBE")
    + _grant("monitor", "CLUSTER", "kafka-cluster", "DESCRIBE")
)


# --- secrets ----------------------------------------------------------------------------
def password_var(user: str) -> str:
    if user not in USERS:
        raise ValueError(f"unknown Kafka user {user!r}; one of {USERS}")
    return f"GG_KAFKA_{user.upper()}_PASSWORD"


def _read_env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines()
                if "=" in line and not line.startswith("#"))  # fmt: skip


def generate_secrets(secrets_dir: Path = SECRETS) -> list[Path]:
    """Passwords for missing users (never overwrites), one file per user, and the cluster id."""
    env_file = secrets_dir / "kafka.env"
    if not env_file.exists():
        fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write("# Kafka logins (S6.4). Never commit.\n")
    env = _read_env(env_file)
    with env_file.open("a") as f:
        if "GG_KAFKA_CLUSTER_ID" not in env:
            cid = base64.urlsafe_b64encode(uuid.uuid4().bytes).rstrip(b"=").decode()
            f.write(f"GG_KAFKA_CLUSTER_ID={cid}\n")
        for user in USERS:
            if not env.get(password_var(user)):
                f.write(f"{password_var(user)}={secrets.token_urlsafe(32)}\n")
    env = _read_env(env_file)
    written = [env_file]
    for user in USERS:
        own = secrets_dir / f"kafka-{user}.env"
        fd = os.open(own, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(f"{password_var(user)}={env[password_var(user)]}\n")
        os.chmod(own, 0o600)
        written.append(own)
    return written


def password(user: str, secrets_dir: Path | None = None) -> str:
    path = (secrets_dir or _secrets_dir()) / f"kafka-{user}.env"
    value = _read_env(path).get(password_var(user))
    if not value:
        raise KeyError(f"{password_var(user)} missing from {path}: run `just kafka-secrets`")
    return value


def client_config(user: str, bootstrap: str = HOST_BOOTSTRAP,
                  secrets_dir: Path | None = None) -> dict:  # fmt: skip
    """confluent-kafka settings for one login."""
    return {
        "bootstrap.servers": bootstrap,
        "security.protocol": "SASL_PLAINTEXT",
        "sasl.mechanisms": "SCRAM-SHA-512",
        "sasl.username": user,
        "sasl.password": password(user, secrets_dir),
    }


# --- the broker -------------------------------------------------------------------------
def bootstrap_admin() -> None:
    """Create the admin login over the container-local listener. The password goes in a
    file on the container's tmpfs (via stdin), never on a command line."""
    pw = password("admin", SECRETS)
    script = (
        "umask 077; cat > /tmp/admin-scram.properties && "
        "KAFKA_HEAP_OPTS=-Xmx64m /opt/kafka/bin/kafka-configs.sh "
        "--bootstrap-server 127.0.0.1:19091 --alter --entity-type users --entity-name admin "
        "--add-config-file /tmp/admin-scram.properties; rc=$?; "
        "rm -f /tmp/admin-scram.properties; exit $rc"
    )
    subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "sh", "-c", script],
        # The file form takes no brackets (the --add-config form does).
        input=f"SCRAM-SHA-512=iterations={ITERATIONS},password={pw}\n",
        text=True, check=True, capture_output=True,
    )  # fmt: skip


def _admin():
    from confluent_kafka.admin import AdminClient

    return AdminClient(client_config("admin", secrets_dir=SECRETS))


def _wait(futures: dict, ignore: tuple[str, ...] = ()) -> None:
    for key, fut in futures.items():
        try:
            fut.result(timeout=30)
        except Exception as e:  # noqa: BLE001 -- kafka raises KafkaException with codes
            if not any(code in str(e) for code in ignore):
                raise RuntimeError(f"{key}: {e}") from e


def _binding(a: Acl):
    from confluent_kafka.admin import (
        AclBinding,
        AclOperation,
        AclPermissionType,
        ResourcePatternType,
        ResourceType,
    )

    rtype = "BROKER" if a.resource_type == "CLUSTER" else a.resource_type  # librdkafka's name
    return AclBinding(ResourceType[rtype], a.name, ResourcePatternType.LITERAL,
                      a.principal, "*", AclOperation[a.operation],
                      AclPermissionType.ALLOW)  # fmt: skip


def setup() -> dict[str, int]:
    from confluent_kafka.admin import (
        AclBindingFilter,
        AclOperation,
        AclPermissionType,
        NewTopic,
        ResourcePatternType,
        ResourceType,
        ScramCredentialInfo,
        ScramMechanism,
        UserScramCredentialUpsertion,
    )

    admin = _admin()
    info = ScramCredentialInfo(ScramMechanism.SCRAM_SHA_512, ITERATIONS)
    upserts = [UserScramCredentialUpsertion(u, info, password(u, SECRETS).encode())
               for u in USERS if u != "admin"]  # fmt: skip
    _wait(admin.alter_user_scram_credentials(upserts))

    existing = set(admin.list_topics(timeout=30).topics)
    new = [NewTopic(t, num_partitions=PARTITIONS, replication_factor=1, config=cfg)
           for t, cfg in TOPICS.items() if t not in existing]  # fmt: skip
    if new:
        _wait(admin.create_topics(new), ignore=("TOPIC_ALREADY_EXISTS",))

    # ACLs: exactly the list above -- add the missing, remove anything else.
    everything = AclBindingFilter(ResourceType.ANY, None, ResourcePatternType.ANY, None, None,
                                  AclOperation.ANY, AclPermissionType.ANY)  # fmt: skip
    held = admin.describe_acls(everything).result(timeout=30)
    want = {_binding(a) for a in ACLS}
    stale = [b for b in held if b not in want]
    missing = [b for b in want if b not in set(held)]
    if missing:
        _wait(admin.create_acls(missing))
    if stale:
        _wait(admin.delete_acls(stale))
    return {"users": len(upserts) + 1, "topics_created": len(new), "acls": len(want),
            "acls_added": len(missing), "acls_removed": len(stale)}  # fmt: skip


def rotate() -> None:
    """New passwords for every login: admin first (container-local listener), then the rest
    with setup; each proven by logging in. The old files are restored if anything fails."""
    from graphguard.ops import secrets_registry as reg

    files = ["kafka.env", *[f"kafka-{u}.env" for u in USERS]]
    saved = {f: (SECRETS / f).read_text() for f in files}
    try:
        reg.set_env_values(SECRETS / "kafka.env",
                           {password_var(u): secrets.token_urlsafe(32) for u in USERS})  # fmt: skip
        generate_secrets()  # rewrites the per-user files from kafka.env
        bootstrap_admin()
        setup()
        for u in USERS:
            _login_ok(u)
    except Exception:
        for f, text in saved.items():
            (SECRETS / f).write_text(text)
        bootstrap_admin()
        setup()
        raise
    reg.record(*files)


def _login_ok(user: str) -> None:
    from confluent_kafka.admin import AdminClient

    AdminClient(client_config(user, secrets_dir=SECRETS)).list_topics(timeout=15)


def status() -> dict:
    admin = _admin()
    md = admin.list_topics(timeout=15)
    return {"brokers": len(md.brokers),
            "topics": sorted(t for t in md.topics if not t.startswith("__"))}  # fmt: skip


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "secrets":
        for p in generate_secrets():
            print(f"wrote {p.relative_to(REPO_ROOT)}")
        return 0
    if cmd == "cluster-id":
        print(_read_env(SECRETS / "kafka.env")["GG_KAFKA_CLUSTER_ID"])
        return 0
    if cmd == "bootstrap":
        bootstrap_admin()
        print("admin login created")
        return 0
    if cmd == "setup":
        print(setup())
        return 0
    if cmd == "rotate":
        rotate()
        print("Kafka logins rotated (each proven by logging in)")
        return 0
    if cmd == "status":
        print(status())
        return 0
    print(f"usage: {argv[0]} secrets|cluster-id|bootstrap|setup|status")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
