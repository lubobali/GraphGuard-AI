# Phase 6 — The stream: stories

**Status:** written 2026-11-21, waiting for Lubo's approval. Research behind it:
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

## S6.1 — The scorer alert: an email when it breaks, and when it heals

**As** Lubo, **I want** an email when the scorer goes down and another when it comes back,
**so that** an outage reaches me before the stream starts depending on the scorer (it sat
broken for 18 days once and nobody noticed — S5.2).

Acceptance criteria (Given/When/Then):
- [ ] **Given** the scorer is healthy, **when** the check runs, **then** no email is sent
      and the state file says `healthy`.
- [ ] **Given** the last state was `healthy`, **when** a check finds a problem (`just
      k8s-check` fails, or `/health` answers 503 "unavailable"/"not loaded", or no
      answer), **then** exactly one email is sent: what broke, since when, the first
      command to run, a link to the runbook.
- [ ] **Given** it is still broken, **when** the next checks run, **then** no new email —
      except one reminder per 24 h while broken.
- [ ] **Given** it was broken, **when** a check passes, **then** one "recovered" email with
      how long it was down.
- [ ] **Flapping guard:** a state changes only after 2 checks in a row agree (no email for
      a 1-minute blip, e.g. during a rolling upgrade).
- [ ] **If the email itself fails**, the failure is logged and the check retries next run;
      `just alert-status` shows the last check, the state and the last email sent (and
      exits 1 when the check is stale or mail failed), next to the other health checks.
- [ ] **The judgement is pure and unit-tested** (state machine: healthy/broken/flapping/
      reminder/recovery, all with a fake clock and a fake mailer). Only `main` talks to
      k3s, HTTP and SES.
- [ ] **Live drill without breaking anything:** `just alert-drill` runs the real path with
      a forced-failure flag (never touches the scorer) and sends one real "drill" email
      and one "recovered" email. Lubo confirms both arrived.
- [ ] **Least privilege:** the SES key can send only from the one verified address
      (`ses:FromAddress` condition) and nothing else — a live test proves another action
      is denied. Key in `.secrets/alerts-aws.env` (registry entry), Lubo's address in
      `.secrets/` too, **never in the repo**. The unit runs sandboxed (like the edge check),
      key handed in with `LoadCredential`.
- [ ] Runbook `docs/runbooks/scorer-down.md`: what each email means, first commands, how to
      silence it during planned work (`just alert-pause 2h`).

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

## S6.2 — Training is the truth: the online snapshot matches it exactly

**As** the person defending the numbers, **I want** the snapshot that seeds the stream to
equal training's features bit for bit, **so that** the stream starts from what the model
learned on.

- Money totals seeded with training's sequential arithmetic, not `sum()` (D2).
- `sent_last_24h`: a send exactly 24 h earlier is **excluded**, as in training; the
  snapshot carries each sender's recent send times (481,840 sends), because a count
  cannot roll forward.
- One tie order everywhere: `(timestamp, source_row)` (FINDING-010) — including the
  training sort, which is checked first.
- The stream source is `silver` with `train_end <= ts < val_end`, asserted;
  `test_set_touch_check` green; `sealed` never touched.
- Proof: snapshot vs training features per account, zero mismatches. Scorer behaviour
  unchanged (2,000/2,000 identical scores).

## S6.3 — Live features, proven before Kafka exists

**As** the stream, **I want** one atomic update per transaction that returns both
accounts' features *before* the event and then applies it, **so that** live features stay
exactly equal to training forever.

- One Redis Function per event: per-account watermark `(timestamp, source_row)` so a
  repeat changes nothing; one global edge set for distinct counterparties (975k pairs,
  compact encoding); per-sender 24 h window; a pending record for crash recovery.
- `noeviction` and real headroom in Redis; memory measured with `MEMORY USAGE`.
- **The parity test:** replay all ~1M validation events through the updater (no Kafka),
  compare every feature of every row with `graph.py` — **zero mismatches**. Plus: every
  event twice, shuffled same-minute ties, a crash in the middle, the 24 h edge. A sample
  version runs in CI, the full one as `slow`.

## S6.4 — Kafka on the box, hardened and measured

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

## S6.5 — The replayer: a bank that sends like a real one

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

## S6.6 — The consumer: score every event once

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

## S6.7 — Chaos: kill it, restart it, repeat it — same answers

**As** a skeptical reviewer, **I want** proof that crashes and repeats change nothing,
**so that** "effectively-once" is measured, not claimed.

- kill -9 the consumer at seeded points (including between Redis and Postgres), restart the
  broker, re-send slices, duplicate everything.
- After each: rows = distinct event ids = events sent; stored offset = end of topic; Redis
  features = batch recomputation.
- **Decision parity under chaos:** same decisions at 1×, 600× and as-fast-as-possible, with
  and without faults.

## S6.8 — Rules next to the model

**As** an investigator, **I want** simple rules beside the model, **so that** there is a
baseline the model must beat and a safety net if it fails.

- Rules on as-of state only: velocity, fan-out / fan-in, structuring just under a round
  amount, new account + large amount; "both accounts new → review" (FINDING-014) as a hard
  override.
- Combination policy in an ADR: alert if any rule fires or the score passes the threshold;
  every alert has `reasons[]`; k queue slots per simulated day.
- **The table:** rules-only vs model-only vs combined precision@k at the same k, on
  validation, and what each catches that the other misses.

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
