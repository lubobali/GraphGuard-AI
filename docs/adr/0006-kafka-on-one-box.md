# ADR 0006 — Kafka on one box: one KRaft node, SCRAM + deny-by-default, a plain consumer

**Status:** accepted, 2026-11-21 (S6.4)
**Decided by:** Lubo approved Phase 6 with D3 (consumer on k3s) and D4 (SCRAM without TLS);
the measurements below decided the sizes.

## Context

Phase 6 replays the validation window as a live stream. R-2 replaced Redpanda (no longer
source-available from 26.3.1) with Apache Kafka 4.x. The box gives the whole project ~4 GB,
and every container must be capped, unprivileged and reachable only from the box.

## Decision

**Broker.** Apache Kafka **4.4.0**, the official JVM image pinned by digest (built
2026-10-07). Not `apache/kafka-native`: Apache labels it experimental. One node in KRaft
combined mode (broker + controller, no ZooKeeper), every replication factor 1, topics with
one partition (ADR 0005: receiver-side features need one total order). Heap
`-Xms256m -Xmx384m` under a **768m** cap; uid 10380; read-only root; no capabilities.

**Listeners, explicit.** `CONTROLLER` and `INTERNAL` on the container's own loopback
(anonymous, so the broker can talk to itself — nothing outside the container reaches them);
`HOST` and `PODS` require a **SCRAM-SHA-512** login and are published only on the host's
loopback and the k3s pod bridge.

**Who may do what.** StandardAuthorizer, `allow.everyone.if.no.acl.found=false`; the ACLs
live in `src/graphguard/stream/kafka_admin.py` and `just kafka-setup` makes the broker match
them exactly (it removes anything else). One login per program: replayer (write
`transactions`), consumer (read it in its own group; write decisions / alerts / DLQ), shadow,
monitor (describe), admin (setup only). `just rotate-kafka` rotates them all, each proven.

**SCRAM without TLS** (D4). Every client is on the box; the remaining risk is someone who is
already root reading loopback traffic — and root can read `.secrets/` anyway. TLS with a
private CA is the stronger option, cheap at this load; it is the first change if any client
ever leaves the box.

**Arrival-time retention.** Topics use `message.timestamp.type=LogAppendTime`: the replay
carries 2022 event times, and with the default CreateTime, 7-day retention would delete
every record the moment it landed. Event time travels in the message body. Proven live.

**JVM hardening.** The broker runs with an extra JVM flag in `KAFKA_OPTS` for a known JDK
issue; the assessment and the condition for removing it are in the private record, and a
unit test keeps the flag in place.

**CI.** CI jobs cannot reach other containers (S5b.2 isolation probe), so CI runs the config
and ACL tests (`test_kafka_config.py`); the broker's behaviour is proven by live tests on the
box (`test_kafka_live.py`: no login, wrong password, each login's denials, arrival-time
retention, the pod listener).

**A plain consumer, not a framework.** Flink's shipped defaults ask ~3.3 GB (JobManager
1,600 MB + TaskManager 1,728 MB) before any Python worker; RisingWave wants ≥ 8 GiB; Bytewax
has had no release since Nov 2024. Quix Streams fits in memory but keeps its own state
(RocksDB) apart from the Redis the scorer reads, and its exactly-once covers Kafka outputs
only — it would add a second copy of state without removing any hard part. The consumer is a
few hundred lines of confluent-kafka 2.16 whose exactness is proven row by row (S6.3).

## Measured (2026-11-21)

| | |
|---|---|
| Idle | 332 MiB, 108 threads |
| 1,015,300 messages in (idempotent producer) | 1.9 s (~535k/s) |
| …and read back | 10.4 s |
| Peak during that | **422 MiB** of 768 MiB |

## Consequences

- One partition is the scaling limit (named in ADR 0005). Fine for ~190 tx/s peaks.
- Kafka's data dir `kafka-data/` (uid 10380, 700) is not backed up: the replay can always
  be re-sent from the lakehouse.
- The consumer pod's NetworkPolicy must allow the broker's post-DNAT address, the same
  trap as Redis — done with the consumer (S6.6).
