"""The stream consumer (S6.6): read each transaction, score it once, store the decision.

    python -m graphguard.stream.consumer        # the k3s Deployment runs this

For every micro-batch:

1. **Decode** each Kafka record (`messages.decode`); a broken one becomes a dead letter.
2. **Reorder**: hold the newest records in a small buffer and release them in training's
   order (time, then `source_row`). A record up to `buffer_size` positions late is applied
   exactly where it belongs; later than that it is a dead letter (`late`), never a wrong
   score. (The replayer's `late_max_shift` must be smaller -- 50 vs 200.)
3. **Drop repeats** already decided (Postgres knows), whenever they arrive.
4. **Live features** (S6.3, `updater`): each event gets both accounts' state *before* it,
   then is applied -- one MULTI/EXEC per batch.
5. **Score in process** (FINDING-013: the HTTP hop costs ~94% of the CPU) with the same model
   bundle and `to_model_row` as the scorer, plus the cold-account policy (FINDING-014).
6. **One Postgres transaction**: decisions (`ON CONFLICT DO NOTHING`), dead letters, the
   Kafka position to resume from, and the outbox. Then the outbox is published to Kafka.

**One writer:** a Postgres advisory lock; a second consumer refuses to start. **Store down
or not loaded** (Redis restarted): pause, never score on zeros (S5.5's rule).
"""

from __future__ import annotations

import datetime as dt
import heapq
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass

from graphguard.serving.online_features import to_model_row
from graphguard.serving.service import COLD_POLICY, UNSEEN_CATEGORY
from graphguard.stream import messages as msg
from graphguard.stream import updater as up

log = logging.getLogger("graphguard.consumer")
GROUP = "graphguard-consumer"
TOPIC = "transactions"
LOCK_KEY = 6_006_006  # pg_advisory_lock key: one consumer at a time


@dataclass(frozen=True)
class Decision:
    event_id: int
    seq: int
    event_time: dt.datetime
    from_account: str
    to_account: str
    amount_paid: float
    score: float
    cold_policy: str
    model_version: str
    model_sha256: str
    features: tuple[float, ...]
    rules: tuple[str, ...] = ()
    alert: bool = False

    def payload(self) -> str:
        return json.dumps(
            {
                "event_id": self.event_id,
                "event_time": self.event_time.isoformat(),
                "score": self.score,
                "cold_policy": self.cold_policy,
                "rules": list(self.rules),
                "alert": self.alert,
                "model_version": self.model_version,
            },
            separators=(",", ":"),
        )


class ReorderBuffer:
    """Holds the newest `size` records; releases the oldest in training's order."""

    def __init__(self, size: int) -> None:
        self.size = size
        self._heap: list = []
        self._n = 0

    def __len__(self) -> int:
        return len(self._heap)

    def push(self, key, item, offset: int) -> list:
        heapq.heappush(self._heap, (key, self._n, item, offset))
        self._n += 1
        out = []
        while len(self._heap) > self.size:
            out.append(heapq.heappop(self._heap)[2])
        return out

    def drain(self) -> list:
        out = [heapq.heappop(self._heap)[2] for _ in range(len(self._heap))]
        return out

    def resume_offset(self, last: int | None) -> int | None:
        """Where a restart must begin: the oldest record still held, else after the last."""
        if self._heap:
            return min(entry[3] for entry in self._heap)
        return None if last is None else last + 1


def _dead(event_id, offset, reason, raw=None) -> dict:
    return {"event_id": event_id, "kafka_offset": offset, "reason": reason, "raw": raw}


