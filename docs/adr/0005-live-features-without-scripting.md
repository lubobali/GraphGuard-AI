# ADR 0005 — Live features: one writer, one MULTI/EXEC per batch, no Redis scripting

**Status:** accepted, 2026-11-21 (S6.3)
**Decided by:** Lubo approved S6.3; the design changes the research's suggestion for a
security reason stated below, and the measurements decided the rest.

## Context

The stream (Phase 6) must keep every account's features exact after every transaction:
FINDING-008 measured an 83% PR-AUC loss when cumulative features are refreshed in batch,
and FINDING-015 showed the online path must repeat training's arithmetic bit for bit. Each
event needs both accounts' state *before* it, then the update, and the two must be one
step — a crash in between must not count anything twice.

The research (`docs/research/Kafka streaming fraud pipeline 2026.md`) suggested one Redis
Function (Lua) per event. But S5b.1 removed scripting from every Redis user on purpose
(EVAL/FUNCTION; RediShell, CVE-2025-49844 — a use-after-free in Redis's Lua). Turning it
back on to make features faster would weaken a security decision for convenience.

## Decision

- **One writer.** One consumer reads one Kafka partition (S6.4-S6.6), so nothing else
  writes stream state. (A lease that stops a second writer comes with the consumer, S6.6.)
- **Read, compute in Python, write once.** For a micro-batch the writer reads what it needs
  in one pipeline (both hashes, seen-pair flags, 24 h window counts, pending records),
  `plan()` computes the whole batch with training's float64 arithmetic, and all writes go
  out in **one MULTI/EXEC** — Redis applies it entirely or not at all.
- **Repeats and crashes:** each account carries a watermark (last applied
  `(timestamp, source_row)`); each applied event leaves its before-state for 6 h (deleted
  once its decision is stored). A redelivered event gets the same features back; an older,
  unknown event is refused as `late`.
- **Distinct counts** from one global set of seen pairs (16,384 shards, so each stays in
  Redis's compact encoding): one answer says "new counterparty" for both sides.
- **24 h counts** from each sender's send times (sorted set), counted with an exclusive
  lower bound like training, trimmed as time moves.
- A new Redis user `stream` gets only the plain commands this uses; **still nobody has
  scripting**.

## Measured (2026-11-21)

| | |
|---|---|
| Full validation replay, memory store | 1,015,300 events, **0 mismatches** with training, 9,734 events/s |
| Same replay, real Redis (throwaway copy) | **0 mismatches**, **6,038 events/s** (busiest minute in the data: 187/s) |
| Redis memory | 224 MB of data at peak, 303 MiB resident → live Redis 320mb of data, 448m container cap |
| Seed (`store-load`) | 512,705 accounts + 481,525 recent sends + 936,359 pairs in 22 s |

## Consequences

- One partition is the scaling limit: receiver-side features need a total order. Past
  this box, the known way is a second stage keyed by receiver — named, not built.
- A reload (`store-load`) resets the stream to the snapshot, by design.
- Windows of senders who stop sending are trimmed only when they send again; bounded by one
  day of sends, and inside the measured peak.

## Alternatives rejected

- **Redis Function / Lua per event** — undoes S5b.1's no-scripting rule.
- **WATCH-based optimistic transactions** — needed only with several writers; one writer
  makes them dead weight.
- **Flink / Quix Streams** — Flink's shipped defaults ask ~3.3 GB; Quix keeps its own state
  copy (RocksDB) apart from the Redis the scorer reads. Recorded in the S6.4 ADR.
