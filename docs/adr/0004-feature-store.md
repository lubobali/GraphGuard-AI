# ADR 0004 — Feature store: keep our own; Feast evaluated, not adopted

**Status:** accepted, 2026-11-18 (S5.6e)
**Decided by:** Lubo approved the story that makes this decision by measurement; the
numbers below decided it.

## Context

Since August the plan said "Feast" while the code used its own store: Polars computes
account states, `gold.account_features_asof` holds them in the lakehouse, and
`just store-load` copies them into Redis, where the scorer reads them. R-2 asked for a
real decision: Feast as a library, or our own store with the reasons written down.

Feast is the open-source standard (Databricks and Tecton play the same role), and
since 0.64 it reads Iceberg natively. So the question was not "is Feast good", but
"does Feast reproduce *our* features exactly, at a cost this box can carry".

## What was measured (Feast 0.68.0, its own uv project `featurestore/`)

| | Feast | Our store |
|---|---|---|
| Online values, all 512,705 accounts × 9 features | **identical** to ours (counts as ints, money bit for bit, timestamps same instant) | — |
| Fill the online store | 36.3 s (materialise into SQLite) | **13.4 s** (`store-load` into Redis) |
| Peak RAM to fill it | **3,957 MB** — nearly the project's whole 4 GB budget | **580 MB** |
| Size of the filled store | 1,047 MB (SQLite file) | ~159 MB in Redis |
| Two-account lookup | p50 0.18 ms, p99 0.40 ms (local SQLite file) | Redis over the network: p99 7.6 ms end to end on k3s (S5.3) — not like for like |
| Training features with same-minute ties | **cannot reproduce them** (below) | exact, by (timestamp, source_row) |
| Dependencies | in the main project it downgrades the scorer's Redis client (8.1 → 7.4), `tenacity`, `prometheus-client`, and adds pandas, dask, gunicorn, mypy | — |

**The tie test** (`featurestore/tests/test_point_in_time_ties.py`, characterisation):
three payments from one account, two in the same minute. Training says the first saw 0
earlier sends, the second 1, the third 2. Feast's point-in-time join uses the event
timestamp and breaks ties by a `created` timestamp, so:
- with rows holding the count *before* each payment, the first payment receives the
  second one's row — it sees a payment that came **after** it;
- with rows holding the count *including* each payment, a payment **counts itself**.

Both are leakage (contract rule 3). 9.4% of transactions tie on the minute
(FINDING-010), so this is not an edge case.

**Integration findings.** Feast's type inference uses a small REST client that sends
the warehouse *name* where Lakekeeper expects its id (HTTP 400); declaring every column
avoids it. Feast authenticates with a static bearer token (no OAuth refresh) — fine for
a run under an hour. It reads the whole Iceberg table into memory before joining, which
is where the 4 GB goes. Vended credentials worked: Feast read as `reader`, with a
read-only key for that one table.

## Options

- **(a) Feast fills Redis and the scorer reads through Feast.** Rejected: 7× the RAM of
  our loader on a box with 4 GB for the whole project, Feast's own key format in Redis,
  and its dependencies in the serving image.
- **(b) Feast as the feature registry and offline retrieval, our loader for Redis.**
  Rejected: it cannot build the training features without leakage, and a registry
  nobody reads from is a second definition that can drift.
- **(c) Keep our own store.** **Chosen.**

## Decision

Keep our own store: Polars computes the features, gold holds them, `store-load` fills
Redis, the scorer reads Redis. Feast stays in `featurestore/` as a pinned, tested,
reproducible **evaluation** — `just feast-trial`, `just feast-parity`, `just feast-test` —
outside every production path and outside the main lockfile.

## Consequences

- The plan no longer claims Feast. What we do have is the same shape: an offline store
  (gold, versioned, time-travel) and an online store (Redis) with **one** definition of
  each feature and parity tests between them (S5.6a), which is the problem a feature
  store exists to solve.
- The tie test pins Feast's current behaviour. A Feast upgrade that changes it fails
  that test and reopens this decision.
- **Revisit when:** Feast supports an ordering column in point-in-time joins; or Phase
  6's stream needs online writes from Kafka that Feast's push sources would do better;
  or the job outgrows one box (Phase 10, Spark offline store).
- The 3.96 GB peak ran uncapped once on 2026-11-18 (nothing was harmed); every Feast run
  is now capped at 4.5 GB by `just feast-trial`.
