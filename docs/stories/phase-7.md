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

Today every soak, e2e and chaos run truncates the stream tables, and the only database
login can write.

- [ ] A `demo` schema built from the soak's validation decisions: one command
      (`just demo-build`) copies decisions, joins what the UI needs (currencies, banks,
      payment format, account names — D8) and adds indexes for the queue's sorts. Stream
      resets do not touch it (test: run `db.reset()`, the demo is unchanged).
- [ ] A **SELECT-only** role `demo_reader` on the `demo` schema only, through
      `pg_access.SERVICES` (registry entry, rotation, backup covered automatically). Live
      test: it cannot write, cannot read `stream` tables, cannot read other databases.
- [ ] The verdict table (D7) is the only writable table, owned by a separate `demo_writer`
      role used only by the API's verdict endpoint.
- [ ] Rebuilding is deterministic: same inputs → same rows (hash in the build output).
- [ ] Postgres stays under its cap (measured before/after).

## S7.2 — The ring list in the lakehouse, with the test window sealed

**As** the leakage contract, **I want** ring labels in the lakehouse split like the
transactions, **so that** the UI and the agent can never see a test-window ring.
- Rings from the patterns file → `gold.rings` (train + validation) and `sealed.rings`
  (test). `test_set_touch_check` extended to catch raw patterns/CSV reads past
  validation. A test proves the API never returns a test-window ring.

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
