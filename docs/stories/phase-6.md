# Phase 6 — The stream: stories

**Status:** approved by Lubo 2026-11-21 with D1-D4 as recommended (SES, keep the model, consumer on k3s, SCRAM without TLS). S6.1-S6.8 done; S6.9 next. Research behind it:
`docs/research/Kafka streaming fraud pipeline 2026.md` (four tracks, notes beside it).

**How stories are expanded:** one at a time, just before work starts on it. The next story
(S6.1) has the full treatment; the rest stay short until their turn.

## Main goal

A **replayed transaction stream that behaves like a real one**: events arrive one by one in
true order, late, twice, in bursts, sometimes broken; the consumer keeps every account's
features **exactly** equal to training, scores each event with the model and with rules,
and writes each decision once — whatever crashes in between. Labels arrive late, as they
do in a bank. It runs overnight unattended.

The data stays synthetic (IBM AMLworld). We imitate the **arrival**, not the data. The
stream replays **only the validation window** (`train_end` → `val_end`, ~1.0M
transactions, ~50 hours of event time). The test window stays sealed.

**Epic / Definition of Done** (PLAN.md, Phase 6): transactions flowing continuously,
decisions landing in Postgres, rules and model both scoring, and the system surviving
being left running overnight.

**What the research changed** (vs PLAN.md's sketch):
1. **The hardest part is not Kafka, it is exact live features.** FINDING-008: stale
   features cost 83% of PR-AUC, so the consumer must update both accounts after every
   event. And the online snapshot already disagrees with training in two small places
   (money totals summed differently; a send exactly 24 h ago counted on one side only).
   Those get fixed and **proven offline before any broker exists**.
2. **Kafka's "exactly-once" does not reach Redis or Postgres.** We get effectively-once
   from at-least-once delivery plus writes that ignore repeats (event id in Postgres, a
   per-account watermark in Redis).
3. **Plain Python consumer, not Flink.** Flink's shipped defaults alone ask ~3.3 GB — our
   whole budget. Written down in an ADR with the numbers.
4. **Realism = properties, not tools:** same decisions at any replay speed, seeded faults
   that change nothing, late labels, a rules baseline, shadow scoring.
5. **Kafka 4.4.0** (Oct 2026; 4.2.2+ carry the 2026 security fixes), official JVM image —
   not the "native" image, which Apache marks experimental.

**Rules that apply to every story:** nothing named `lubot-*`, `forgejo`, `sentinel-*` or
`aws-job-streamer` is touched. Never `k3s-killall.sh`. Approving a story covers the
containers and AWS resources it lists, nothing else. Every container: memory cap, no
capabilities, no-new-privileges, digest, localhost/k3s-bridge ports only
(`test_compose_hardening.py`). Box-wide changes go to the LuBot session first. New secrets
get a registry entry. No heavy lakehouse job or training during a replay (4 GB budget).

### Decisions for Lubo (with my recommendation)

| # | Question | Recommendation |
|---|---|---|
| D1 | How the scorer alert sends email | **AWS SES** in our AWS account: a new IAM user `graphguard-alerts` allowed only `ses:SendEmail` from one verified address. No personal mail password on the box. (Alternative: a Gmail app password.) |
| D2 | Money-total fix | **Keep the current model:** the online path repeats training's exact float arithmetic. (Alternative: integer micro-units everywhere — cleaner, but changes training features in the last digits and needs a retrain and a new model version.) |
| D3 | Where the consumer runs | **k3s Deployment** in the restricted `graphguard` namespace, next to the scorer (same pod rules, own NetworkPolicy). |
| D4 | Kafka logins | **SCRAM logins + deny-by-default ACLs**, one login per program, without TLS (listeners reach only the host and the k3s bridge). TLS with a private CA written as the stronger option in the ADR. |

### Memory plan (caps to start; each replaced by a measured peak)

| New piece | Cap |
|---|---|
| Kafka broker (heap ~256-384 MB) | 768 MB |
| Consumer (k3s) | ~512 MB |
| Replayer (host job, runs during a replay only) | ~384 MB |
| Shadow consumer (only during S6.10 comparisons) | ~400 MB |
| Lag exporter | ~64 MB |
| Extra Redis state (edges, 24 h windows) | +30-45 MB inside Redis |

About 1.3-1.6 GB, ~2 GB with the shadow consumer. Fits beside today's ~0.5 GB of services
plus k3s, if no lakehouse job or training runs at the same time.

---

## S6.1 — The scorer alert: an email when it breaks, and when it heals ✅ done 2026-11-21

**As** Lubo, **I want** an email when the scorer goes down and another when it comes back,
**so that** an outage reaches me before the stream starts depending on the scorer (it sat
broken for 18 days once and nobody noticed — S5.2).

Acceptance criteria (Given/When/Then):
- [x] **Given** the scorer is healthy, **when** the check runs, **then** no email is sent
      and the state file says `healthy`.
- [x] **Given** the last state was `healthy`, **when** a check finds a problem (`just
      k8s-check` fails, or `/health` answers 503 "unavailable"/"not loaded", or no
      answer), **then** exactly one email is sent: what broke, since when, the first
      command to run, a link to the runbook.
- [x] **Given** it is still broken, **when** the next checks run, **then** no new email —
      except one reminder per 24 h while broken.
- [x] **Given** it was broken, **when** a check passes, **then** one "recovered" email with
      how long it was down.
- [x] **Flapping guard:** a state changes only after 2 checks in a row agree (no email for
      a 1-minute blip, e.g. during a rolling upgrade).
- [x] **If the email itself fails**, the failure is logged and the check retries next run;
      `just alert-status` shows the last check, the state and the last email sent (and
      exits 1 when the check is stale or mail failed), next to the other health checks.
- [x] **The judgement is pure and unit-tested** (state machine: healthy/broken/flapping/
      reminder/recovery, all with a fake clock and a fake mailer). Only `main` talks to
      k3s, HTTP and SES.
- [x] **Live drill without breaking anything:** `just alert-drill` runs the real path with
      a forced-failure flag (never touches the scorer) and sends one real "drill" email
      and one "recovered" email. Lubo confirms both arrived.
- [x] **Least privilege:** the SES key can send only from the one verified address
      (`ses:FromAddress` condition) and nothing else — a live test proves another action
      is denied. Key in `.secrets/alerts-aws.env` (registry entry), Lubo's address in
      `.secrets/` too, **never in the repo**. The unit runs sandboxed (like the edge check),
      key handed in with `LoadCredential`.
- [x] Runbook `docs/runbooks/scorer-down.md`: what each email means, first commands, how to
      silence it during planned work (`just alert-pause 2h`).

**Done 2026-11-21.** 24 unit tests (state machine with a fake clock, messages, SES call shape,
sandboxed unit) + 4 live AWS denials (other sender, other recipient, reading SES settings,
S3). Drill: both emails accepted by SES. Timer active; the check runs sandboxed and sees
only its two credentials (`.secrets/` hidden, verified). `just health` added. The existing
S5.2 runbook was extended (section 0), not replaced. Key pasted in chat by Lubo's choice
(accepted risk, private record).

Definition of Done: timer installed and active (every 5 min), drill emails received, unit
tests + `just check` green, CI green, LuBot sites 200 before/after, CLAUDE.md and PLAN.md
updated.

Tasks:
1. Tests first: state machine (`src/graphguard/ops/alert.py`, pure), message text, SES
   call shape (fake client).
2. `main`: run `k8s_health` + `/health` probe, load state from `private/alerts/state.json`,
   decide, send, save.
3. AWS (Lubo in the console, I give the steps): verify one sender/recipient address in SES
   (sandbox is fine — we only email Lubo), create user `graphguard-alerts` + policy.
   Lubo enters the key with `just secret-set alerts-aws.env` (or pastes it, accepted risk).
4. systemd `graphguard-alert.service/.timer`, `just alert-install | alert-status |
   alert-drill | alert-pause`.
5. Runbook, docs, drill.

Estimate: one session. Depends on: nothing. Phase 8 monitoring replaces it later.

Out of scope: paging/SMS, Slack, alerting on Kafka/consumer (S6.11 extends this same
alert to the stream), dashboards.

Risks: SES sandbox limits (200/day — far above our need); mail landing in spam (drill
checks it; Lubo marks "not spam" once); the check itself dying silently → `alert-status`
in the health checks catches a stale check.

New AWS resources this story creates (covered by approval): one SES verified identity, one
IAM user + one policy. No new container.

---

## S6.2 — Training is the truth: the online snapshot matches it exactly ✅ done 2026-11-21

**As** the person defending the numbers, **I want** the snapshot that seeds the stream to
equal training's features bit for bit, **so that** the stream starts from what the model
learned on.

**Measured first (2026-11-21, train + validation only):**
- Training's tie order is the source order (= `source_row`): `sort("timestamp")` gave the
  stable result in 6/6 runs — but Polars does not promise it (`maintain_order=False`).
- Training's 24 h window is **exclusive** at t−24h: 0 mismatches in 356,771 sends of 300
  senders (incl. the 20 biggest hubs); the snapshot's inclusive `>=` would miss 246,508.
- Training's "amount before" is exactly `(S + a) − a` (S = sequential running total):
  0 mismatches on the biggest hub's 132,535 sends; plain `S` differs 8 times (last digit).

Acceptance criteria (Given/When/Then):
- [x] **Tie order is explicit:** every history sort says `maintain_order=True` (source order
      = `source_row`). Given rows whose source order disagrees with time and ties within a
      minute, the features follow (timestamp, source order) — unit test with enough rows
      to force a parallel sort.
- [x] **Model untouched:** the training features before and after the change are identical
      on train + validation (frame equality), so `xgb-ab9ee07e6bd8` stays the model.
- [x] **Money:** the snapshot's totals are the sequential running total (`cum_sum`), and
      `to_model_row` computes "before" as `(S + a) − a`, exactly as training. Unit test
      with amounts where `sum()` and the sequential sum differ.
- [x] **24 h edge:** the snapshot counts sends in `(as_of − 24h, as_of)` — a send exactly
      24 h earlier is excluded. Unit test at the boundary.
- [x] **Recent send times** for the stream: `recent_sends_frame(as_of)` (one row per send
      in that window) and a gold table `gold.account_recent_sends` written by
      `just lakehouse-build`; count equals `sent_last_24h` per account.
- [x] **Validation-only stream source:** `validation_stream(catalog)` reads `silver` with
      `train_end <= timestamp < val_end` in `(timestamp, source_row)` order and asserts both
      bounds on the data it returns; it cannot name `sealed`. `test_set_touch_check` green.
- [x] **The proof (real data, `slow`):** for every account active in validation, the
      `train_end` snapshot gives exactly the training features of its first validation
      send / receive (counts, distinct, seconds since last send, `(S + a) − a`, and the 24 h
      count from the recent send times) — zero mismatches.
- [x] **Scorer unchanged:** 2,000 validation transactions score identically through the old
      and new `to_model_row` against the same store, or every difference is explained.

**Done 2026-11-21** (FINDING-015). Exact parity on a 30k-row adversarial history (unit) and on
every account active in validation (slow, real data: 0 mismatches; the old code fails with
79,003 / 117,585). Training features identical before/after on 4.06M rows → model unchanged.
1 of 2,000 scores moved by 8.7e-8, explained (the 24 h fix: 14 → 13, training says 13).
`gold.account_recent_sends` live (481,525 sends); Redis reloaded; old approx parity test made
exact. `MAINTAINED_TABLES` = tracked + recent sends (training lineage does not record the
stream's seed). Not done here: the live HTTP scorer still runs image 0.1.5 with the old
"before" arithmetic (last-digit only) — the next image (S6.6) carries it.

Definition of Done: unit + slow proof green, `just check` + `just ci-sandbox` green,
`just lakehouse-build` + `just store-load` re-run (gold and Redis refreshed), the live
scorer still healthy, LuBot sites 200, docs updated.

Out of scope: the live updater itself (S6.3), the edge set for distinct counts (S6.3),
rolling a new scorer image (only if the 2,000-score check finds a difference worth it).

## S6.3 — Live features, proven before Kafka exists ✅ done 2026-11-21

**As** the stream, **I want** every transaction to return both accounts' features *before*
it and then apply it, atomically, **so that** live features stay exactly equal to training
forever.

**Design decision (changes the research's suggestion):** no Redis Function / Lua. S5b.1
banned scripting on purpose (RediShell, CVE-2025-49844) and that stays. Instead: **one
writer** (one consumer, one partition), which reads the state it needs, computes a whole
micro-batch in Python (same float64 arithmetic as training), and writes it in **one
`MULTI/EXEC`** — all or nothing. A new Redis user `stream` gets only the plain commands it
uses. A lease that stops a second writer comes with the consumer (S6.6).

Redis layout (namespace `gg`): `acct:{a}` hash (today's fields + `wm`, the last applied
`(timestamp, source_row)`); `edge:{shard}` sets of `from→to` pairs (16,384 shards, compact
encoding) for distinct counts; `win:{a}` sorted set of the sender's sends in the last 24 h
(score = time), trimmed as time moves; `ev:{source_row}` the before-features of an applied
event (6 h TTL, deleted once the decision is stored) for crash recovery and repeats.

Acceptance criteria:
- [x] **The full proof:** start from the `train_end` seed (states, recent sends, edges),
      replay all ~1.0M validation events through the updater in micro-batches, compare
      every history feature of every row with training (`graph.py`) — **zero mismatches**.
      Runs on a throwaway capped Redis (offline, no published port besides loopback).
- [x] **Repeats change nothing:** an event delivered twice returns the same before-features
      and applies once (unit + live).
- [x] **Crash between Redis and Postgres:** the event comes back, Redis says "already
      applied" and hands back the stored before-features — same score.
- [x] **Late events are refused, not applied:** an event older than an account's watermark
      and not a known repeat → status `late`, state untouched (counted; S6.5 injects them).
- [x] **Same-minute ties and the 24 h edge** in unit tests (shuffled arrival inside a batch
      is re-ordered by `(timestamp, source_row)`; a send exactly 24 h earlier is out).
- [x] **Seed:** `gold.account_edges` (distinct pairs before `train_end`) written by
      `just lakehouse-build`; `just store-load` loads accounts + windows + edges and clears
      old `edge:`/`win:`/`ev:` keys; the scorer's view is unchanged.
- [x] **Least privilege:** Redis user `stream` — only `HGETALL HSET SMISMEMBER SADD ZCOUNT
      ZADD ZREMRANGEBYSCORE GET SET DEL MULTI EXEC PING` on `gg:acct:* gg:edge:* gg:win:*
      gg:ev:*`; still nobody has `EVAL`/`FUNCTION`; loader gains `SADD ZADD` on the new
      patterns. Live ACL tests prove it.
- [x] **Memory measured** (`INFO memory`, `MEMORY USAGE` samples) after seeding and after the
      full replay; Redis cap raised only if needed, with headroom kept (`noeviction` stays).
- [x] Speed measured: events/s through the updater (target ≫ 187/s, the busiest minute).

**Done 2026-11-21** (ADR 0005). Full validation replay: 1,015,300 events, **0 mismatches** on
every feature — memory store 9,734 ev/s, real Redis (throwaway copy) 6,038 ev/s (32× the
busiest minute). Redis 224 MB data / 303 MiB resident at peak → live Redis raised to 320mb
data / 448m cap (was 200mb / 256m), recreated twice with alert paused, reloaded in 22 s each
time. 14 unit tests (mutations caught: inclusive window, wrong edges, money off by 1e-9) + 3
live tests (Redis ≡ memory, repeats, acks) + live ACL tests for `stream`. Seed tables
`gold.account_edges` (936,359 pairs) + recent sends live; `store-load` now resets the
stream. The research's Lua design was replaced (scripting stays banned).

Definition of Done: proofs green, `just check` + `just ci-sandbox` green, live store reloaded
with the new seed, scorer healthy throughout, LuBot sites 200, ADR 0005 (no scripting;
single writer + MULTI/EXEC), docs updated.

Out of scope: Kafka (S6.4), the consumer loop and Postgres (S6.6), the writer lease (S6.6).

## S6.4 — Kafka on the box, hardened and measured ✅ done 2026-11-21

**As** an operator, **I want** one Kafka 4.4.0 broker that fits its cap and only talks to
our programs, **so that** the stream has a safe pipe.

- Official JVM image by digest, KRaft combined mode, every replication count 1, small
  segments; heap cut, cap 768 MB; Java runtime checked for the Nov 2026 JDK flaw.
- Listeners set explicitly (the image otherwise binds every interface): host loopback and
  the k3s bridge only; the controller listener never published. `just edge-baseline`
  after.
- SCRAM logins + deny-by-default ACLs (D4): replayer, consumer, shadow, admin, monitor.
  Secrets in the registry; the pod's login as a Kubernetes Secret.
- **Topics keep event time in the message, and retention uses arrival time** — otherwise
  Kafka would delete 2022-stamped records the moment they land.
- Peak memory measured under a 100× replay; passes `test_compose_hardening.py`.
- ADRs: Kafka config, and "plain consumer vs Flink / Quix Streams" with the numbers.
- How CI gets a broker (CI jobs cannot reach other containers) decided and written here.

New container (covered by approval): `graphguard-kafka`, and later `graphguard-kafka-exporter`.

**Done 2026-11-21** (ADR 0006). Kafka 4.4.0 (official image, digest), KRaft combined,
uid 10380, read-only, heap 384m / cap 768m. Measured: idle 332 MiB; 1,015,300 messages in at
~535k/s and read back in 10 s, peak **422 MiB**. SCRAM + deny-by-default: 21 ACLs from
`kafka_admin.py`, `kafka-setup` idempotent (2nd run: 0 added, 0 removed); 8 live tests (no
login, wrong password, each login's denials, 2022 event time kept, pod listener); 16 unit
tests; `just rotate-kafka`. A JVM hardening flag is set and test-enforced (assessment in
the private record). Edge watchdog ok. CI: config/ACL tests only (jobs cannot reach containers); broker
behaviour proven live. Deferred to S6.6 with the pod: its Kubernetes Secret and NetworkPolicy.
Lag exporter → S6.11.

## S6.5 — The replayer: a bank that sends like a real one ✅ done 2026-11-21

**As** the demo, **I want** a producer that replays validation transactions like live
payments, with real-world mess, **so that** the consumer is tested against what production
throws at it.

- Idempotent producer; one partition; each message carries `event_id` (`source_row`),
  event time and `seq`.
- Pacing: true time (1×), accelerated (e.g. 60×, 600×), as fast as possible.
- **Seeded realism, logged to a fault log:** late/out-of-order events, duplicates, bursts
  (paydays), malformed records, a schema-version change mid-stream. Faults touch
  *delivery* only, never event time or labels.
- Durable checkpoint: a restarted replayer resumes without re-sending.
- Runs as a job user (`gg-reader`-style profile) reading `silver`.

**Done 2026-11-21.** `stream/replayer.py` + `stream/messages.py` (schema v1/v2, **no label in
the message** — labels come later, S6.9; amounts bit-exact through JSON). Pacing 1× / N× /
max with bursts that compress wall time only. Seeded faults (duplicate, late up to N
positions, malformed, schema v2 mid-stream) logged to `stream-runs/<run>/faults.jsonl`.
Checkpoint after each flushed batch; a crash resumes there (≤ one batch re-sent, dropped by
event id). Runs as job `replay` (user gg-reader, its own Kafka login only). Smoke run
(2,000 events, chaos): 2,025 records = 2,000 distinct + 22 duplicates + 3 malformed, v1 + v2,
0 labels, 46 late arrivals, all inside validation; re-run → 0 sent. 18 unit tests.
**Carries into S6.6:** the consumer needs a reorder buffer larger than the replayer's
`late_max_shift` (50) so late events are applied in training's order, not refused.

## S6.6 — The consumer: score every event once ✅ done 2026-11-21

**As** the fraud checker, **I want** to read each transaction, update features, score it
with the model in process and store the decision exactly once, **so that** nothing is lost
or doubled.

- confluent-kafka 2.16.x, new group protocol, micro-batches (200-1,000).
- New Postgres database + role (`pg_access.SERVICES`, backed up automatically):
  `decisions` (score, rules fired, the features behind it, model version + hash),
  `consumer_offsets`, `outbox` — all written in **one transaction**;
  `ON CONFLICT (event_id) DO NOTHING`.
- Bad records → dead-letter topic, never a crash. Redis down / not loaded → pause, not
  cold scores (same rule as S5.5). Clean shutdown on SIGTERM.
- Proof: N events in → exactly N decisions; the scores equal the HTTP scorer's for the
  same events.

**Done 2026-11-21.** `stream/consumer.py` on k3s (`k8s/consumer.yaml`: 1 replica,
`Recreate`, restricted pod, own egress policy — DNS + Redis + Kafka + Postgres on
graphguard-net, S3 on 443 — secrets from `graphguard-stream` / `graphguard-model`, same
pinned model as the scorer). Reorder buffer 200 (> the replayer's 50), repeats dropped by
event id, live features (S6.3), in-process scoring (`score_rows` == `score_one`), one Postgres
transaction per batch (decisions + offset + outbox), dead letters, advisory-lock single
writer, pause when Redis is down or not loaded. Postgres `stream` / `stream_app` (own db only,
from pods + host; live access test; backed up; `just rotate-pg stream_app` rolls the pod —
done live). **Proof (`stream/e2e.py`): 20,000 events → 20,000 decisions, 0 score mismatches
with the offline evaluation — host consumer, host + chaos, and the k3s pod + chaos (210
repeats dropped, 20 malformed → dead letters, 0 late).** Pod peak 345 MiB → cap 640Mi.
Scorer rolled to image 0.1.6 (carries S6.2's arithmetic): 32/32 health checks during the
upgrade. Postgres now also on the pod bridge (pg_hba: only `stream` from pods). `just ci-wait`
(read-only Forgejo token) — CI is now checked without Lubo.

## S6.7 — Chaos: kill it, restart it, repeat it — same answers ✅ done 2026-11-21

**As** a skeptical reviewer, **I want** proof that crashes and repeats change nothing,
**so that** "effectively-once" is measured, not claimed.

- kill -9 the consumer at seeded points (including between Redis and Postgres), restart the
  broker, re-send slices, duplicate everything.
- After each: rows = distinct event ids = events sent; stored offset = end of topic; Redis
  features = batch recomputation.
- **Decision parity under chaos:** same decisions at 1×, 600× and as-fast-as-possible, with
  and without faults.

**Done 2026-11-21.** `python -m graphguard.stream.chaos` — 6 scenarios on the k3s consumer,
20,000 events each: clean at max speed, clean at 600×, seeded faults, the pod killed twice
(force delete), a crash between Redis and Postgres (the consumer's once-only chaos hook), the
broker restarted mid-replay. **6/6 exact:** every transaction decided once, 0 score
mismatches with the offline evaluation, 0 rule mismatches, Redis's final state equal to a
batch recomputation (300 accounts), exactly the planned dead letters — and the same 211 rule
hits and 221 alerts in every scenario (decision parity across speeds and faults). The first
run found a real bug: a malformed record redelivered after a kill became a second dead letter
(22 vs 20) → `dead_letters` unique per Kafka offset, and a dead-letter message is published
only for a new row. Images 0.1.7 (chaos hook) and 0.1.8 (fix + rules); scorer rolled each
time with 0 failed health checks.

## S6.8 — Rules next to the model ✅ done 2026-11-21

**As** an investigator, **I want** simple rules beside the model, **so that** there is a
baseline the model must beat and a safety net if it fails.

- Rules on as-of state only: velocity, fan-out / fan-in, structuring just under a round
  amount, new account + large amount; "both accounts new → review" (FINDING-014) as a hard
  override.
- Combination policy in an ADR: alert if any rule fires or the score passes the threshold;
  every alert has `reasons[]`; k queue slots per simulated day.
- **The table:** rules-only vs model-only vs combined precision@k at the same k, on
  validation, and what each catches that the other misses.

**Done 2026-11-21** (FINDING-016, ADR 0007). Six as-of rules (`stream/rules.py`), thresholds
from the training window only (generated `stream/rule_thresholds.py`, shipped in the image).
Validation through `evaluate()`: rules-only p@5000 0.0042 (21 launderers), model-only 0.1084
(542), combined 0.1084 at k (PR-AUC 0.262 vs 0.282). Rules find 7 the model misses. Live: each
decision stores its rules and an `alert` flag (priority ≥ the rank-5,000 line on validation);
alerts with `reasons` go to the `alerts` topic through the outbox. The e2e check now also
proves live rules == offline rules for every transaction.

## S6.9 — Labels arrive late, like in a bank

**As** the person who will build retraining (Phase 8), **I want** labels to arrive days
after the alert on their own topic, **so that** nothing downstream learns from the future.

- Separate `labels` stream with `label_known_at`; investigator capacity per day; delay
  drawn from a stated, cited distribution (US SAR deadline 30-60 days; Dal Pozzolo's
  7-day feedback).
- `gold.labels.label_known_at` filled; anything that learns sees a label only after it.
- **Finding written up honestly:** with realistic delays almost no labels arrive inside a
  ~50-hour window — which is exactly why real systems monitor without labels.

## S6.10 — Shadow scoring: a challenger that decides nothing

**As** the model owner, **I want** a second model to score the same stream without acting,
**so that** a new model is compared on identical traffic before it is promoted.

- Second consumer group → `decisions_shadow`, never the alert queue.
- Report: agreement, alert overlap, precision@k per model where labels exist, per segment
  (currency, payment format, cold-account class).

## S6.11 — Lag, latency and the overnight run (the Phase 6 gate)

**As** Lubo, **I want** to leave the stream running overnight and find it healthy in the
morning, **so that** Phase 6 is done by the plan's own definition.

- Consumer lag and decision latency exported (lag exporter, capped); the S6.1 alert extended
  to "stream stalled" and "lag growing".
- Overnight soak at a steady rate: zero lost or doubled decisions, memory flat under caps,
  LuBot untouched.
- CLAUDE.md "Where we are" updated only when this passes.
