"""The live broker refuses what each login may not do (S6.4).

Runs where `graphguard-kafka` is up and `.secrets/kafka-*.env` exist; skips elsewhere
(CI). Positive checks write one marked record, and the admin deletes it again at the end,
so the stream's topic is left empty.
"""

import datetime as dt
import uuid

import pytest

from graphguard.stream import kafka_admin as ka

SECRETS = ka.SECRETS
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not (SECRETS / "kafka-admin.env").exists(), reason="Kafka not set up"),
]


def _cfg(user, **extra):
    return {**ka.client_config(user, secrets_dir=SECRETS), **extra}


def _produce(cfg, topic, value=b"probe", ts_ms=None, offsets=None):
    """Send one marked record; the delivery error (None = delivered). `offsets` collects
    where it landed, so a reader can go straight there however full the topic is."""
    from confluent_kafka import Producer

    errors = []

    def report(err, msg):
        errors.append(err)
        if err is None and offsets is not None:
            offsets.append(msg.offset())

    p = Producer({**cfg, "message.timeout.ms": 8000})
    p.produce(topic, value, headers={"graphguard-test": b"1"}, timestamp=ts_ms or 0,
              on_delivery=report)  # fmt: skip
    p.flush(15)
    return errors[0] if errors else "no delivery report"


def _consume_error(cfg, topic, group):
    from confluent_kafka import Consumer

    c = Consumer({**cfg, "group.id": group, "auto.offset.reset": "earliest",
                  "enable.auto.commit": False})  # fmt: skip
    c.subscribe([topic])
    try:
        for _ in range(20):
            msg = c.poll(1.0)
            if msg is not None and msg.error():
                return msg.error().name()
            if msg is not None:
                return "OK"
        return "NOTHING"
    finally:
        c.close()


@pytest.fixture(scope="module", autouse=True)
def leave_topics_empty():
    yield
    from confluent_kafka import TopicPartition
    from confluent_kafka.admin import AdminClient

    admin = AdminClient(_cfg("admin"))
    for topic in ("transactions", "decisions"):
        tp = TopicPartition(topic, 0, -1)  # -1 = up to the end
        for fut in admin.delete_records([tp]).values():
            fut.result(timeout=30)


def test_no_login_gets_nothing():
    from confluent_kafka.admin import AdminClient

    admin = AdminClient({"bootstrap.servers": ka.HOST_BOOTSTRAP, "socket.timeout.ms": 3000})
    with pytest.raises(Exception):  # noqa: B017 -- any failure: SASL is mandatory
        admin.list_topics(timeout=5)


def test_a_wrong_password_is_refused():
    from confluent_kafka.admin import AdminClient

    cfg = _cfg("replayer", **{"sasl.password": "wrong"})  # betterleaks:allow -- deliberately wrong
    with pytest.raises(Exception):  # noqa: B017
        AdminClient(cfg).list_topics(timeout=8)


def test_the_replayer_writes_transactions_and_nothing_else():
    assert _produce(_cfg("replayer"), "transactions") is None
    assert _produce(_cfg("replayer"), "decisions").name() == "TOPIC_AUTHORIZATION_FAILED"
    err = _consume_error(_cfg("replayer"), "transactions", "graphguard-consumer")
    assert err in {"TOPIC_AUTHORIZATION_FAILED", "GROUP_AUTHORIZATION_FAILED"}


def test_the_consumer_reads_with_its_own_group_only_and_cannot_write_input():
    _produce(_cfg("replayer"), "transactions")
    assert _consume_error(_cfg("consumer"), "transactions", "graphguard-consumer") == "OK"
    assert _consume_error(_cfg("consumer"), "transactions", f"other-{uuid.uuid4().hex[:6]}") == (
        "GROUP_AUTHORIZATION_FAILED"
    )
    assert _produce(_cfg("consumer"), "transactions").name() == "TOPIC_AUTHORIZATION_FAILED"
    assert _produce(_cfg("consumer"), "decisions") is None


def test_nobody_but_admin_can_create_topics():
    from confluent_kafka.admin import AdminClient, NewTopic

    for user in ("replayer", "consumer", "shadow", "monitor"):
        admin = AdminClient(_cfg(user))  # keep the handle alive until the answer arrives
        fut = admin.create_topics([NewTopic(f"x-{uuid.uuid4().hex[:6]}", 1, 1)])
        with pytest.raises(Exception, match="AUTHORIZATION"):
            list(fut.values())[0].result(timeout=15)


def test_the_monitor_cannot_read_or_write():
    assert _produce(_cfg("monitor"), "transactions").name() == "TOPIC_AUTHORIZATION_FAILED"
    err = _consume_error(_cfg("monitor"), "transactions", "graphguard-consumer")
    assert err in {"TOPIC_AUTHORIZATION_FAILED", "GROUP_AUTHORIZATION_FAILED"}


def test_a_2022_event_time_is_kept_because_retention_uses_arrival_time():
    from confluent_kafka import TIMESTAMP_LOG_APPEND_TIME, Consumer, TopicPartition

    old = int(dt.datetime(2022, 9, 6, tzinfo=dt.UTC).timestamp() * 1000)
    where: list[int] = []
    assert _produce(_cfg("replayer"), "transactions", b"old", ts_ms=old, offsets=where) is None
    c = Consumer({**_cfg("consumer"), "group.id": "graphguard-consumer",
                  "enable.auto.commit": False})  # fmt: skip
    # Straight to our record: the topic may already hold a whole replay (this test used to
    # read from the start and give up after 20 records -- flaky after every e2e run).
    c.assign([TopicPartition("transactions", 0, where[0])])
    try:
        seen = None
        for _ in range(20):
            msg = c.poll(1.0)
            if msg is not None and not msg.error() and msg.value() == b"old":
                seen = msg
                break
    finally:
        c.close()
    assert seen is not None
    kind, ts = seen.timestamp()
    assert kind == TIMESTAMP_LOG_APPEND_TIME and ts > old + 10**11  # stamped on arrival (2026)


def test_the_pod_bridge_listener_also_requires_a_login():
    from confluent_kafka.admin import AdminClient

    ok = AdminClient(ka.client_config("consumer", ka.POD_BOOTSTRAP, SECRETS))
    assert "transactions" in ok.list_topics(timeout=10).topics
    anon = AdminClient({"bootstrap.servers": ka.POD_BOOTSTRAP, "socket.timeout.ms": 3000})
    with pytest.raises(Exception):  # noqa: B017
        anon.list_topics(timeout=5)