class Consumer:
    """The decision logic, independent of where records come from (tested with fakes)."""

    def __init__(self, store, sink, model, model_info: dict, buffer_size: int = 200) -> None:
        self.store, self.sink, self.model, self.info = store, sink, model, model_info
        self.buffer = ReorderBuffer(buffer_size)
        self.last_offset: int | None = None
        self.currency = model.category_maps.get("payment_currency", {})
        self.counts = {"decided": 0, "repeats": 0, "late": 0, "malformed": 0}

    def step(self, records) -> None:
        released, dead = [], []
        for r in records:
            if r.error():
                continue
            self.last_offset = r.offset()
            try:
                t = msg.decode(r.value())
            except msg.MalformedRecord as e:
                dead.append(_dead(None, r.offset(), f"malformed: {e}", r.value()))
                self.counts["malformed"] += 1
                continue
            released += self.buffer.push((t.timestamp, t.event_id), (t, r.offset()), r.offset())
        self._process(released, dead)

    def flush(self) -> None:
        """Release everything held (end of stream, or a quiet moment)."""
        self._process(self.buffer.drain(), [])

    def _process(self, released: list, dead: list) -> None:
        if not released and not dead:
            return
        decided = self.sink.decided({t.event_id for t, _ in released}) if released else set()
        fresh, offsets, seen = [], {}, set()
        for t, off in released:
            if t.event_id in decided or t.event_id in seen:
                self.counts["repeats"] += 1
                continue
            seen.add(t.event_id)
            fresh.append(t)
            offsets[t.event_id] = off
        by_id = {t.event_id: t for t in fresh}
        events = [
            up.Event(t.event_id, t.timestamp, t.from_account, t.to_account, t.amount_paid)
            for t in fresh
        ]
        befores = self.store.apply(events) if events else []
        rows, kept = [], []
        for e, b in zip(sorted(events, key=up.order), befores, strict=True):
            t = by_id[e.source_row]
            if b.status == up.LATE:
                dead.append(_dead(t.event_id, offsets[t.event_id], "late"))
                self.counts["late"] += 1
                continue
            rows.append(
                to_model_row(
                    sender=b.sender,
                    receiver=b.receiver,
                    timestamp=t.timestamp,
                    amount_paid=t.amount_paid,
                    amount_received=t.amount_received,
                    from_bank=t.from_bank,
                    to_bank=t.to_bank,
                    payment_currency_code=self.currency.get(t.payment_currency, UNSEEN_CATEGORY),
                )
            )
            kept.append((t, b))
        scores = self.model.score_rows(rows) if rows else []
        cols = self.model.feature_columns
        decisions = [
            Decision(
                t.event_id,
                t.seq,
                t.timestamp,
                t.from_account,
                t.to_account,
                t.amount_paid,
                float(s),
                COLD_POLICY[(b.sender.is_cold, b.receiver.is_cold)],
                self.info["version"],
                self.info["sha256"] or "",
                tuple(float(row[c]) for c in cols),
            )
            for (t, b), s, row in zip(kept, scores, rows, strict=True)
        ]
        outbox = [
            {"topic": "decisions", "key": str(d.event_id), "payload": d.payload()}
            for d in decisions
        ]
        outbox += [
            {
                "topic": "transactions.dlq",
                "key": str(d["event_id"]),
                "payload": json.dumps({k: v for k, v in d.items() if k != "raw"}),
            }
            for d in dead
        ]
        self.sink.commit(decisions, dead, self.buffer.resume_offset(self.last_offset), outbox)
        self.store.ack([e.source_row for e in events])
        self.counts["decided"] += len(decisions)


# --- Postgres ----------------------------------------------------------------------------
_INSERT_DECISIONS = (
    "INSERT INTO decisions (event_id, seq, event_time, from_account, to_account, amount_paid, "
    "score, cold_policy, rules, alert, model_version, model_sha256, features) "
    "VALUES %s ON CONFLICT (event_id) DO NOTHING"
)


class PostgresSink:
    def __init__(
        self,
        conn,
        feature_names: tuple[str, ...],
        version: str,
        group: str = GROUP,
        topic: str = TOPIC,
    ) -> None:
        self.conn, self.group, self.topic = conn, group, topic
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feature_sets VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (version, list(feature_names)),
            )

    def load_offset(self) -> int | None:
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "SELECT next_offset FROM consumer_offsets WHERE grp=%s AND topic=%s AND part=0",
                (self.group, self.topic),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def decided(self, ids: set[int]) -> set[int]:
        with self.conn, self.conn.cursor() as cur:
            cur.execute("SELECT event_id FROM decisions WHERE event_id = ANY(%s)", (list(ids),))
            return {r[0] for r in cur.fetchall()}

    def commit(self, decisions, dead, next_offset, outbox) -> None:
        from psycopg2.extras import execute_values

        with self.conn, self.conn.cursor() as cur:  # one transaction
            if decisions:
                execute_values(
                    cur,
                    _INSERT_DECISIONS,
                    [
                        (
                            d.event_id,
                            d.seq,
                            d.event_time,
                            d.from_account,
                            d.to_account,
                            d.amount_paid,
                            d.score,
                            d.cold_policy,
                            list(d.rules),
                            d.alert,
                            d.model_version,
                            d.model_sha256,
                            list(d.features),
                        )
                        for d in decisions
                    ],
                )
            if dead:
                execute_values(
                    cur,
                    "INSERT INTO dead_letters (event_id, kafka_offset, reason, raw) VALUES %s",
                    [(d["event_id"], d["kafka_offset"], d["reason"], d["raw"]) for d in dead],
                )
            if next_offset is not None:
                cur.execute(
                    "INSERT INTO consumer_offsets (grp, topic, part, next_offset) VALUES "
                    "(%s, %s, 0, %s) ON CONFLICT (grp, topic, part) DO UPDATE SET "
                    "next_offset = EXCLUDED.next_offset, updated_at = now()",
                    (self.group, self.topic, next_offset),
                )
            if outbox:
                execute_values(
                    cur,
                    "INSERT INTO outbox (topic, msg_key, payload) VALUES %s",
                    [(o["topic"], o["key"], o["payload"]) for o in outbox],
                )

    def publish_outbox(self, producer, limit: int = 5_000) -> int:
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, topic, msg_key, payload FROM outbox WHERE published_at IS "
                "NULL ORDER BY id LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()
        if not rows:
            return 0
        errors = []
        for _, topic, key, payload in rows:
            producer.produce(
                topic,
                payload.encode(),
                key=key.encode(),
                on_delivery=lambda err, _m: err and errors.append(err),
            )
            producer.poll(0)
        producer.flush(60)
        if errors:
            raise RuntimeError(f"outbox publish failed: {errors[0]}")
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                "UPDATE outbox SET published_at = now() WHERE id = ANY(%s)", ([r[0] for r in rows],)
            )
        return len(rows)


