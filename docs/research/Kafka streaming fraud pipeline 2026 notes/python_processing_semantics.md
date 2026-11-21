# Python Kafka producer/consumer: delivery guarantees, exactly-once, failure handling (as of 2026-11-21)

Scope: a Python producer replays historical transactions into a Kafka 4.x topic in event-time order. A Python consumer updates Redis features, scores with XGBoost in process (~0.6 ms CPU per event), and writes the decision to Postgres and a results topic. Single broker, single box, little memory. It must survive kill -9 with nothing lost and nothing counted twice.

Research budget: about 15 tool calls. Primary sources were used where reachable: the confluent-kafka-python changelog, librdkafka INTRODUCTION.md and CONFIGURATION.md, the Apache Kafka docs, and the aiokafka, kafka-python and quixstreams docs. Some questions (DLQ patterns, CVE databases, measured client memory) were not covered by primary sources in this pass. They are listed under Gaps.

## 1. Python clients in Nov 2026: maturity, KIP-848, transactions, asyncio, wheels, memory, CVEs

### Takeaway
**confluent-kafka-python (librdkafka) is the right choice.** In Nov 2026 it is the only Python client with all of the following:
- GA support for KIP-848 (`group.protocol=consumer`, since 2.12.0, Oct 2025)
- transactions
- non-experimental asyncio classes (since 2.13.0)
- wheels from 3.12 through 3.15

aiokafka and kafka-python are both pure Python and active, but neither supports KIP-848. quixstreams sits on top as a framework. Its exactly-once covers Kafka outputs, not a Redis + Postgres sink.

