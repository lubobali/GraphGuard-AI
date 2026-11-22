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
         rules 21; 127 of 168 rings caught (140 touched — S7.3 corrected the word); alert line 5,000 per ~50.6 h ≈ 2,370/day vs
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

**As** a manager, **I want** "your team works N a day → it catches X laundering transactions
and Y rings, misses Z; the rules at the same workload catch W", **so that** I can choose a
team size from real numbers.

**Design.**
- `evaluate()` gains, per k: `caught` and `missed` (counts — the slider's language),
  `recall_at_k`, and the minority-class F1 at k (R-2's promise: F1 of the laundering class
  when the top k are called laundering). Test-first, in `tests/evaluation`.
- `capacity_curve()` (`src/graphguard/evaluation/capacity.py`): every k from 1 to 5,000 in
  one vectorised pass (5,000 `evaluate()` calls would each re-sort a million rows). **A test
  holds it equal to `evaluate()`** at every default k and at random k — so the slider's
  numbers still come out of the one entry point's definitions.
- Four rankings, same validation rows: **system** (the queue's priority, ADR 0007), **model**
  (score only), **rules** (`rules_only_rank`, FINDING-016), **random** (seeded). Rings: both
  readings — *caught* (≥ 50% of the ring's validation hops flagged) and *touched* (any hop).
- Per day: the window is 50.6 hours ≈ 2.11 days; "N a day" = k = N × 2.11 (stated on the
  screen). No money anywhere (ADR 0008).
- Stored in the demo database (`capacity`: ranking, k, caught, missed, precision, recall,
  rings caught, rings touched), built by `just demo-build`; `docs/analysis/s7.3-capacity.json`
  keeps the checkpoints (k = 50, 100, 211, 500, 1,000, 5,000).

**Acceptance criteria**
- [ ] Unit (first): `caught + missed == n_positives`; recall and F1 on a hand-built case;
      the curve equals `evaluate()` (precision, caught, rings caught/touched) at the default
      ks and 20 random ks, on random data with ties.
- [ ] Live: at k = 5,000 the model curve gives 542 caught (s6.8) and the rules curve 21;
      the ring numbers at k = 5,000 are written down with their definition, and ADR 0008 /
      the stories corrected if "127" is not the reading they say.
- [ ] The 100-a-day point (k = 211) is in the JSON with all four rankings — the demo's
      opening sentence.
- [ ] `capacity` readable by `demo_reader`; 20,000 rows; rebuild deterministic.

**Done 2026-11-22.** `evaluate()` reports `caught_at_k`, `missed_at_k`, `recall_at_k`,
`f1_at_k` (minority-class F1, R-2). `evaluation/capacity.py`: every k in one pass, held equal
to `evaluate()` k by k (3 seeds, default + 20 random ks). Demo table `capacity` (4 rankings ×
5,000 k = 20,000 rows) and `docs/analysis/s7.3-capacity.json`. Live: model at k = 5,000 → 542
caught, **127 rings caught (≥ half their hops) and 140 touched** — so "127" is the *caught*
reading; ADR 0008 and this file said "touched" and are corrected. Rules 21. **The demo's
opening sentence (100 a day, k = 211):** the system catches 167 of 1,083 laundering
transactions and 35 of 168 rings (81 touched); rules alone 1 and 0; random 0. The rule
override costs 3 at that size (model alone 170) — written into ADR 0007.

## S7.4 — Why this alert, in plain words

**As** an investigator, **I want** the three things that pushed a score up, each in one plain
sentence, **so that** I can trust or reject the alert quickly.

**Design.**
- **Exact SHAP from XGBoost itself** (`pred_contribs=True`, TreeSHAP; no new library) on
  the feature vectors the stream stored. Units are log-odds; contributions + base value =
  the model's raw margin, and sigmoid(margin) = the stored score.
- **The right model, proven:** the build recomputes each explained row's score with the
  local production bundle and refuses to run unless it equals the stored score
  bit-for-bit (the model that decided is the model that explains).
- **Reason templates** (`demo/reasons.py`): one sentence per feature, filled with that
  transaction's as-of value — counts as numbers, timings as durations, currencies by name.
  **Money totals are never printed** (the history sums mix 15 currencies): those two
  features are said as "higher than N% of senders/receivers in this window" instead.
- The top 3 *positive* contributions become the reasons; rule hits are shown word for word
  from the rule's own definition (`rules.py`), separately.
- Stored for the top 20,000 of the queue (4× the slider's maximum): `explanations`
  (event id, base value, contributions, the three reasons).

**Acceptance criteria**
- [ ] Unit (first): a template for every one of the 15 features (a test fails if the model
      gains a feature without one); no reason ever prints a summed amount; the NaN case
      ("never sent before") reads correctly; top-3 picks the largest *positive* ones.
- [ ] Unit: additivity on a small real-shaped model — contributions sum to the margin.
- [ ] Build: every explained row's recomputed score == stored score (exact); every row's
      contributions sum to logit(score) within float32 rounding (stated tolerance 1e-4).
- [ ] Live: 20,000 rows in `explanations`, each with 3 reasons; `demo_reader` can read it.
- [ ] Measured: build time and memory added.

**Done 2026-11-22.** `demo/reasons.py` (a sentence for each of the 15 features; the two
mixed-currency sums said as "higher than in N% of the payments in this window"; rule hits in the
rules' own words), `demo/explain.py` (XGBoost's own TreeSHAP). Demo table `explanations`: the
top 20,000, 3 reasons each. The build recomputed every explained score with the local bundle —
**all 20,000 equal the stored scores bit-for-bit** (it refuses otherwise) — and the
contributions sum back to the scores within 1e-5 (live test). SHAP with 4 threads (identical
output; 1 thread took ~90 s): build 75 s, peak 2.0 GB.
**Finding (FINDING-018):** the explanations showed weekday as a top-3 reason for 77.9% of the
top 5,000. Investigated: each weekday occurs once in training and Wednesday (48% of
validation) never; the simulator launders a near-constant count per day. Retrained the same
recipe without it: PR-AUC 0.28253 vs 0.28155 (reproduced exactly), 555 vs 542 caught at 5,000 —
it costs nothing. Production unchanged in Phase 7; the weekday reason is labelled as a simulator
pattern on screen; the leakage audit gains the calendar section it never had; the model without
weekday is Phase 8's first challenger.

## S7.5 — The ring as it looked at the moment of the alert

**As** an investigator, **I want** the money around an alert drawn, **so that** I can see the
shape — fan-out, pass-through, a loop back — that no single row shows.

**Design.**
- **As of the alert, exactly:** only transactions strictly before it in the project's order —
  (time, source_row), the same order the features use (FINDING-010). Leakage rule 2 applied
  to pixels: nothing at or after the alert, ever.
- **Money-flow view, two hops:** the alert's edge; who paid the sender and who paid *them*
  (upstream); whom the receiver paid and whom *they* paid (downstream); plus the sender's
  other payees and the receiver's other payers (one hop). A loop shows up when downstream
  reaches back to the sender. Following flow, not every neighbour, keeps hubs from
  exploding the picture.
- **Window:** the 72 hours before the alert (a ring spans a median of 3 days, FINDING-002),
  so early validation alerts reach back into the training window's transactions — read from
  silver (train + validation), never the sealed window.
- **Hub cap:** at most 6 edges per account per direction, the most recent; the rest collapse
  into one "+N more" node carrying the count. Self-transfers (reinvestment rows) are left out
  of the expansion.
- **Precomputed** for the queue's top 20,000 (the explanations' set) into the demo table
  `subgraphs` (one JSON graph per alert: nodes with names and banks, edges with time,
  amount, currency, format, and the stream's score/rank where the edge is a validation
  transaction). **No labels in it** — ring membership is the answer key's, joined only on
  its own tab (S7.8).

**Acceptance criteria**
- [ ] Unit (first): an edge at the alert's minute but later in source order is excluded, an
      earlier one included; nothing after the alert; the cap and "+N more" count are exact;
      upstream/downstream follow the money; a loop back to the sender is kept.
- [ ] Unit: deterministic (same input → identical JSON).
- [ ] Live: for all 20,000 graphs, every edge is before its alert (checked in SQL on the
      stored JSON); no graph has more than the cap allows; no node or edge carries a label.
- [ ] Measured: graph sizes (median, p95, max edges), build time and memory, table size.

**Done 2026-11-22.** `demo/subgraph.py` (`EdgeIndex` + `subgraph()`), demo table `subgraphs`
(20,000 JSON graphs, 32 MB). Live, over all 20,000: **no edge at or after its alert** in
(time, source_row) order (checked in SQL on the stored JSON), no label anywhere, under the cap's
ceiling. Sizes: median 12 edges / 6 accounts, p95 29, max 52; 70.5% of graphs carry a "+N more".
**Does the picture show the ring?** For the 340 laundering alerts in the top 5,000 whose ring
has earlier validation hops, the graph shows at least one of them 74.4% of the time, a median of
73% of them (earlier hops in the training window are not counted: the answer key holds
validation only). Build 86 s, peak 2.4 GB (from 2.8: arrays instead of 2.2M-element lists).
Two of my own edits had silently not applied (a replace after reformatting): one `LOADED`
list now drives both the TRUNCATE and the reader's grants, with a test.

## S7.6 — A small read API

**As** the frontend, **I want** one small read-only API, **so that** the browser never touches
the database and every number on screen has one source.

**Design.**
- `graphguard/demo/api.py` (FastAPI, one uvicorn worker) over a query layer
  (`demo/queries.py`) that only ever connects as **`demo_reader`** — plus one write path,
  the verdict, as **`demo_writer`** (INSERT into `verdicts`, nothing else). The owner's
  password never reaches the container: it gets `.secrets/demo-api.env` (reader + writer
  only), derived from `demo-db.env`, registered, refreshed by `rotate-pg demo_reader|writer`.
- Container `graphguard-demo-api` in docker-compose, from the serving image (new tag
  0.1.13 carrying `demo/`), **127.0.0.1:8130 only** (private, D4: ssh tunnel like MLflow),
  read-only root, no capabilities, non-root 10001, pids-limited, **256 MiB cap** (D3),
  log rotation — the compose hardening test applies unchanged.
- Endpoints (GET unless said):
  `/api/meta` (build, model, window, banner text) · `/api/capacity?per_day=N` (the four
  rankings at k = N × 2.11) · `/api/capacity/curve` (sampled, for the chart) ·
  `/api/queue?per_day=N&page=P` (alerts within k, grouped by sending account, best rank
  first, due time = alert + 24 h) · `/api/alerts/{id}` (the transaction, names, rank and
  percentile — never "chance" —, the three reasons, every contribution, rule hits in words,
  both accounts' recent history, the ring, past verdicts) · `/api/alerts/{id}/answer` (the
  answer key: laundering or not, ring type and its other hops — a separate path so the agent
  can be denied it) · `/api/performance` (measured offline at k; confirmed so far from the late
  labels, with the share still unknown) · `/api/live` (server-sent events: the window replayed
  in order, a few per second) · **POST** `/api/alerts/{id}/verdict` (escalate / close + note).
- **Defences:** per-client rate limit (reads 20/s, verdicts 1/s), at most 4 open live
  streams, JSON-only writes (a cross-site form cannot post), strict security headers (CSP,
  no framing, no sniffing, no referrer), no server banner, every input validated.
- "Estimated live performance" (score-based, no labels) is **not** shown: our scores are not
  calibrated probabilities (training weighted laundering ~1,326×), so such an estimate
  would be wrong by construction. Drift and estimation are Phase 8's (monitoring).
- The demo build also copies the late labels (stream `labels` → demo `labels`) so the
  "confirmed so far" layer has its data.

**Acceptance criteria**
- [ ] Unit (first, FastAPI TestClient on a fake query layer): every endpoint's shape; k from
      per-day (clamped 1..5,000); headers present on every response; rate limit returns 429;
      the 5th live stream is refused; a form-encoded verdict is refused, a bad verdict is 422.
- [ ] Unit: the API module does not import polars, numpy or xgboost (memory).
- [ ] Live (against the real demo DB): queue at 100/day groups 211 alerts by account in rank
      order; an alert's detail has 3 reasons and a ring; `/answer` agrees with `truth`;
      capacity at k = 5,000 says 542 / 127; a verdict lands in `verdicts`.
- [ ] Container: up, healthy, **memory measured under the 256 MiB cap**, reachable only on
      127.0.0.1:8130; `test_compose_hardening` passes; `just demo-api-up | down | logs`.
- [ ] The demo API is never given the owner password or any non-demo secret (test on the
      env file's keys).

**Done 2026-11-22.** `demo/queries.py` (reader pool + one writer connection) and
`demo/api.py` (FastAPI): meta, capacity (+ curve), queue grouped by account, alert detail,
answer key (own path), performance (measured + confirmed so far; no score-based "estimate" —
our scores are not calibrated), live SSE, and the verdict (JSON only). Container
`graphguard-demo-api` on its own image tag (**0.1.14**: API changes never roll the pods), 127.0.0.1:8130 only, **45 MiB of a 256 MiB cap**,
hardening test unchanged; scorer, consumer and shadow rolled to 0.1.13 (72 health probes in
6 minutes, none failed — the probe cannot see a missing pod, k8s-check covers that), old tags
pruned. Tests: 15 unit (headers, limits, 415/422, busy stream, no heavy imports) + 6 live
(211 alerts / 190 accounts at 100 a day, 542 / 127 at 5,000, a verdict lands, the env file
holds only reader + writer). I wrote the API before its unit tests — against this file's own
rule; the tests then found a real bug (a bad verdict was a 500, now 422).
**Incident (mine):** starting the container with a bare `docker compose up` (no
`--env-file`) made compose recreate our Postgres with an empty user in its health check —
~1 minute without the database. Fixed at once with the recipe's env file; data intact (both
databases 1,015,300 rows), the consumer restarted twice and resumed exactly at its saved
offset, every health check green. The recipes now pass `--env-file` + `--no-deps`, and a test
fails any compose call in the justfile without it. LuBot not involved (own containers).

## S7.7 — The Queue page, with the slider

**As** a manager, **I want** one screen that shows the work and the trade-off, **so that** I
understand the system in a minute.

**Design.**
- `web/`: **Next.js 16.4.5, Pages Router, static export** (`output: 'export'`), React 19.2.9,
  TypeScript 6.0.3. Pages Router, not App Router: the App Router's export puts inline
  `<script>` tags in every page, which the API's strict CSP (`script-src 'self'`) blocks; a
  test fails the build if any exported HTML carries an executable inline script.
  Served by the demo API from `web/out` (no Node server at all, ADR 0008 D5).
- **Supply chain** like the Python side: exact versions, each **≥ 14 days old** when chosen,
  `package-lock.json` committed, `npm ci --ignore-scripts`, built in our pinned CI image
  (Node 22.23.5) in a capped throwaway container — nothing installed on the box. Few
  dependencies: no CSS framework (CSS modules), no chart library (the one chart is hand-drawn
  SVG); React Flow arrives with S7.8.
- **The page, top to bottom:**
  1. Honesty banner: synthetic data (IBM AMLworld), validation window, the model.
  2. **The slider**: "my team works N alerts a day" (10–1,000, default 100), and the plain
     sentence: *"A team of ~5 working 100 alerts a day catches 167 of 1,083 laundering
     transactions and 35 of 168 rings; it misses 916. Simple rules alone, same workload: 1."*
  3. **The capacity chart**: laundering caught vs alerts a day — system, rules, random —
     with the slider's point marked; a table view of the same numbers beside it (accessible).
  4. **What is confirmed so far**: measured offline (solid), and the late labels known by the
     end of the window, with the share still unknown and the bias note (FINDING-017). No
     "estimated live" line (our scores are not calibrated — S7.6).
  5. **The queue**: the alerts inside the slider's workload, grouped by sending account —
     rank, top-percentile, due time, amount in its own currency, the top reason, rule chips,
     new-account tag; each row opens the case (S7.8).
- Light and dark from the system setting; keyboard-usable; text contrast ≥ 4.5:1, chart lines
  ≥ 3:1 (WCAG 2.2).

**Acceptance criteria**
- [ ] `just web-install | web-build | web-test` (in the CI image); `web/out` produced.
- [ ] Tests (first, Node's built-in test runner — no extra dependency): the sentence builder
      (counts, plural, team size), the per-day ↔ k conversion matching the API's, the chart's
      scales; and a post-build check: no inline executable script in any exported HTML,
      no external URL in any asset, no secret-looking string in the bundle.
- [ ] Live: the page served by the API on 127.0.0.1:8130 renders the slider sentence with the
      API's own numbers (checked by fetching both), and the headers include the CSP.
- [ ] Bundle size recorded; the API's memory unchanged (static files only).

**Done 2026-11-22.** `web/`: Next.js 16.4.5 Pages Router static export (React 19.2.9, TS 6.0.3),
four dependencies + types; **every package in the tree ≥ 14 days old** (`npm install
--before=<today-14d>`, lockfile committed, 30 packages), `npm ci --ignore-scripts`, built in our
CI image in a capped container (`just web-install | web-build | web-test`). The Queue page:
banner, slider + plain sentence, the capacity chart (hand-drawn SVG: 2 px lines, legend + direct
labels, crosshair/tooltip on pointer and keyboard, table view; series colours validated for colour
blindness in light and dark with the data-viz validator), "what we know, and when", the queue
grouped by account. Site 564 KB (JS 440 KB); the API serves it (image 0.1.15: mounts `web/`, not
`web/out`, which `next build` recreates). **Found by the export check:** Next 16's default bundler
(Turbopack) injects an inline script even with the Pages Router — the strict CSP would block it;
built with webpack instead (`next build --webpack`), the check is now green and runs in every
build. CI runs the web tests (no install needed). Live: every page and every asset loads with the
CSP; the sentence built from the live API's numbers reads "…catches 167 of 1,083 laundering
transactions and 35 of 168 rings. It misses 916. Simple rules alone, same workload: 1 transaction
and 0 rings." **Not done: a visual check** — no browser could be run on the box (the safety check
refused a browser container); Lubo looks at it over the tunnel.

## S7.8 — The Case page

**As** an investigator, **I want** an alert opened into everything I need, **so that** I can
decide in minutes.

**Design** (`/case/?id=<event>`):
1. **Header** — rank and top-share (never "chance"), sender → receiver with names and banks,
   amount in its own currency, time, payment format, new-account tag, due time.
2. **Why** — the three plain reasons (S7.4), then a small diverging bar chart of the biggest
   pushes up and down (log-odds, labelled in words: "raises risk" / "lowers risk"), raw
   values one click away; rule hits word for word.
3. **The ring** — React Flow 12.12.1 + dagre 3.1.3 (both ≥ 14 days old), laid out **left to
   right in time**; accounts as nodes (name, bank; sender and receiver marked), transactions
   as edges labelled with amount and currency; the alert's edge emphasised; "+N more" nodes
   for capped hubs. **Play** reveals the money in time order (off when the reader prefers
   reduced motion). A table of the same transactions beside it (accessible, and for people
   who find graphs hard — Quantexa's own users said so).
4. **History** — both accounts' recent payments in the window.
5. **Answer key** — closed by default, its own button and its own API path: was it
   laundering, which ring type, which of the drawn transactions belong to the ring
   (highlighted when opened). Labelled as what a bank would *not* know on the day.
6. **Verdict** — escalate / close with a note, saved to the audit table; past verdicts listed.
7. The agent's report slot (filled by S7.10).

**Acceptance criteria**
- [ ] Unit (first, Node runner, no install): graph → flow nodes/edges (ids, roles, the alert
      edge marked, "+N more" nodes), the time order for Play, plain feature names for all 15,
      the contribution bars' split into up/down and their scale.
- [ ] The diverging pair validated with the data-viz validator (light and dark).
- [ ] Build: export check still green (no inline script; React Flow's CSS is a file).
- [ ] Live: `/case/?id=` for a top alert loads; its assets load with the CSP; the API calls the
      page makes (`/api/alerts/{id}`, `/answer` only on click, `/verdict` POST) answer.
- [ ] Keyboard: every control reachable; the graph has a table equivalent.

**Done 2026-11-22.** `/case/?id=`: header (rank, top-share, names, banks, amount in its own
currency, format, due), **Why** (three reasons, rule hits verbatim, a diverging bar chart of the
eight biggest pushes — red raises / blue lowers, the pair validated for colour blindness in both
modes, direction also said in words — raw numbers one click away), **the money around it**
(React Flow 12.12.1 + dagre 3.1.3, both ≥ 14 days old; left to right in time; Play reveals the
payments in time order, off under reduced motion; legend; a table of the same payments as the
accessible view — the canvas itself is hidden from screen readers), the **answer key** behind
its own button and API path (highlights the ring's payments, says a bank would not know this
on the day), the **decision** (escalate / close + note → audit table, past verdicts listed) and
both accounts' recent history. Logic tested in Node (13 tests, no install). Site 832 KB; export
check green. As in S7.7, no visual check could be run here.

## S7.9 — The About page

**As** a hiring manager, **I want** the proof on one page, **so that** I can judge the work in
two minutes.

**Design** (prerendered, readable without JavaScript; live numbers where the API has them):
1. **What it is** in three sentences, and the honesty line (synthetic data, one box, replay).
2. **The architecture**, drawn: CSV → lakehouse (bronze/silver/gold, sealed test window) →
   features → XGBoost (MLflow, S3 by hash) → Kafka replay → consumer on k3s (live features in
   Redis, model in process, rules) → Postgres decisions → demo copy → this API → these pages.
3. **The result against the baselines** — PR-AUC and laundering caught at 5,000 for the model,
   rules, by-amount, random, and the GNN that lost (FINDING-007), from the evaluation records.
4. **The findings that shaped it** — one line each, linked to `docs/findings.md`: the ring is
   in the shape not the row, stale features cost 83%, the GNN lost, rules barely work here,
   labels arrive late, weekday is a simulator artifact.
5. **The leakage contract** in five lines, and how it is enforced (the three guards).
6. **Model risk, SR 26-2's headings** (April 2026, guidance): purpose, data, limits,
   monitoring, validation — and that the LLM agent sits outside its scope.
7. **Limits, said plainly** and links (repo, findings, ADRs).

**Acceptance criteria**
- [ ] Every number on the page is either fetched from the API or copied from a committed
      analysis file — a test compares the page's static numbers with those files.
- [ ] The export check allows plain links to other sites (navigation) but still fails on
      anything *loaded* from another host.
- [ ] Prerendered: the key text is in the exported HTML (works without JS).

**Done 2026-11-22.** `/about/`: what it is + the honesty line, the architecture drawn (offline
row and live row, the model loaded at start with its hash checked), the result against the
baselines (XGBoost 0.28155 · GNN 0.04470 · rules 0.00186 · by amount 0.00170 · random 0.00103;
542 / 21 / 7 caught at 5,000), six findings with links, the leakage contract, model risk under
SR 26-2's headings, links. Every fixed number lives in `web/lib/aboutNumbers.json` with its
source, and `test_about_numbers.py` checks each against the committed analysis files.
Prerendered (live test: the key text is in the HTML). The export check now allows plain links
(navigation) and still fails on anything loaded from another host.

## S7.10 — The investigator agent, with a measured error rate

**As** an investigator, **I want** a draft case report I can check, **so that** I save time
without trusting a black box.

**Model (D6, decided 2026-11-22):** NVIDIA NIM's free tier (PLAN.md), OpenAI-compatible
endpoint, a tool-calling model chosen from the live catalog at run time and recorded with
every result. The key is `.secrets/nim.env`, registered, **typed by Lubo** (`just secret-set
nim.env`) — the one step of this phase that needs him. Rate limits are unpublished (~40/min
reported), so the runner paces itself.

**Design.**
- **Tools** (`graphguard/agent/tools.py`, also served over **MCP** by `agent/mcp_server.py`):
  `get_alert`, `get_ring`, `get_history`, `get_reasons` — read-only, through `demo_reader`,
  **never the answer key** (a test proves no tool can reach `truth` or `/answer`).
- **Structured report:** a short summary, a proposed ring type (one of AMLworld's eight, or
  "none evident"), and claims — each claim cites transaction ids and may carry an amount, a
  time, a count or a relation.
- **The checker** (`agent/checker.py`, deterministic): a claim is *supported* only if every
  cited id is in the evidence the tools returned, every amount/time/relation matches a cited
  record, every count equals what it counts, and every number in its prose appears in a cited
  record. Anything else is *unsupported*.
- **The template baseline** (`agent/template.py`): the same report shape built by code from the
  reasons and the ring's shape — supported by construction; its ring-type guess is a shape
  heuristic. The LLM must beat it on ring type to earn its place; published either way.
- **Eval set** (`docs/analysis/s7.10-evalset.json`): 64 validation alerts from the top 5,000 —
  5 per ring type (40, stratified, seeded) + 24 clean alerts (expected: "none evident").
  Ids only; the expected type comes from the answer key, which the agent never sees.
- **Metrics:** unsupported-claim rate **before** the checker (the LLM's real error rate, with a
  Wilson 95% interval) and **after** (gate: zero — the checker drops what it cannot support);
  ring-type recall on the 40; "none evident" rate on the 24; latency. Logged to MLflow.
- **On the Case page:** the agent's checked report, every claim linked to its transactions,
  dropped claims shown as dropped. The agent drafts; the person decides.

**Acceptance criteria**
- [ ] Unit (first): the checker on hand-built reports (a wrong amount, an uncited id, a made-up
      number in prose, a wrong count → unsupported; correct ones → supported); the template is
      100% supported on real alerts; tools cannot reach the answer key.
- [ ] Baseline measured on the eval set **now** (no key needed): ring-type recall, none-evident
      rate, 0 unsupported.
- [ ] With the key: the LLM run on all 64; both rates and the comparison published in
      `docs/analysis/s7.10-agent.json` and a FINDING, whatever they say.

**In progress 2026-11-22 — the half that needs no key is done.** `agent/checker.py` (12 tests:
wrong amount / currency / time / direction / count, uncited ids, invented numbers in prose →
unsupported; Wilson intervals), `agent/tools.py` (read-only; a test parses the code and finds no
path to the answer key, and a live spy shows the tools only ever call the alert view),
`agent/template.py` (the baseline), `agent/evalset.py` → `docs/analysis/s7.10-evalset.json`
(64 cases: 5 per ring type + 24 clean, seeded). **Baseline measured**
(`docs/analysis/s7.10-baseline.json`): 149 claims, **0 unsupported** (95% CI 0–2.5%) — after the
baseline exposed a real checker bug (numbers inside account names, "Corporation #35871", were
read as invented amounts; test + fix); ring type right **7 of 40**; "none evident" right on
**11 of 24** clean alerts. That is the bar. `nim.env` is registered as an optional secret
(health stays green until it exists) and `just secret-set nim.env` takes it, format-checked,
nothing printed. **Waiting on Lubo for the key**; then: the MCP server, the LLM runner, the run
on all 64, `s7.10-agent.json`, a FINDING, and the report on the Case page.

## S7.11 — The test on a real person (the Phase 7 gate)

**As** Lubo, **I want** a non-technical person to use it, **so that** "it is clear" is
measured, not assumed.
- One session with someone who does not know what a model is — **Lubo's wife**: the tester
  gets the Queue page and no explanation. Written down: what they say the system does,
  what they would do next, where they got stuck. Fixes from it, then the gate is marked.

Out of scope for Phase 7: a public URL (separate step, LuBot session first), logins and
roles for many users, live re-scoring, money totals, a manager operations dashboard with
simulated SLAs. The video is Phase 8b.
