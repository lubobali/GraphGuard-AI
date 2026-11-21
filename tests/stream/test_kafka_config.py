"""Kafka (S6.4): the broker config, the topics and who may do what -- checked without a broker.

The live proof (a real broker refusing what each login may not do) is
test_kafka_live.py.
"""

import pytest
import yaml

from graphguard.config import REPO_ROOT
from graphguard.stream import kafka_admin as ka

pytestmark = pytest.mark.unit

PROPS = dict(
    line.split("=", 1)
    for line in (REPO_ROOT / "docker/kafka/server.properties").read_text().splitlines()
    if line and not line.startswith("#")
)
KAFKA = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())["services"]["kafka"]


# --- the broker --------------------------------------------------------------------------
def test_listeners_are_explicit_and_only_container_loopback_is_anonymous():
    listeners = dict(x.split("://") for x in PROPS["listeners"].split(","))
    protocols = dict(x.split(":") for x in PROPS["listener.security.protocol.map"].split(","))
    for name, addr in listeners.items():
        if protocols[name] == "PLAINTEXT":
            assert addr.startswith("127.0.0.1:"), f"{name} is anonymous and not loopback-only"
        else:
            assert protocols[name] == "SASL_PLAINTEXT"
    assert PROPS["sasl.enabled.mechanisms"] == "SCRAM-SHA-512"


def test_published_ports_reach_only_the_sasl_listeners():
    published = {p.rsplit(":", 1)[1] for p in KAFKA["ports"]}
    listeners = dict(x.split("://") for x in PROPS["listeners"].split(","))
    sasl_ports = {listeners[n].rsplit(":", 1)[1] for n in ("HOST", "PODS")}
    assert published == sasl_ports


def test_deny_by_default_with_the_standard_authorizer():
    assert PROPS["authorizer.class.name"].endswith("StandardAuthorizer")
    assert PROPS["allow.everyone.if.no.acl.found"] == "false"
    assert set(PROPS["super.users"].split(";")) == {"User:ANONYMOUS", "User:admin"}
    assert PROPS["auto.create.topics.enable"] == "false"


def test_one_broker_means_one_replica_everywhere():
    for key in ("offsets.topic.replication.factor", "transaction.state.log.replication.factor",
                "transaction.state.log.min.isr", "share.coordinator.state.topic.replication.factor",
                "default.replication.factor", "min.insync.replicas"):  # fmt: skip
        assert PROPS[key] == "1", key


def test_heap_is_cut_and_the_container_is_capped():
    assert "-Xmx384m" in KAFKA["environment"]["KAFKA_HEAP_OPTS"]
    assert KAFKA["mem_limit"] == "768m"


def test_jvm_hardening_flag_is_set():
    # Why, and when it may go: private/security (S6.4). Re-check on every image bump.
    assert KAFKA["image"].startswith("apache/kafka:4.4.0@sha256:833b867a")
    assert "-XX:-UseBASE64Intrinsics" in KAFKA["environment"]["KAFKA_OPTS"]


# --- topics ------------------------------------------------------------------------------
def test_every_topic_has_one_partition_and_keeps_arrival_time():
    # The replay carries 2022 event times; with CreateTime retention, Kafka would delete
    # those records as soon as they land. Event time travels in the message body instead.
    for name, cfg in ka.TOPICS.items():
        assert cfg["message.timestamp.type"] == "LogAppendTime", name
    assert ka.PARTITIONS == 1  # receiver-side features need one total order (ADR 0005)


def test_the_stream_topics_exist():
    assert {"transactions", "decisions", "alerts", "transactions.dlq"} <= set(ka.TOPICS)


# --- who may do what -------------------------------------------------------------------
def _ops(user):
    return {
        (a.resource_type, a.name, a.operation) for a in ka.ACLS if a.principal == f"User:{user}"
    }


def test_the_replayer_can_only_write_transactions():
    assert _ops("replayer") == {("TOPIC", "transactions", "WRITE"),
                                ("TOPIC", "transactions", "DESCRIBE")}  # fmt: skip


def test_the_consumer_reads_transactions_and_writes_only_its_outputs():
    ops = _ops("consumer")
    assert ("TOPIC", "transactions", "READ") in ops
    assert ("GROUP", "graphguard-consumer", "READ") in ops
    written = {n for t, n, o in ops if o == "WRITE"}
    assert written == {"decisions", "alerts", "transactions.dlq"}
    assert not any(o in {"ALTER", "DELETE", "CREATE", "ALL"} for _, _, o in ops)


def test_the_shadow_writes_only_its_own_table():
    assert {n for t, n, o in _ops("shadow") if o == "WRITE"} == {"decisions.shadow"}


def test_the_monitor_can_only_describe():
    assert {o for _, _, o in _ops("monitor")} == {"DESCRIBE"}


def test_no_acl_grants_all_or_a_wildcard_write():
    for a in ka.ACLS:
        assert a.operation != "ALL"
        assert not (a.name == "*" and a.operation != "DESCRIBE")


def test_admin_has_no_acls_because_it_is_the_setup_super_user():
    assert _ops("admin") == set()
    assert set(ka.USERS) == {"admin", "replayer", "consumer", "shadow", "monitor", "labeler"}


def test_the_labeler_writes_only_labels_and_the_consumer_may_read_them():
    assert _ops("labeler") == {("TOPIC", "labels", "WRITE"), ("TOPIC", "labels", "DESCRIBE")}
    assert ("TOPIC", "labels", "READ") in _ops("consumer")


# --- client settings -------------------------------------------------------------------
def test_clients_log_in_with_scram_and_the_producer_is_idempotent(tmp_path):
    (tmp_path / "kafka-replayer.env").write_text("GG_KAFKA_REPLAYER_PASSWORD=pw\n")
    cfg = ka.client_config("replayer", secrets_dir=tmp_path)
    assert cfg["security.protocol"] == "SASL_PLAINTEXT"
    assert cfg["sasl.mechanisms"] == "SCRAM-SHA-512"
    assert cfg["sasl.username"] == "replayer" and cfg["sasl.password"] == "pw"
    assert ka.PRODUCER["enable.idempotence"] is True and ka.PRODUCER["acks"] == "all"


def test_secrets_are_generated_once_and_never_rotated_by_accident(tmp_path):
    ka.generate_secrets(tmp_path)
    first = (tmp_path / "kafka.env").read_text()
    ka.generate_secrets(tmp_path)
    assert (tmp_path / "kafka.env").read_text() == first
    for user in ka.USERS:
        f = tmp_path / f"kafka-{user}.env"
        assert oct(f.stat().st_mode & 0o777) == "0o600"
        assert f.read_text().count("=") == 1  # only that user's password