### Cited Findings
**confluent-kafka-python**
- Latest line is v2.16.x, built on librdkafka 2.16.0:
  - v2.16.0 adds free-threaded CPython support (3.14t wheels). In the same release, `Producer.close()` now aborts any open transaction.
  - v2.16.1 requires `certifi>=2026.10.19` for the Schema Registry client, so it stops trusting a root CA whose intermediate keys were compromised. No CVE ID is named.
  - v2.16.2 adds 3.15/3.15t wheels and drops 3.8. — [confluent-kafka-python CHANGELOG](https://github.com/confluentinc/confluent-kafka-python/blob/master/CHANGELOG.md)
- Earlier dated releases:
  - v2.14.2 (2026-06-03): maintenance.
  - v2.14.0 (2026-04-01): async context managers for `AIOProducer`/`AIOConsumer`.
  - v2.13.2 (2026-03-02): fixes a memory leak in `Producer.produce()`.
  - v2.13.0 (2025-12-15): the async classes lose their "experimental" label.
  - v2.12.0 (2025-10-09): KIP-848 marked "General Availability", plus `AIOProducer` (beta, with transactional operations).
  - v2.15.0: adds a *Preview* KIP-932 share consumer.
  - v2.15.1: fixes race conditions and a segfault on Python 3.14. — [CHANGELOG](https://github.com/confluentinc/confluent-kafka-python/blob/master/CHANGELOG.md)
- Python 3.12 wheels have been published since v2.3.0. — [CHANGELOG](https://github.com/confluentinc/confluent-kafka-python/blob/master/CHANGELOG.md)
- Confluent calls the KIP-848 protocol "production ready starting with version 2.12.0". — [Confluent blog: client updates KIP-848](https://www.confluent.io/blog/kafka-client-updates-kip-848-oauth/)
- KIP-848 needs broker v4.0.0+ and librdkafka v2.12.0+, and it is opt-in (`group.protocol` defaults to `classic`). — [librdkafka INTRODUCTION.md](https://github.com/confluentinc/librdkafka/blob/master/INTRODUCTION.md)

**aiokafka (pure-Python asyncio)**
- 0.14.0 (2026-04-29) adds rack-aware fetching (KIP-392). It also fixes transaction failures when the coordinator is dead, and produces a batch when *either* the max size or the linger time is reached.
- 0.13.0 (2026-01-02) refreshes the transaction coordinator after broker fail-over. It also removes the `api_version` parameter, a breaking change; 0.14 restores it as deprecated.
- No KIP-848 support appears in its changelog. — [aiokafka CHANGES.rst](https://github.com/aio-libs/aiokafka/blob/master/CHANGES.rst)
- PyPI lists 0.14.0 as requiring Python ≥3.10. — [PyPI aiokafka](https://pypi.org/project/aiokafka/)

**kafka-python (pure Python)**
- 3.0.0 was released 2026-06-11. It is Python 3 only (≥3.8), with a protocol stack generated from Kafka's JSON message schemas. It ships as a pure `py3-none-any` wheel. 3.0.9 was out by 2026-07-21, and Read the Docs lists up to 3.0.11. — [PyPI kafka-python 3.0.0](https://pypi.org/project/kafka-python/3.0.0/), [Upgrading 2.3→3.0](https://kafka-python.readthedocs.io/en/3.0.0/upgrade_to_3_0.html)
- KIP support in kafka-python:
  - KIP-98 (EOS) supported since 2.2.0
  - KIP-447 supported since 3.0.0
  - KIP-890 (transaction server-side defense, the 4.0 protocol) only **partial**: transaction RPCs are capped below the KIP-890 versions
  - KIP-848 and KIP-932 **not supported** — [kafka-python Supported KIPs](https://kafka-python.readthedocs.io/en/master/kips.html)

**quixstreams**
- Latest is 3.28.1 (2026-10-15). Needs Python ≥3.11. Advertises "Exactly-once processing guarantees" via Kafka transactions. — [PyPI quixstreams](https://pypi.org/project/quixstreams/)
- At-least-once is the default (`processing_guarantee` switches it).
- Checkpoints run every `commit_interval` = 5 s by default. Each checkpoint flushes sinks, produces changelogs, flushes the producer, commits input offsets, then flushes state stores.
- Its sink guidance says re-flush after a revocation timeout "is safe under at-least-once semantics". The page does not claim EOS for external sinks. — [Quix checkpointing docs](https://docs.quix.io/quix-streams/advanced/checkpointing.html)

### Inferences
- **Pick confluent-kafka-python ≥2.16.2, pinned under the project's 14-day rule.** It has a C core with bounded, configurable queues (see §5 for memory settings). Synchronous `Consumer` + `Producer` is the simplest correct choice. The scoring work is CPU-bound (~0.6 ms), so asyncio buys little. `AIOConsumer` is available if the rest of the code becomes async.
- KIP-848 is optional on a single-consumer setup, since there is nothing to rebalance between. Enabling `group.protocol=consumer` is low-risk and gives the faster, incremental rebalance protocol. Callbacks must then use the incremental assign/unassign semantics.
- **Avoid quixstreams for this design.** Its EOS stops at Kafka, and it adds a RocksDB state store and its own checkpoint model on top of the project's own Redis feature store.
- Avoid kafka-python if you rely on transactions against Kafka 4. Its KIP-890 support is only partial.

### Gaps
- **librdkafka and KIP-890 TV2:** no explicit librdkafka changelog entry for client-side KIP-890 "transaction version 2" was found. Kafka docs say producers upgrade dynamically on reconnect (§2), but this was not confirmed for librdkafka.
- **Client memory:** no independent measurement of per-client RSS (confluent-kafka vs aiokafka) was found. Measure locally.
- **CVEs:** no CVE database was queried. The only security item found is the certifi bump in confluent-kafka 2.16.1.

## 2. Delivery semantics: idempotent producer, offset commits, EOS vs idempotent sink

### Takeaway
- **Producer:** `enable.idempotence=true` makes librdkafka force `acks=all`, `max.in.flight≤5`, unlimited retries and fifo queueing. That removes producer-side duplicates and reordering.
- **Consumer:** Kafka transactions (`send_offsets_to_transaction`) only make Kafka-to-Kafka read-process-write exactly-once. They do *not* cover Redis or Postgres. For this pipeline, effectively-once comes from at-least-once delivery plus an idempotent sink: keep the consumed position, or an event-id dedup row, inside the same Postgres transaction as the decision, and make Redis updates conditional on a per-account last-applied sequence.

### Cited Findings
**Producer defaults and idempotence**
- librdkafka defaults: `enable.idempotence=false`, `acks=-1` (all), `max.in.flight=1000000`, `retries=2147483647`, `message.timeout.ms=300000`, `linger.ms=5`, `transaction.timeout.ms=60000`. — [librdkafka CONFIGURATION.md](https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md)
- With `enable.idempotence=true`, unless you set them yourself, librdkafka sets `max.in.flight=5` (must stay ≤5), `retries=INT32_MAX`, `acks=all` and `queuing.strategy=fifo`. Conflicting explicit settings, such as `acks=1`, fail producer creation. — [CONFIGURATION.md](https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md), [INTRODUCTION.md](https://github.com/confluentinc/librdkafka/blob/master/INTRODUCTION.md)
- Idempotence keeps ordering with max.in.flight up to 5.
- Fatal idempotent errors: `OUT_OF_ORDER_SEQUENCE_NUMBER` (when head-of-line) and `UNKNOWN_PRODUCER_ID` (unless benign expiry).
- An experimental `enable.gapless.guarantee` exists and is off by default. — [INTRODUCTION.md](https://github.com/confluentinc/librdkafka/blob/master/INTRODUCTION.md)

**Consumer offsets**
- Consumer defaults: `enable.auto.commit=true`, `auto.commit.interval.ms=5000`, `enable.auto.offset.store=true`, `isolation.level=read_committed`, `auto.offset.reset=largest`. — [CONFIGURATION.md](https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md)
- librdkafka's at-least-once recipe:
  1. Set `enable.auto.offset.store=false`.
  2. Process the message.
  3. Call `store_offsets()`.
  4. Keep `enable.auto.commit=true` so the background committer commits only stored offsets.
- Only greater offsets are committed; storing an older one has no effect. — [INTRODUCTION.md](https://github.com/confluentinc/librdkafka/blob/master/INTRODUCTION.md)

**Transactions**
- Transaction errors fall into three classes:
  - retriable
  - abortable (`txn_requires_abort()`: call `abort_transaction()` and retry)
  - fatal (destroy the producer)
- Treat unflagged errors as fatal. A newer producer with the same `transactional.id` fences the old one with `__FENCED`. `message.timeout.ms` must be lower than `transaction.timeout.ms`. — [INTRODUCTION.md](https://github.com/confluentinc/librdkafka/blob/master/INTRODUCTION.md)
- Kafka 4.0 ships KIP-890 phase 2 (server-side transaction defense, "transaction version 2"):
  - It is on by default once the 4.0 upgrade is finalized, controlled by the `transaction.version` feature flag.
  - The producer epoch is bumped on every transaction, so a late duplicate cannot land in the next transaction. This reduces "zombie transactions".
  - Producers upgrade on their next connect, never mid-transaction. — [Kafka transaction protocol docs](https://kafka.apache.org/41/operations/transaction-protocol/), [Kafka 4.0 upgrade notes](https://kafka.apache.org/40/getting-started/upgrade/), [Confluent: Introducing Kafka 4.0](https://www.confluent.io/blog/introducing-apache-kafka-4-0/)
- Kafka's exactly-once covers the read-process-write cycle inside Kafka. — [Confluent: Exactly-once semantics are possible](https://www.confluent.io/pt-br/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/)
- External writes sit outside that transaction ("two systems, not one"). No single transaction can span the application database and Kafka. — [nejckorasa, Idempotent processing with Kafka](https://dev.to/nejckorasa/idempotent-processing-with-kafka-11l5) (blog, secondary)

**Patterns for an external sink**
- Store the offset in an offsets table inside the same DB transaction as the results, and seek to the stored offsets on start. — [Apache Kafka users mailing list](https://go.mail-archive.com/users@kafka.apache.org/msg30622.html)
- (topic, partition, offset) is a unique dedup key for a record. — [Kafka Cookbook: processing guarantees](https://dsbasko.github.io/kafka-cookbook/en/03-consumer/03-03-processing-guarantees/) (secondary)
- Dedup row in the same DB transaction as the effect, with the Kafka commit only after the DB commit. — [OrderHub day 32](https://dev.to/dev48v/orderhub-day-32-exactly-once-kafka-consumers-a-dedup-row-in-the-same-db-transaction-as-the-5fje) (blog)
- DBOS records the idempotency key inside the same transaction, then commits the offset. — [DBOS blog](https://www.dbos.dev/blog/exactly-once-apache-kafka-processing) (vendor)
- Transactional outbox: write state plus the outgoing message in one local transaction and publish from the outbox. — [Kafka Cookbook](https://dsbasko.github.io/kafka-cookbook/en/03-consumer/03-03-processing-guarantees/)

### Inferences (recommended design for this pipeline)
**Producer (replayer)**
- Settings: `enable.idempotence=true` (implies `acks=all`, max.in.flight 5), `compression.type=lz4` or `zstd`, `linger.ms=5–20`.
- Key messages by `source_row` (the transaction key) or by sender account. Keying by account keeps per-account order inside a partition, which matters for feature updates. On a single partition, everything is ordered anyway.
- Idempotence only removes duplicates *within one producer session*. If the replayer is killed and restarted, it must resume from a durable checkpoint, for example the last acked `source_row`, stored after delivery callbacks confirm it. Otherwise it re-sends rows.
- Make re-sends harmless: every event carries a stable `event_id = source_row` and the consumer dedups on it. That is simpler and more robust than a transactional producer for a replayer.

**Consumer**
- Settings: `enable.auto.commit=false` (or `true` with `enable.auto.offset.store=false`), `isolation.level=read_committed`, `auto.offset.reset=earliest`.
- Postgres is the source of truth. In one Postgres transaction per micro-batch:
  - `INSERT ... ON CONFLICT (event_id) DO NOTHING` into the decisions table
  - `UPSERT` into `consumer_offsets(topic, partition, next_offset)`
  - commit
- On start (in `on_assign`), read `consumer_offsets` and seek there. Committing the offset to Kafka afterwards is optional, for lag monitoring only.
- With the offset kept in Postgres, a crash between the Postgres commit and the Kafka commit cannot double count.
- Redis is not transactional with Postgres, so make Redis updates idempotent on their own. Each account hash keeps `last_seq`, the (timestamp, source_row) of the last event applied; FINDING-010 says to order by both. A Lua script applies the feature delta only if the incoming seq > `last_seq`, and sets `last_seq` atomically. A replay after a crash then becomes a no-op for events already applied.
  - Caveat: after a crash, Redis may be *ahead* of Postgres for a batch. On replay, Redis skips and Postgres writes. Scoring needs the features *as of before* the event, so replayed events must be scored with the stored pre-event feature snapshot, or with the decision row already recorded. The simplest rule: if the decision for `event_id` already exists in Postgres, skip; else compute.
  - Safer alternative: record the decision, *including the feature values used*, in Postgres first. Then apply the Redis deltas idempotently. On replay, re-applying deltas is guarded by `last_seq`, and the decision is never recomputed.
- Results topic: produce to it after the Postgres commit, with an idempotent producer and `event_id` as key. Downstream readers dedup on `event_id`. Alternatively, publish it from an outbox table in the same Postgres transaction.
- A Kafka transaction (`send_offsets_to_transaction`) would only make the *results topic + input offset* atomic. It does nothing for Redis or Postgres, and adds a transaction coordinator plus `transaction.timeout.ms` failure modes. It is not worth it here.

### Gaps
- No primary source from Stripe, Uber, Shopify or Zalando was fetched in this pass. The idempotent-consumer sources above are mostly blogs and secondary.
- No source was found that specifically describes the Redis Lua last-applied-sequence pattern. It is presented here as an inference.

## 3. Dead-letter queues, retry topics, schema validation on consume

### Takeaway
No primary-source documentation was gathered in this pass. Kafka and librdkafka have no built-in DLQ; it is an application pattern. The recommendation below is inference.

### Cited Findings
- Abortable vs fatal error classes in librdkafka decide what is retried in process and what kills the client. — [INTRODUCTION.md](https://github.com/confluentinc/librdkafka/blob/master/INTRODUCTION.md)
- quixstreams re-flushes sink batches after revocation timeouts under at-least-once, so duplicates must be tolerated. — [Quix checkpointing docs](https://docs.quix.io/quix-streams/advanced/checkpointing.html)

### Inferences
- **Split failures into two kinds:**
  - *Poison:* deserialize or validation failure, or a score exception on a specific record. Retrying cannot fix it. Produce the raw bytes plus headers (error class, message, source topic/partition/offset, consumer version) to `transactions.dlq`, record it in the same Postgres transaction as the batch (counts toward the offset advance), and move on.
  - *Transient:* Redis or Postgres down. Do **not** DLQ these. Stop advancing, back off and retry the whole batch. The scorer's existing 503/"not loaded" semantics map onto this: pause consumption (`consumer.pause()`) until the store marker exists.
- Retry topics (delayed retry tiers) are unnecessary for a replayed stream with no external API calls. A single DLQ plus a replay script is enough.
- Schema validation on consume: validate with a Pydantic model (or the existing Pandera contract) right after deserialization. A validation failure means DLQ, never a crash loop.

### Gaps
- No primary sources were found on Python DLQ libraries or patterns in 2026 (for example, Confluent's or Uber's retry-topic write-ups were not fetched).

## 4. Serialization and schema registry

### Takeaway
**On a tiny single-producer, single-consumer box, versioned JSON (or JSON Schema) contracts in code with Pydantic validation are enough.** A registry costs an extra JVM or Python service, hundreds of MB by vendor estimates, for no consumer it would actually protect.

### Cited Findings
- Licences: Karapace and Apicurio are Apache 2.0. Confluent Schema Registry is under the Confluent Community License. — [AxonOps comparison](https://axonops.com/blog/comparing-kafka-schema-registries/) (vendor). Apicurio also describes itself as fully Apache 2.0. — [CNCF sandbox issue](https://github.com/cncf/sandbox/issues/461)
- Memory estimates, vendor-produced and unverified:
  - AxonOps' own registry: ~50 MB
  - Karapace: ~200 MB
  - Apicurio: ~300 MB
  - Confluent SR: ~500 MB+
  — [AxonOps comparison](https://axonops.com/blog/comparing-kafka-schema-registries/)
- Karapace's README describes its memory only as "moderate" and claims API compatibility with Confluent SR up to 6.1.1. — [Karapace README](https://github.com/aiven/karapace/blob/master/README.rst)
- Apicurio runs on Quarkus, "for low memory footprint". Storage can be Kafka or PostgreSQL. — [Red Hat Apicurio Registry 3.0 guide](https://docs.redhat.com/en/documentation/red_hat_build_of_apicurio_registry/3.0/html-single/apicurio_registry_user_guide/apicurio_registry_user_guide)
- confluent-kafka 2.16.0 added experimental async serde classes. 2.12.2 hot-fixed an Avro schema-evolution crash in the Schema Registry client. — [CHANGELOG](https://github.com/confluentinc/confluent-kafka-python/blob/master/CHANGELOG.md)

### Inferences
- **Use JSON (orjson) with a `schema_version` field in each message (or a header), plus a Pydantic v2 model per version, kept in the repo and tested as a contract.** It is human-readable for a portfolio and has zero extra RAM.
- If binary or schema evolution is wanted later, Protobuf with generated classes in code still needs no registry.
- If a registry is ever wanted for demo value, Apicurio on the existing Postgres is the lightest licence-clean option. Its RAM must be measured against the 4 GB budget first.

### Gaps
- No independent RAM benchmarks for the registries were found. The figures come from a competing vendor.

## 5. Throughput: micro-batching, backpressure, lag, max.poll.interval.ms, shutdown, rebalances

### Takeaway
- **Micro-batch:** `consume(num_messages=N, timeout=…)`, then pipeline the Redis Lua calls, write one Postgres transaction, then advance the offset.
- **Memory:** cap prefetch explicitly (the default consumer queue allows 64 MB per partition-set, and the producer queue up to 1 GB).
- **Shutdown:** on SIGTERM, stop polling, finish the in-flight batch, `flush()` the producer, then `close()` the consumer.

### Cited Findings
- Consumer memory defaults:
  - `queued.min.messages=100000`
  - `queued.max.messages.kbytes=65536` (takes priority)
  - `fetch.max.bytes=52428800`
- Liveness defaults: `max.poll.interval.ms=300000`; `session.timeout.ms=45000` (not used with `group.protocol=consumer`).
- `group.instance.id` enables static membership, so a member can rejoin without a rebalance.
- Producer queue defaults: `queue.buffering.max.messages=100000`, `queue.buffering.max.kbytes=1048576`, `batch.size=1000000`. — [CONFIGURATION.md](https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md)
- With KIP-848, rebalance callbacks get only the partitions being added or revoked (incremental assign/unassign). `partition.assignment.strategy` is replaced by `group.remote.assignor` (`uniform`/`range`). Session and heartbeat timeouts move to broker configs (`group.consumer.session.timeout.ms`, `group.consumer.heartbeat.interval.ms`). — [INTRODUCTION.md](https://github.com/confluentinc/librdkafka/blob/master/INTRODUCTION.md)
- `Producer.close()` aborts an open transaction (v2.16.0). — [CHANGELOG](https://github.com/confluentinc/confluent-kafka-python/blob/master/CHANGELOG.md)

### Inferences
- Throughput math: 0.6 ms of CPU per event is about 1,600 events/s for one core before I/O. Batching Redis (one pipeline of Lua `EVALSHA` per batch) and Postgres (`COPY` or `executemany` / `execute_values` with `ON CONFLICT`) amortizes round trips. Batches of 200–1000 messages or 100–500 ms are reasonable starting points.
- Memory caps to set: `queued.max.messages.kbytes=8192–16384`, `queued.min.messages=1000–10000`, `fetch.max.bytes` around 8 MB. On the replayer: `queue.buffering.max.kbytes=32768` or so, and handle `BufferError` by calling `poll()`/`flush()` (backpressure).
- Replay pacing: the producer should throttle to a target rate (event-time × speed factor). Otherwise it fills the topic far ahead and lag becomes meaningless. Measure consumer lag as committed (or Postgres-stored) offset vs high watermark (`get_watermark_offsets`). Export it as a metric.
- `max.poll.interval.ms`: a batch of 1000 at about 1 ms is about 1 s, far below 300 s. Keep the default, but bound batch time. If Redis or Postgres is down, use `pause()` and keep calling `poll()` so the consumer is not evicted.
- SIGTERM handling:
  1. The signal handler sets a flag.
  2. The loop exits after the current batch commits to Postgres.
  3. `producer.flush(timeout)`.
  4. `consumer.close()`. With the commit-after-processing design, close never commits unprocessed work.
- Rebalance callbacks: in `on_revoke`, finish or discard the in-flight batch before the partition goes. In `on_assign`, seek to Postgres-stored offsets.
- Static membership (`group.instance.id`) avoids a rebalance on a quick restart under the classic protocol.

### Gaps
- No measured numbers for confluent-kafka consumer RSS at these settings were found. Measure under the container cap.

## 6. Testing: integration tests and fault injection in CI

### Takeaway
Use a real single-node KRaft broker in a container. The `apache/kafka-native` GraalVM image is the lightest official option. Fault tests should kill -9 the consumer at random points, restart the broker, and inject duplicate deliveries. Then assert on Postgres that the count of `event_id` equals the count of produced events, with no duplicates, and that the Redis features equal a batch recomputation.

### Cited Findings
- `apache/kafka-native` runs a GraalVM-native Kafka broker as a combined broker + KRaft controller by default. — [Docker Hub apache/kafka-native](https://hub.docker.com/r/apache/kafka-native)
- Testcontainers' Java module supports `apache/kafka` and `apache/kafka-native`. — [Testcontainers Kafka module (Java)](https://java.testcontainers.org/modules/kafka)
- The Python module is `pip install testcontainers[kafka]`, used as `with KafkaContainer() as kafka:`. The default image is not documented on the community page. An older summary shows `confluentinc/cp-kafka:7.6.0`. — [Testcontainers community module](https://testcontainers.com/modules/kafka/)
- Confluent has a tutorial on kafka-native with Testcontainers. — [Confluent tutorial](https://developer.confluent.io/confluent-tutorials/kafka-native-testcontainers/kafka/)

### Inferences
- **CI here** runs `runs-on: graphguard` with a 2 GB job cap and a fresh network per job. A sibling broker container needs Docker access from the job, which the isolation probe forbids. The likely option is a broker started *inside* the job's own compose/service definition, capped (for example 512 MB), or `kafka-native` with a small heap. This must be checked against `scripts/ci/isolation-probe.sh` and the compose hardening test before choosing.
- Layer the tests:
  1. Unit tests with a fake consumer/producer interface. Wrap confluent-kafka behind a small protocol, then mock only that external boundary.
  2. Integration tests against the real broker: produce N, consume, assert exactly N decisions.
  3. Fault tests (marked `slow`):
     - (a) run the consumer as a subprocess and `SIGKILL` it at a random batch boundary, and *inside* a batch (between the Redis apply and the Postgres commit, using a fault hook env var), then restart
     - (b) restart the broker container mid-stream
     - (c) re-produce a slice of events (duplicate delivery), and rewind offsets by seeking back
- Assertions after each fault test:
  - `SELECT count(*), count(DISTINCT event_id)` equals the number of distinct produced events
  - the stored offset equals the high watermark
  - per-account Redis features equal an offline as-of recomputation from the same events. This reuses the project's train/serve parity machinery.
- Repeat with randomized kill points over a fixed seed list, so the tests stay deterministic.

### Gaps
- No primary source was found on the Python testcontainers Kafka module's current default image, or on KRaft support in it. Check the testcontainers-python source.
- No measured RAM for `apache/kafka-native` was found here.
- No dedicated talk or blog on fault-injection testing of streaming correctness (for example Jepsen-style) was fetched in this pass.
