# Streaming feature state: exact incremental account features with train/serve parity (Nov 2026)

Scope: how GraphGuard's Phase 6 stream consumer should keep the nine per-account
point-in-time features exactly equal to the batch (Polars) values, inside the memory
budget, and whether a stream-processing framework is worth it.

Method note. Web sources were fetched on 2026-11-21. Some numbers below were
**measured on this box** on 2026-11-21 against `data/raw/HI-Small_Trans.csv`, **train +
validation rows only** (timestamp < `val_end` 2022-09-08T16:09; the test window was not
read). Those are marked "measured (local)" and the script is described inline, so they
can be re-run. Redis memory figures are **estimates** from encoding rules, not
measurements: no throwaway Redis was started (starting a container needs Lubo's
approval).

---

## 1. Exact incremental updates in Redis (counters, money, distinct counts, 24h window, atomicity)

### Takeaway
Every feature can be kept exact in Redis, but two of the obvious tools break exactness:
`HINCRBYFLOAT` (it does not reproduce Polars' float64 sums) and HyperLogLog
(approximate). The memory-cheap exact design is: one small hash per account for counters
plus a watermark; **one global, sharded set of directed edges** (encoded as integers) whose
`SADD` result drives both `distinct_out[s]` and `distinct_in[r]`; a per-sender sorted set
(or minute buckets) for the 24h count, read with an exclusive `ZCOUNT`; and the whole
sender+receiver update in **one Lua script / Redis Function**, which Redis runs atomically.

### Cited Findings
**Counters and money**
- `HINCRBYFLOAT` behaves exactly like `INCRBYFLOAT`; it fails if the field or increment
  is not parsable as a double; it is replicated to replicas/AOF as an `HSET` "so that
  differences in the underlying floating point math implementation will not be sources of
  inconsistency" — [Redis HINCRBYFLOAT](https://redis.io/docs/latest/commands/hincrbyfloat/)
- `INCRBYFLOAT`: "The precision of the output is fixed at 17 digits after the decimal point
  regardless of the actual internal precision of the computation"; trailing zeros removed;
  the value is stored as a decimal string, not as a binary double —
  [Redis INCRBYFLOAT](https://redis.io/docs/latest/commands/incrbyfloat/)
- Measured (local): **Polars 1.43.2 `cum_sum()` on float64 is bit-identical to Python's
  sequential `itertools.accumulate`** (0 mismatches over all 5,078,345 amounts, also equal
  to `numpy.cumsum`), but **Polars `sum()` is not sequential**: over all amounts `sum()` =
  22,899,645,860,702.707 (equal to `math.fsum`, i.e. compensated/pairwise), while the
  sequential sum = 22,899,645,860,698.848. (Also: Python 3.12's built-in `sum()` of floats
  is compensated, so it is not a valid "sequential" reference either.) — measured on this
  box, no external source.
- Measured (local): `Amount Paid` has **up to 6 decimal places**; max single amount
  1,046,302,363,293.48; max per-account total sent 1.506e12, received 1.486e12 (all rows).
  In integer micro-units (×10^6) the largest per-account total is 1.51e18, under int64's
  9.22e18 (about 6x headroom on this dataset). — measured, no external source.
- How the code defines the features today (read from the repo): batch training features
  in `src/graphguard/features/graph.py` use `cum_sum().over(account) - amount_paid` for
  `amount_sent_before`/`amount_received_before`; the snapshot that seeds the store
  (`account_states_frame` in `src/graphguard/serving/online_features.py`) uses
  `pl.col("amount_paid").sum()`. — repo files.

**Distinct counts**
- Small sets are encoded compactly: sets of integers as **intset** up to
  `set-max-intset-entries 512`; since Redis 7.2 small non-integer sets as **listpack** up to
  `set-max-listpack-entries 128` / `set-max-listpack-value 64`; sorted sets as listpack up
  to `zset-max-listpack-entries 128` / `zset-max-listpack-value 64`; hashes up to
  `hash-max-listpack-entries 512` / `-value 64`. Special encodings use "up to 10 times less
  memory (with 5 times less memory used being the average saving)"; overflowing converts
  to the normal encoding automatically — [Redis memory optimization](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/)
- Same page: the "bucketed hash" trick (split a numeric id into key + field so each hash
  holds ~100 fields) took 100k small values from 11 MB (plain keys) to 1.7 MB (Redis 2.2
  measurement, old) — [Redis memory optimization](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/)
- HyperLogLog is approximate (Redis documents a standard error of 0.81%, max ~12 KB per
  key; not re-fetched this session) — [Redis HyperLogLog](https://redis.io/docs/latest/develop/data-types/probabilistic/hyperloglogs/)
- Measured (local, train+val): **975,372 distinct directed (sender, receiver) pairs**
  (not 5M: the 4.06M train+val transactions repeat pairs a lot); 513,896 accounts.
  `distinct_out`: 494,881 senders, median 1, p99 9, p99.9 15, max 14,230; **only 15
  senders exceed 128, and those 15 also exceed 512** (38,254 members between them).
  `distinct_in`: 420,146 receivers, median 2, p99 7, p99.9 30, max 545; 2 exceed 128, 1
  exceeds 512. — measured, no external source.
- Batch definition (repo): a counterparty is "new" when `cum_count().over([from, to]) == 1`;
  `distinct_out_before = cumsum(is_new) - is_new`. Self-transfers (from == to, e.g.
  "Reinvestment") count as a counterparty like any other. — `features/graph.py`.

**Sliding 24h count**
- Batch definition (repo): `sent_last_24h = n_sent_before - cum_sent as-of (t - 24h)`,
  via a backward as-of join on timestamp. So sends **at exactly t-24h are excluded** and
  same-minute sends with a smaller `source_row` are included. The snapshot code instead
  uses `timestamp >= window_start` (inclusive) — the two boundaries differ.
  — `features/graph.py` lines ~84-115, `serving/online_features.py` ~110-119.
- Measured (local): at `train_end` there are **481,840 sends in the trailing 24h, spread
  over 105,326 senders**, max 18,790 for one sender; over train+val the most sends any
  sender made in any 24h is 26,368, p99 19; 15 senders ever exceed 128. — measured.

**Atomicity**
- "Redis guarantees the script's atomic execution. While executing the script, all server
  activities are blocked during its entire runtime." Scripts "can perform conditional
  updates across multiple keys"; all keys must be passed in `KEYS` (never computed inside
  the script); since 7.0 replication of scripts is effects-only (wrapped in MULTI/EXEC);
  scripts are cached volatilely by SHA (`NOSCRIPT` after restart), and Redis Functions
  (7.0+) are the persisted, named alternative — [Redis Lua scripting intro](https://redis.io/docs/latest/develop/programmability/eval-intro/)
- Same page: if `maxmemory` is reached, the first memory-using write in a script aborts the
  script (unless `pcall`), but if the first write does not need memory the script runs to
  completion and can exceed `maxmemory` — so a mid-script OOM can leave a partial update
  unless the script is designed for it — [Redis Lua scripting intro](https://redis.io/docs/latest/develop/programmability/eval-intro/)

### Inferences
- **Do not use `HINCRBYFLOAT` for amounts.** Its result is a 17-decimal string from a
  long-double computation, not the float64 value Polars produces, so equality with batch is
  not guaranteed. Two exact options:
  1. **Integer micro-units everywhere (recommended).** Parse the amount string straight to
     an integer of micro-units (Polars `Decimal(38,6)` or string split — *not*
     `float * 1e6`, because 1e12 with 6 decimals needs ~19 significant digits and float64
     has ~15.9), sum with `HINCRBY` online and integer `cum_sum` in batch. Exact by
     construction, order-independent, and it removes the snapshot `sum()` vs `cum_sum()`
     trap. Convert to float only when building the model row. Caveat: int64 headroom is
     ~6x here; Phase 10 (180M rows) should re-check, since `HINCRBY` is int64-only.
  2. **Replicate float64 exactly in Python.** Read the stored running sum, compute
     `new = old + a` in Python float64, `HSET` `repr(new)` (round-trips exactly), and compute
     the "before" feature as `(old + a) - a` to match batch's `cum_sum - amount` (which is
     *not* always bit-equal to `old`). Works only if the seed is the sequential `cum_sum`
     value per account, not Polars `sum()`.
- **Current snapshot seeding is a parity trap.** `account_states_frame` seeds
  `amount_sent`/`amount_received` with `sum()`, which is not the sequential value the
  training features see; and its `sent_last_24h` uses an inclusive boundary where training
  is exclusive. Both are small in magnitude but break "exact" — the parity test (section 4)
  would catch them. Also a single seeded `sent_last_24h` count cannot be rolled forward;
  the snapshot must carry the actual last-24h send timestamps (481,840 entries) or minute
  buckets.
- **Distinct counts: one global edge set, not two per-account sets.** A directed edge
  (s, r) is new for s's out-set exactly when it is new for r's in-set, so one membership
  test serves both counters: `if SADD edge == 1 then HINCRBY s distinct_out 1; HINCRBY r
  distinct_in 1`. Encode the edge as an integer `s_id * 2^20 + r_id` (ids < 2^20 = 1,048,576
  covers 515k accounts with room) and shard by `edge % 16384` into keys `E:{n}` so each
  holds ~60-75 members → every shard stays an **intset** (8 bytes per int64 member).
  Estimate: ~1.0-1.2M edges × 8 B ≈ 8-10 MB + 16,384 keys of overhead ≈ 1-2 MB → **~10-12
  MB total**, versus roughly 90+ MB for ~915k per-account sets of 12-character string
  account ids (each top-level key costs tens of bytes of overhead before any members).
  Both are estimates; verify with `MEMORY USAGE` / `INFO memory` on a test db.
- Integer account ids need a dense id map. Best: assign `account_id` in the gold snapshot
  (deterministically, e.g. by first appearance in (timestamp, source_row) order) and give
  new stream accounts the next id via `INCR` inside the script. A 64-bit hash of the pair
  instead of ids would be "almost" exact (collision chance ~1e-8 at 1M edges) — fine
  operationally, but it is not proof, so ids are the cleaner story.
- **HyperLogLog is ruled out**: 0.81% error breaks row-level parity, and at a median of
  1-2 counterparties exact sets are tiny anyway.
- **24h count, two exact options.** (a) Per-sender sorted set, member = `source_row`, score =
  epoch minute; count with `ZCOUNT key (cutoff +inf` (the `(` makes the lower bound
  exclusive, matching batch), and trim with `ZREMRANGEBYSCORE key -inf cutoff` on each send
  to bound memory. Correctness comes from the exclusive `ZCOUNT`, not from trimming, so
  stale keys of idle accounts are only a memory question. Estimate ~105k keys, ~480k
  entries mostly in listpack, plus ~15 hub skiplists → roughly 20-30 MB. (b) **Minute
  buckets are exact here**, because timestamps have minute resolution: a hash
  `minute → count` per sender holds at most 1,440 fields, so the 18,790-send hub collapses
  to ≤1,440 entries. (b) is smaller for hubs; (a) is simpler to reason about.
- **One script per transaction**: `KEYS = [acct:s, acct:r, E:{shard}, win:s]`, `ARGV = [ts,
  source_row, amount_micro, s_id, r_id]`. It reads the before-state of both accounts, checks
  the watermarks, applies all updates, and returns the before-state. Load it as a Redis
  Function (persisted across restart) rather than `EVALSHA`. Keep a `maxmemory` headroom
  well above working size so a script never hits OOM half way.
- Total estimated new memory ≈ 10-12 MB (edges) + 20-30 MB (window) + the existing
  per-account hashes; plausibly within the current 200 MB cap, but the present store's
  usage was not checked here.

### Gaps
- No measured Redis memory for these structures (needs a throwaway Redis 7.4 — container
  start requires approval). Per-key overhead figures above are rule-of-thumb estimates.
- Current `used_memory` of GraphGuard's Redis was not read (ACL'd live store).
- The validation window will add new edges beyond the 975,372 counted up to `val_end`;
  that count already includes validation, so it is an upper bound for the replay.

---

## 2. Score-then-update ordering, idempotency, late and out-of-order events

### Takeaway
"Features before the event" falls out naturally if the Lua script returns the
pre-update state and applies the update in the same atomic call. Exactly-once *effect* on
Redis comes from a per-account watermark `(timestamp, source_row)`: an event is applied to
an account only if it is strictly after that account's watermark. Exactness also needs
**total order**: consume the replay from one partition (or a key-ordered design that keeps
both sender- and receiver-side order), because tied minutes are broken by `source_row`.

### Cited Findings
- Batch semantics: every "before" feature is computed over history ordered by
  `(timestamp, source_row)`; 9.4% of transactions tie on the minute (FINDING-010, project
  `CLAUDE.md`). Same-minute earlier rows count as "before". — repo/CLAUDE.md.
- Redis scripts are atomic and block the server while running, so a read-then-write inside
  one script cannot be interleaved — [Redis Lua scripting intro](https://redis.io/docs/latest/develop/programmability/eval-intro/)
- Quix Streams exactly-once: messages "do not fully commit or produce until the checkpoint
  successfully completes"; exactly-once costs "at worst 10% slower" (not guaranteed); its
  guarantee covers Kafka output and its own RocksDB state, and "if an error callback ignores
  an exception, the offset is still committed" (message skipped) —
  [Quix Streams configuration](https://quix.io/docs/quix-streams/configuration.html)
- Tecton 1.0 changed the aggregation "leading edge" default from the stream's latest event
  time to the request's wall-clock time and warns this can change served values — an
  example of how window boundaries silently create skew —
  [Tecton AggregationLeadingEdge](https://tecton-docs.pages.dev/docs/sdk-reference/feature-views/configuration/read-features/AggregationLeadingEdge)

### Inferences
- **Watermark idempotency is exact here because order is total.** Store `wm` =
  `(ts, source_row)` in each account hash. In the script: sender side applies only if
  `(ts,row) > wm_s`, receiver side only if `(ts,row) > wm_r` (separately — a self-transfer
  touches one hash, handle `s == r` explicitly). The edge `SADD` is naturally idempotent
  (duplicate add returns 0), and the window `ZADD` keyed by `source_row` is idempotent too.
  No unbounded "applied events" set is needed. A duplicate delivery returns
  `status=duplicate`.
- **Kafka exactly-once does not reach Redis or Postgres.** Kafka transactions cover
  consume→produce→offset within Kafka; side effects in external stores need their own
  idempotency (watermark in Redis, primary key in Postgres). So "at-least-once Kafka +
  idempotent sinks" is the correct, simpler design for this consumer (inference; consistent
  with the Quix caveats above).
- **Crash window.** If the consumer dies after the Redis script but before the decision is
  in Postgres, the replayed event is now a "duplicate" and its before-features are gone.
  Fix: the script also writes `pending:{source_row}` = the returned before-state (same
  atomic call); the consumer deletes it after the Postgres commit. On replay of a duplicate,
  the consumer scores from `pending:*` (or skips if the decision row already exists).
- **Pipelining keeps exactness.** Scores never feed back into state, so the consumer can
  pipeline a batch of `FCALL`s in order; Redis executes them in order and each returns its
  own before-state. Score the batch afterwards with XGBoost in process (FINDING-013 says the
  Phase 6 consumer should score in process). 1M events at tens of microseconds per script is
  on the order of a minute or two of Redis CPU (inference; not measured).
- **Partitioning.** If the topic is partitioned by sender, receiver-side updates for one
  account arrive from many partitions with no relative order, and same-minute ties can be
  applied in a different order than batch → `distinct_in` and amounts-before may differ.
  For a 1M-event replay, **one partition** is the honest choice; document it as the scaling
  limit (the scale-out answer is a second stage re-keyed by receiver, Kafka Streams style).
- **Late / out-of-order events** (event with `(ts,row)` behind an account's watermark):
  - Cumulative features: the event cannot be inserted "in the past" without changing values
    already served for later events, so exact parity with a batch recompute is impossible
    for those scores. Policy options: reject to a dead-letter topic with a counter; or apply
    it (counts become correct going forward) and flag the decision as `late`. Batch must use
    the same policy or parity tests must exclude those rows.
  - Windowed `sent_last_24h`: a sorted set by timestamp accepts a late insert correctly for
    future reads; only already-served values are affected.
  - In the replay from the lakehouse the source is ordered, so late events should be zero;
    assert that (a counter that must stay 0).

### Gaps
- No primary source fetched on Kafka transactional semantics vs external sinks in this
  session (the statement above is standard Kafka behaviour, labelled as inference).
- No measurement of Lua/Function throughput on this box.

---

## 3. Memory sizing and bounding

### Takeaway
At this scale the exact state is small: ~1M directed edges, ~480k live 24h timestamps,
~515k account hashes. With integer ids and sharded intsets, distinct-count state is ~10 MB;
the window ~20-30 MB; hubs (15 accounts) are the only large structures and are bounded by
trimming or by minute buckets.

### Cited Findings
- Encoding thresholds and the 5-10x saving of compact encodings —
  [Redis memory optimization](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/)
- Redis does not always return freed memory to the OS; provision for **peak**; set
  `maxmemory-policy noeviction` so writes fail loudly instead of evicting state —
  [Redis memory optimization](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/)
- Measured (local): 975,372 directed pairs; 494,881 senders / 420,146 receivers; 15
  senders > 512 counterparties (38,254 members); 481,840 trailing-24h sends at
  `train_end`; max 26,368 sends by one sender in any 24h — measured.

### Inferences
- **`noeviction` is mandatory** for a state store: an evicted counter silently resets a
  feature to 0 — the exact failure the 83% PR-AUC finding is about.
- Bounding: trim window entries older than 24h on every send; a periodic sweep (or lazy trim
  on read) handles idle accounts. Edge state cannot be bounded without losing exactness
  (distinct is cumulative), but it grows with *new pairs*, not transactions (4.06M rows →
  0.98M pairs).
- Keep the 15 hub sets as plain hashtables — fine; do not raise `set-max-intset-entries` to
  15k to force intset on hubs (O(n) inserts; the docs advise benchmarking conversions).
- Alternative worth one sentence in an ADR: keep all state in the consumer's Python memory
  (dicts + a set of 1M ints ≈ 60-100 MB) and write only serving values to Redis. Faster, but
  recovery means replaying from the snapshot, and two copies of state can drift. Redis as the
  single source of truth is simpler to make idempotent.

### Gaps
- Real `MEMORY USAGE` numbers for each structure (needs a test Redis).

---

## 4. Frameworks in Nov 2026 vs a plain Python consumer

### Takeaway
For one box, ~1 GB, Python, 1M events and state that the HTTP scorer must also read from
Redis, a **plain Python consumer (confluent-kafka) + Redis Functions** is the defensible
senior choice. The JVM/Rust/SQL engines do not fit the memory budget; the Python
frameworks either keep state in their own RocksDB (duplicating Redis) or are poorly
maintained. Quix Streams is the one Python framework worth naming as the considered
alternative.

### Cited Findings
- **Apache Flink**: shipped `config.yaml` defaults are `jobmanager.memory.process.size:
  1600m` and `taskmanager.memory.process.size: 1728m` (≈3.3 GB before any Python worker) —
  [Flink default config.yaml](https://raw.githubusercontent.com/apache/flink/master/flink-dist/src/main/resources/config.yaml).
  Derived memory components must stay within min/max bounds or startup fails —
  [Flink memory setup](https://ci.apache.org/projects/flink/flink-docs-master/docs/deployment/memory/mem_setup/).
  PyPI `apache-flink` latest 2.3.0 (2026-06-21) — [PyPI](https://pypi.org/project/apache-flink/).
  No authoritative PyFlink memory floor found.
- **Quix Streams**: latest 3.28.1 (2026-10-15) — [PyPI](https://pypi.org/project/quixstreams/).
  Pure Python, state in local RocksDB backed by Kafka changelog topics
  (`use_changelog_topics` default True), `processing_guarantee` at-least-once (default) or
  exactly-once (≤~10% slower), state recovery automatic, local state deleted if the
  committed offset is no longer retained — [Quix configuration](https://quix.io/docs/quix-streams/configuration.html).
  3.20.0 added transaction control and Postgres conflict resolution —
  [Quix 3.20.0 release](https://quix.io/blog/quix-streams-release-3-20-0)
- **Bytewax**: "Bytewax is now community-maintained … As of May 2025, Bytewax (the company)
  is no longer commercially viable" — [bytewax GitHub](https://github.com/bytewax/bytewax).
  Last PyPI release 0.21.1 on 2024-11-25 — [PyPI](https://pypi.org/project/bytewax/)
- **Faust (faust-streaming fork)**: PyPI 0.15.4 released 2026-10-28 —
  [PyPI](https://pypi.org/project/faust-streaming/); this contradicts Snyk's undated
  "Inactive" rating — [Snyk](https://security.snyk.io/package/pip/faust-streaming)
- **Arroyo**: acquired by Cloudflare on 2025-04-10 to power Cloudflare Pipelines —
  [Cloudflare blog](https://blog.cloudflare.com/cloudflare-acquires-arroyo-pipelines-streaming-ingestion-beta);
  it was said to remain open source and self-hostable (third-party summary, unverified).
- **RisingWave**: compute node minimum 2 cores / 8 GiB, 16 GiB recommended —
  [RisingWave hardware requirements](https://docs.risingwave.com/deploy/hardware-requirements);
  streaming node "recommended minimum memory … 8 GB" —
  [RisingWave OOM troubleshooting](https://docs.risingwave.com/troubleshoot/troubleshoot-oom)
- **Apache Beam**: Python SDK 2.78.0 (2026-11-17) — [PyPI](https://pypi.org/project/apache-beam/);
  stateful streaming needs a runner (Flink/Spark/Dataflow) — inference from Beam's model.
- **Kafka Streams**: JVM library (Kafka 4.x upgrade guides current) —
  [Kafka Streams upgrade guide](https://kafka.apache.org/43/streams/upgrade-guide/)

### Inferences
- **Flink** (≈3.3 GB defaults, plus a Python worker for PyFlink) and **RisingWave** (8 GiB
  minimum) do not fit a ~1 GB stream budget on a box whose swap is ~99% full. Materialize is
  in the same class (not checked this session).
- **Quix Streams** fits memory, but its state lives in RocksDB on the consumer, while the
  Ray Serve scorer on k3s reads features from Redis. Using it means either two state copies
  (RocksDB + Redis write-through) or bypassing its state API — and its exactly-once does not
  cover Redis/Postgres writes. It adds a dependency without removing the hard parts
  (ordering, tie-breaks, idempotent sinks).
- **Bytewax** (no release in 2 years, company gone) should not be picked for new work.
  Faust is alive again but has a history of stalls.
- **Hiring signal (opinion, no source found):** Flink is the name most JD's list for
  streaming; the stronger interview story is "I measured that Flink's defaults alone exceed
  my whole budget, wrote ~300 lines of consumer whose exactness is proven row-by-row, and
  know where it stops scaling (single partition; re-key by receiver)". An ADR stating this,
  with the numbers above, is the senior move. A small optional PyFlink/Quix spike is
  portfolio garnish, not a requirement.

### Gaps
- No hard source on hiring-manager expectations for Flink in 2026.
- No measured RAM for Quix Streams or faust on this workload.
- Materialize self-hosted memory not checked.

---

## 5. Train/serve parity testing and how feature platforms describe it

### Takeaway
The test that matters is **row-by-row equality**: replay the validation events through the
online updater starting from the `train_end` snapshot and assert every feature of every row
equals the batch value from `features/graph.py` (ints exactly; amounts exactly if integer
micro-units, bit-exact if the float path is replicated). Commercial platforms get parity
by one definition compiled to both paths plus tiled aggregates; they rarely promise exact
cumulative distinct counts.

### Cited Findings
- **Tecton**: older events are compacted into tiles, the newest aggregated on demand at
  request time; partial tiles are excluded so online and offline see "an exact number of
  tiles"; same transformation for batch and stream; point-in-time correct backfills; and
  the 1.0 leading-edge change can alter served values —
  [Tecton/Airbnb real-time aggregation, part 1](https://towardsdatascience.com/real-time-aggregation-features-for-machine-learning-part-1-ec7337c0a504),
  [part 2](https://towardsdatascience.com/real-time-aggregation-features-for-machine-learning-part-2-fe9fd42522c0/),
  [Tecton leading edge](https://tecton-docs.pages.dev/docs/sdk-reference/feature-views/configuration/read-features/AggregationLeadingEdge)
- **Feast tiling**: hop-sized tiles (default 5 minutes), cumulative tail aggregations minus
  tiles; supports sum/avg/mean/min/max/count/std via intermediate representations ("IRs
  ensure mathematically accurate merging"); Spark and Ray engines only, the Local engine
  "Does NOT support time-windowed aggregations"; no statement on train/serve consistency
  and no distinct count — [Feast tiling](https://docs.feast.dev/getting-started/concepts/tiling)
- **Chalk**: materialized windowed aggregations update from streams; partial aggregates are
  stored per time bucket and merged at query time; training sets are built by merging tiles
  covering each spine row's window — [Chalk materialized aggregations](https://docs.chalk.ai/docs/materialized_aggregations),
  [Chalk training sets](https://docs.chalk.ai/docs/training-sets-materialized-aggregations)
- **Databricks feature views**: one definition for training and online; streaming features
  not materialized offline — [Databricks fraud feature views](https://www.databricks.com/blog/real-time-fraud-detection-feature-views)
- Project history: Feast 0.68 was measured here and could not build the training features
  without leakage on same-minute ties (ADR 0004, project `CLAUDE.md`).

### Inferences
- Bucket/tile approaches give "exact up to tile boundaries" — fine for ad-click windows,
  not for this project's cumulative-since-forever counts with minute ties. Our own
  definition (per-event state + `(ts, source_row)` order) is stricter than these platforms
  advertise, which is a point worth stating in the write-up.
- Recommended test set (all CI-runnable with a test Redis db or fakeredis):
  1. **Full replay parity**: snapshot at `train_end` → replay all ~1M validation events →
     per row, compare the 9 features (+ the in/out ratio) with `graph.py` output for the
     same `source_row`. Report mismatches by feature; zero required. Aggregate agreement
     (means, totals) is explicitly not enough.
  2. **Duplicate delivery**: replay every event twice (and random re-deliveries) → identical
     result.
  3. **Crash/restart**: kill after a random script call before the Postgres write → resume →
     identical features and exactly one decision per event.
  4. **Tie test**: hand-built events at the same minute with shuffled arrival must be
     rejected or ordered by `source_row`, and match batch.
  5. **Boundary test**: sends exactly 24h earlier are excluded, as in batch.
  6. A fast CI version on a sampled slice (e.g. the hub account + 10k random accounts'
     full histories), with the full 1M replay as a `slow` test.
- The in/out ratio mixes accounts: `(receiver.n_received + 1) / (sender.n_sent + 1)`
  (repo) — compute it in Python from the two returned before-states with the same float
  division; it then matches bit for bit.

### Gaps
- Fennel and Hopsworks docs, and Uber/DoorDash/Stripe/Airbnb posts, were not fetched this
  session (budget). Uber Palette and Airbnb Chronon describe the same "one definition,
  two engines" idea, but no primary quote was collected here.

---

## 6. Persisting decisions to Postgres from the stream

### Takeaway
Key decisions by the event id (`source_row`), insert in batches with
`ON CONFLICT (event_id) DO NOTHING`, deduplicate inside each batch first, store the exact
feature vector, model version/hash and feature-definition version with each decision, and
commit Kafka offsets only after the Postgres commit. An outbox table in the same
transaction is the clean way to emit alerts.

### Cited Findings
- PostgreSQL 19 is current (released 2026-11-19). `ON CONFLICT DO UPDATE` "guarantees an
  atomic INSERT or UPDATE outcome … even under high concurrency"; new `ON CONFLICT DO
  SELECT` gives an atomic insert-or-select; a statement may not affect the same row twice
  ("cardinality violation"), so proposed rows "should not duplicate each other"; `DO
  NOTHING` may omit the conflict target, `DO UPDATE`/`DO SELECT` require it; `RETURNING`
  returns only rows inserted, updated or selected —
  [PostgreSQL 19 INSERT](https://www.postgresql.org/docs/current/sql-insert.html)

### Inferences
- Table sketch: `decisions(event_id bigint primary key, scored_at timestamptz,
  event_ts timestamp, sender_id, receiver_id, score real, decision text, cold_policy text,
  model_version text, model_sha256 text, feature_def_version text, features jsonb (or 10
  typed columns), late boolean default false)`. Typed columns are better for audit queries
  and parity checks; `jsonb` is more flexible. Optionally `outbox(id bigserial, event_id,
  topic, payload jsonb, created_at, sent_at)` written in the same transaction, drained to
  Kafka by a relay — so an alert is never sent without its decision, or vice versa.
- `DO NOTHING` (not `DO UPDATE`) for decisions: the first decision for an event is the audit
  record; a replay must not overwrite it. With PG 19, `DO SELECT ... RETURNING` lets the
  consumer read back the stored decision on a duplicate in one round trip.
- Batch 500-5,000 rows per transaction (multi-row `INSERT` / `executemany` with
  psycopg 3 pipeline, or `COPY` into a temp table + `INSERT ... SELECT ... ON CONFLICT DO
  NOTHING`). Order per batch: Redis scripts → score → Postgres commit → delete
  `pending:*` → commit Kafka offset. Every step is idempotent, so a crash anywhere is safe.
- Give Postgres its own role/database per the project's `pg_access.SERVICES` (a new DB is
  then backed up automatically per CLAUDE.md).

### Gaps
- No throughput measurement of batched upserts on this box.
- psycopg 3 pipeline/COPY docs not fetched this session.
