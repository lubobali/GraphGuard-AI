# Phase 7 — The interface: stories

**Status:** approved by Lubo 2026-11-22 (decisions D1-D8 made for him, as he asked). S7.0 in progress. Research behind it:
`docs/research/AML investigator interface research 2026.md` (five web tracks + a full code
read, notes beside it). Lubo asked for the decisions to be made for him ("make it look
real"); each is written below with its reason, and ADR 0008 records them.

**How stories are expanded:** one at a time, just before work starts on it. S7.0 and S7.1
have the full treatment; the rest stay short until their turn.

## Main goal

A small, honest copy of a **real AML case manager** that a non-technical person can use:
a queue of alerts worked in order, each alert opened into a case with the ring drawn and
the reasons in plain words, a slider that answers "how many alerts can my team work, and
what do we catch and miss", and an investigator agent whose mistakes are measured, not
claimed.

The data stays synthetic (IBM AMLworld) and **every page says so**. Everything shown comes
from the **validation window**; the test window stays sealed (its one-time opening is a
separate step before Phase 8b).

**Epic / Definition of Done** (PLAN.md, Phase 7): someone non-technical looks at it and can
say what the system does and what they would do next — tested on a real person, not on
ourselves — and the agent's unsupported-claim rate is measured and at zero on the eval set.

**What the research changed** (vs PLAN.md's sketch):
1. **Real tools look like a work list, not an ML dashboard.** Queues sort by deadline,
   then risk; alerts are grouped per customer; every decision is logged. So: the queue is
   grouped by account, each alert has a due time, the case page records a verdict.
2. **Managers read counts at a fixed workload, not percentages or AUC** (lay readers
   misread confusion matrices). The slider speaks in counts, next to the rules at the
   same workload; PR-AUC lives on the About page for validators.
3. **No money totals.** Amounts are in 15 currencies (euro, yuan, bitcoin…) with no exchange
   rates; summing them is meaningless. Amounts are shown per transaction in their own
   currency; the slider counts transactions and rings.
4. **The screen obeys the leakage contract too.** The ring is drawn only from payments
   before the alert; the true ring type (the answer key) sits in a separate tab and the
   agent never sees it.
5. **The score is not a probability** (training weighted laundering ~1,326×). The UI shows
   rank and percentile, never "23% chance".
6. **SR 11-7 is gone** (replaced by SR 26-2, April 2026). The About page's model-risk
   summary follows SR 26-2: purpose, data, limits, monitoring — and says the LLM agent is
   outside its scope.
7. **No vendor publishes a measured error rate for its AI investigator.** Ours will — with
   a template baseline it has to beat, published either way.

## Decisions (made for Lubo, recorded in ADR 0008)

| | Decision | Why |
|---|---|---|
| D1 | **One alert = one transaction; the queue groups them by sending account** | The model scores transactions (that is what was evaluated); real tools show one line per customer. Both stay true. |
| D2 | **The demo team works 100 alerts a day** (~5 investigators at ~20 each) | Matches the late-label simulator (S6.9) and industry figures; the slider covers every other number. |
| D3 | **Keep Ray Serve; turn the shadow pod off when not comparing; the new API must fit in ~256 MiB** | Ray Serve on k3s is a Phase 5 deliverable hiring managers look for; swapping it to save memory loses more than it gains while the box has room. Revisited if the measured total says otherwise. |
| D4 | **Private demo first** (localhost over the ssh tunnel, like MLflow) + the video. A public URL is a later, separate step through the LuBot session | A public site on a box that runs LuBot production needs a box-wide change and a security review; the gate needs a real person, not the internet. |
| D5 | **Next.js (static export) + React + TypeScript + Tailwind; React Flow for the ring; a small FastAPI read API** | Static files need no Node server (no memory, none of 2026's Next.js server holes); React Flow is MIT, small, and draws money moving. |
| D6 | **The agent's model is chosen at S7.10** (PLAN says NVIDIA NIM; checked then). A key, if needed, is typed by Lubo with `just secret-set` | Nothing before S7.10 depends on it. |
| D7 | **The case page records a verdict** (escalate / close + note) in an audit table; verdicts never feed training directly | Real tools log every decision; labels only enter learning through the delayed-label door (`known_as_of`). |
| D8 | **Use the synthetic account names** (bank + entity from the raw accounts file) | "Corporation #4421 at Bank 70" reads like a real queue; hex IDs do not. Still synthetic, and labelled so. |

---

## S7.0 — The decisions, written down (ADR 0008), and the ground cleaned

**As** Lubo, **I want** every Phase 7 choice recorded with its reason and the docs telling
the truth, **so that** I can explain each choice in an interview and Phase 7 starts on
facts, not stale notes.

**Tasks and acceptance criteria**

1. **ADR 0008** `docs/adr/0008-the-investigator-interface.md`, in the house ADR format:
   - [ ] D1-D8, each with the options considered, the choice, the reason (with its source
         in the research), and what would make us change it.
   - [ ] The numbers it rests on, checked against `docs/analysis/s6.8-rules.json`:
         1,083 laundering transactions in validation; top 5,000 → 542 caught (541 missed),
         rules 21; 127 of 168 rings touched; alert line 5,000 per ~50.6 h ≈ 2,370/day vs
         the demo's 100/day (why both exist).
2. **PLAN.md**, changed openly, not silently:
   - [ ] New revision **R-4** under "Plan revisions" (date, cause = the 2026-11-22
         research, what changed, what did not).
   - [ ] Phase 7 text: "ranked accounts" → D1; "same stack as LuBot's frontend" → D5;
         SR 26-2 replaces SR 11-7 wherever it is named; no money totals; the tester.
3. **Stale docs fixed** (each checked against the code or the box first):
   - [ ] `README.md`: status line and "What is next" table (Phases 5, 5b, 6 done; 7 next).
   - [ ] `pyproject.toml` description: XGBoost in production, GNN as research arm (R-1).
   - [ ] `CLAUDE.md`: Postgres cap 384M; MLflow "1 worker" vs "2 web workers" (compose
         says `--workers 1` — the paragraph is the stale one); disk free; swap; image
         tags in the k3s/consumer notes; Phase 7 row "in progress".
   - [ ] `docs/leakage_audit.md`: one number to quote — PR-AUC **0.28155** (tuned,
         artifact-free, the production model); 0.248 is the untuned artifact-free run;
         never 0.360. No result changes, only the wording.
   - [ ] `k8s/networkpolicy.yaml` header: says egress is unrestricted; the file denies
         egress by default (S5b.1). Comment only.
   - [ ] FINDING-014 gets a dated note: the live stream fires "both new" ~5 times per
         window, not ~27/day (that was the static snapshot).
4. **Disk: image retention** (found while checking the numbers: 11 scorer images of
   ~2.4 GB each in Docker and in k3s; only 0.1.12 runs):
   - [ ] `just image-prune`: keeps the running tag and the one before it (rollback),
         unpins and removes the rest from k3s and Docker. Never touches other projects'
         images or Docker's shared build cache.
   - [ ] A unit test for the keep/remove choice (never the running tag, never the
         rollback tag, never a non-GraphGuard image).
   - [ ] Measured before/after disk; `just k8s-check` green after.
5. **Done when:** `just check` green, CI green, both remotes equal, LuBot untouched.

Out of scope: any code for the screens (S7.1+).

**Done 2026-11-22.** ADR 0008 (D1-D8, the numbers checked against `s6.8-rules.json`);
PLAN.md R-4 + Phase 7 text; stale docs fixed in README, pyproject, CLAUDE.md (Postgres cap,
MLflow workers, disk, swap, revision count), leakage audit (one number: 0.28155), network
policy comments, FINDING-014 (live: "both new" fired 5 times in the window — checked in the
soak's decisions). **Disk:** `just image-prune` (`ops/images.py`, 5 unit tests) removed 9 old
scorer tags; k3s also kept each removed image under its sha256 name (`ctr images rm` drops
only the tag), so those 9 were removed too and the code now uses `crictl rmi`. Free disk
**28 GB → 60 GB**, k3s image store 23 GB → 4.9 GB; running 0.1.12 and rollback 0.1.11 kept;
`k8s-check` green. Docker's shared build cache (~48 GB, used by LuBot too) left alone.
Note: free disk fell ~8 GB in an hour before the prune, not from GraphGuard's data (Kafka
266 MB, Postgres 1.6 GB, repo 5.2 GB) — reported to Lubo for the LuBot session.

## S7.1 — Demo data that a test run cannot erase, read through a read-only login

**As** an investigator using the demo, **I want** the queue to be there tomorrow, **so
that** a soak or chaos run never empties the screen.

Today every soak, e2e and chaos run truncates the stream tables (`db.reset()`), and the only
database login (`stream_app`) can write.

**Design.** A separate Postgres **database `demo`** (not a schema in `stream`: a stream reset
cannot reach another database). Three roles, each with the least it needs:

| Role | May | From | Used by |
|---|---|---|---|
| `demo_owner` | own the tables, load them | host only | `just demo-build` (root, on the host) |
| `demo_reader` | `SELECT` on the demo tables, nothing else | GraphGuard network + host | the read API (S7.6), tests |
| `demo_writer` | `INSERT` into `verdicts` only (D7) | GraphGuard network + host | the API's verdict endpoint |

Tables (built from the soak's 1,015,300 validation decisions + silver + the accounts file):
- `transactions` — one row per scored transaction: time, both accounts and banks, both
  amounts and currencies (never summed, ADR 0008), payment format, score, **priority**
  (`rules.priority`, ADR 0007), **rank** and **percentile** (by priority, ties by event
  order — the queue's order), rules, alert, cold policy, model version, the feature vector.
- `accounts` — (bank id, account) → bank name, entity name (D8). The key is the pair: 8
  account numbers exist at two banks each (found while reading the file).
- `truth` — event id → is_laundering. **Kept apart** from `transactions` so the queue and the
  agent never read it by accident; the capacity curve and the answer-key tab do (S7.3, S7.8).
- `verdicts` — event id, verdict (escalate / close), note, at. Append-only audit (D7).
- `build_info` — when, from which soak run, model version, row counts, content hash.

**Acceptance criteria**
- [ ] `src/graphguard/demo/db.py` (roles, database, schema; idempotent) and
      `src/graphguard/demo/build.py` (the load); `just demo-setup`, `just demo-build`.
- [ ] Pure parts unit-tested first: rank/percentile order, account-name join on the pair,
      truth split out, the content hash stable for the same input.
- [ ] Built only from the validation window (`assert_in_validation`); refuses to build if
      the stream's decisions are incomplete (count ≠ the validation window's 1,015,300) or
      not from one model version.
- [ ] Live tests: `demo_reader` can SELECT but not INSERT/UPDATE/DELETE/CREATE; cannot
      connect to `stream` or any other database; `demo_writer` can INSERT a verdict but
      not change `transactions`, not delete verdicts. `db.reset()` of the stream leaves
      `demo` unchanged.
- [ ] `pg_access`: the two extra roles get their own hba lines (no `trust`, SCRAM); the
      existing live access test covers them. Passwords in `.secrets/demo-*.env`, each in
      the secrets registry with a rotation command; `demo` is backed up automatically
      (it is in `SERVICES`).
- [ ] Rebuilding is deterministic: same inputs → same content hash.
- [ ] Postgres memory measured before/after; disk size of `demo` recorded.

Out of scope: the API (S7.6), ring edges (S7.5), ring ids (S7.2).

**Done 2026-11-22.** `demo/db.py` + `demo/build.py`, `just demo-setup | demo-build`. Database
`demo` (734 MB): 1,015,300 transactions (rank 1 = highest priority; the stream's 5,000 alerts
are exactly ranks 1-5,000 — a live test), 1,083 laundering in `truth`, 518,581 accounts.
Three roles, live-tested: the reader cannot write or create; the writer can only add a
verdict (cannot read the queue, change or delete verdicts); a bad verdict is refused by the
table; `stream_app` cannot even connect to `demo`. Deterministic: four builds, identical
fingerprints. **Memory:** the first build peaked at 3.5 GB (a million rows as Python
objects); now COPY out, sliced CSV in, vectorised priority (test: equal to
`rules.priority`) → 2.0 GB, run under a 2.5 GB cap; 41 s. Postgres 310 of 384 MiB (68 MB
anon, the rest cache). `demo-db.env` registered (44 secrets, 0 problems), rotation
`just rotate-pg demo_owner|demo_reader|demo_writer`, `demo` in the nightly backup.

## S7.2 — The ring list in the lakehouse, with the test window sealed

**As** the leakage contract, **I want** ring labels in the lakehouse split like the
transactions, **so that** the screens, the agent and training can never see a test-window
ring by accident.

Today the ring list exists only as the raw patterns file, which holds **every** window,
test included. The trainer job is still allowed to read it (ADR 0003's open follow-up), and
the test-set guard does not notice raw-file reads at all.

**Design.**
- `gold.rings` (train + validation) and `sealed.rings` (test): one row per ring
  transaction — `source_row`, time, `pattern_id`, `pattern_type`, `pattern_detail`, `hop`.
  Written by `just lakehouse-build` (builder), matched to bronze on the evaluation's own
  key (`_MATCH_KEY`, first match kept — the same rule as `attach_pattern_ids`). Governance
  is per namespace, so trainer/reader see `gold.rings` and never `sealed.rings`, with no
  policy change.
- `build_artifacts` (the trainer) attaches ring ids from `gold.rings` instead of the raw
  file; the trainer job loses its raw-file permission.
- The demo's `truth` gains `pattern_id`, `pattern_type`, `hop` from `gold.rings`
  (the answer key's tab, S7.8; never the queue, never the agent).
- The guard learns two things: naming the raw transaction or pattern file is allowed
  only in listed files, each with its reason; `features_for_split(..., "test")` counts as
  loading the test split.

**Acceptance criteria**
- [ ] Unit (first): `ring_rows()` gives exactly `attach_pattern_ids`' ring id for every
      transaction (same key, same tie rule); rows ≥ `val_end` go only to the sealed frame.
- [ ] Unit: the guard flags a raw-file name in an unlisted file and `features_for_split(x,
      "test")`; the current tree passes with every raw reader listed and explained.
- [ ] Live: after the build, `gold.rings` has no row at or after `val_end`; the reader
      identity cannot load `sealed.rings`; the validation window holds **168** rings (the
      number every evaluation reports).
- [ ] Slow parity: ring ids from `gold.rings` == from the raw file on all of silver, so
      switching the trainer changes nothing (no retraining needed: rings are only for
      evaluation, never features).
- [ ] The trainer profile no longer lists the patterns file; `test_jobs_live` proves it
      cannot read it. ADR 0003's follow-up marked closed.
- [ ] `just labels publish` re-run after the build (the build resets `label_known_at`).
- [ ] Demo rebuilt with ring columns; live test: 168 distinct rings in `truth`, every one
      from the validation window.

**Done 2026-11-22.** `gold.rings` 1,870 rows (train + validation), `sealed.rings` 684 (test),
written by `just lakehouse-build`; live: no gold row at or after `val_end`, the reader cannot
open `sealed.rings`, **168** validation rings. Training (`build_artifacts`) reads ring ids from
`gold.rings` (snapshot pinned in its lineage); the trainer job lost the raw file
(`test_jobs_live`: no job but the builder can read any raw file). Slow parity on all 4,061,486
silver rows: same ids, same order. **Found on the way:** the old `attach_pattern_ids` join did
not keep row order, and features break same-minute ties by order; measured 0 changed feature
values on train and validation, now guaranteed with `maintain_order` (note under FINDING-015).
The guard now fails on any raw-file name outside `RAW_ALLOWLIST` (19 files, each with its
reason) and counts `features_for_split(..., "test")`. Demo `truth` carries ring id/type/hop
(168 rings, live test). Labels re-published after the build (5 known at stream end, as before).

## S7.3 — The capacity numbers, from the one evaluation entry point

**As** a manager, **I want** "work N a day → catch X, miss Y, rules catch W", **so that** I
can choose a team size from real numbers.
- `evaluate()` gains recall@k and minority-class F1 (R-2), test-first.
- A precomputed curve in **counts per day** (k = 1…5,000): laundering caught, rings
  touched / caught, missed; same for the rules and random. One stated definition of
  "ring caught". No currency totals.

## S7.4 — Why this alert, in plain words

**As** an investigator, **I want** the top three reasons for a score in a sentence each,
**so that** I can trust or reject it quickly.
- Exact SHAP from XGBoost's own `pred_contribs` on the stored feature vectors; test: the
  contributions add up to the stored score exactly. Stored in the demo schema.
- A template table, one plain sentence per feature family, filled with the as-of values;
  rule hits shown word for word; the raw numbers one click away.

## S7.5 — The ring as it looked at the moment of the alert

**As** an investigator, **I want** the money around an alert drawn, **so that** I can see
the shape.
- An as-of subgraph builder (1–2 hops, edges strictly before the alert, hubs collapsed to
  "+N more" by as-of degree). Leakage test: no edge at or after the alert's time.

## S7.6 — A small read API

**As** the frontend, **I want** one small read-only API, **so that** the browser never
touches the database.
- FastAPI, GET-only except the verdict endpoint; server-sent events for the live replay
  feed; rate limit and a cap on open streams; measured memory under ~256 MiB (D3);
  hardened like every other service (`test_compose_hardening.py` or a restricted pod).

## S7.7 — The Queue page, with the slider

**As** a manager, **I want** one screen that shows the work and the trade-off, **so that**
I understand the system in a minute.
- Honesty banner (synthetic data, validation window, date). Slider with the plain
  sentence (default 100/day, D2) and the capacity curve against the rules and random.
  The queue: grouped by account, due time, rank/percentile, top reason, new-account tag.
  A three-layer strip: measured offline (solid), estimated live (dashed, with its
  warning), confirmed so far (with "% still unlabelled" and the label-bias note).

## S7.8 — The Case page

**As** an investigator, **I want** an alert opened into everything I need, **so that** I can
decide in minutes.
- The ring (React Flow, left to right by day, money animated in time order, table beside
  it), the three reasons, rule hits, the account's recent history in its own currency,
  the agent's report (after S7.10), a separate "answer key" tab, and escalate / close
  with a note → audit table (D7). Keyboard usable; reduced motion respected.

## S7.9 — The About page

**As** a hiring manager, **I want** the proof on one page, **so that** I can judge the work.
- Architecture diagram, headline result against rules and dumb baselines, the GNN
  finding, the leakage contract, the SR 26-2 model-risk summary, PR-AUC for validators,
  links to findings and ADRs.

## S7.10 — The investigator agent, with a measured error rate

**As** an investigator, **I want** a draft case report I can check, **so that** I save time
without trusting a black box.
- Tools over MCP (score, ring, reasons, history); structured claims, each citing record
  IDs; a deterministic checker re-verifies every ID, amount and date against the data.
- Eval set from validation alerts only (with "should say I don't know" cases); report the
  unsupported-claim rate **before** the checker (the LLM's real error rate, with a
  confidence interval) and **after** it (gate: zero); typology recall against the answer
  key the agent never saw; a comparison against the plain template — published even if
  the LLM loses. Logged in MLflow. The agent drafts; the human decides.

## S7.11 — The test on a real person (the Phase 7 gate)

**As** Lubo, **I want** a non-technical person to use it, **so that** "it is clear" is
measured, not assumed.
- One session with someone who does not know what a model is (Lubo picks them): they
  get the Queue page and no explanation. Written down: what they say the system does,
  what they would do next, where they got stuck. Fixes from it, then the gate is marked.

Out of scope for Phase 7: a public URL (separate step, LuBot session first), logins and
roles for many users, live re-scoring, money totals, a manager operations dashboard with
simulated SLAs. The video is Phase 8b.