def take_lease(conn) -> bool:
    """One writer: a session-level advisory lock, released when the connection closes."""
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,))
        return bool(cur.fetchone()[0])


# --- the process -------------------------------------------------------------------------
def _settings() -> dict:
    return {
        "kafka": os.environ.get("GRAPHGUARD_KAFKA_BOOTSTRAP", "127.0.0.1:9092"),
        "postgres": os.environ.get("GRAPHGUARD_STREAM_DB", "127.0.0.1:5434"),
        "buffer": int(os.environ.get("GRAPHGUARD_REORDER_BUFFER", "200")),
        "batch": int(os.environ.get("GRAPHGUARD_BATCH", "500")),
        "idle_flush_s": float(os.environ.get("GRAPHGUARD_IDLE_FLUSH_S", "5")),
    }


def _model():
    from graphguard.serving.app import load_model

    return load_model()


def run(stop=lambda: False, max_idle_s: float | None = None) -> dict:
    """The loop. `stop` and `max_idle_s` let tests end it; the pod runs until SIGTERM."""
    from confluent_kafka import (
        OFFSET_BEGINNING,
        Producer,
        TopicPartition,
    )
    from confluent_kafka import (
        Consumer as KafkaConsumer,
    )

    from graphguard.serving.store import RedisFeatureStore
    from graphguard.stream import db
    from graphguard.stream import kafka_admin as ka

    cfg = _settings()
    lease = db.connect(cfg["postgres"])
    if not take_lease(lease):
        raise SystemExit("another consumer holds the lease; refusing to start a second writer")
    m = _model()
    bundle = m["bundle"]
    sink = PostgresSink(db.connect(cfg["postgres"]), bundle.feature_columns, m["version"])
    redis = RedisFeatureStore(user="stream")
    store = up.RedisStore(redis.client)
    consumer = Consumer(store, sink, bundle, m, cfg["buffer"])
    start = sink.load_offset()
    kc = KafkaConsumer(
        {
            **ka.client_config("consumer", cfg["kafka"]),
            "group.id": GROUP,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "fetch.max.bytes": 8 * 1024 * 1024,
            "queued.max.messages.kbytes": 16384,
        }
    )
    kc.assign([TopicPartition(TOPIC, 0, start if start is not None else OFFSET_BEGINNING)])
    producer = Producer({**ka.client_config("consumer", cfg["kafka"]), **ka.PRODUCER})
    log.info("consumer up: model %s, resume at offset %s", m["version"], start)
    idle_since, last_log = time.monotonic(), time.monotonic()
    try:
        while not stop():
            if why := redis.readiness():  # Redis down or not loaded: wait, never cold scores
                log.warning("store %s; pausing", why)
                time.sleep(2)
                continue
            records = kc.consume(cfg["batch"], 1.0)
            if records:
                consumer.step(records)
                idle_since = time.monotonic()
            elif len(consumer.buffer) and time.monotonic() - idle_since > cfg["idle_flush_s"]:
                consumer.flush()
            elif max_idle_s is not None and time.monotonic() - idle_since > max_idle_s:
                break
            sink.publish_outbox(producer)
            if time.monotonic() - last_log > 10:
                log.info("counts %s, held %d", consumer.counts, len(consumer.buffer))
                last_log = time.monotonic()
        consumer.flush() if max_idle_s is not None else None
        sink.publish_outbox(producer)
    finally:
        kc.close()
        lease.close()
    return consumer.counts


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopping = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stopping.__setitem__("now", True))
    counts = run(stop=lambda: stopping["now"])
    log.info("stopped cleanly: %s", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
