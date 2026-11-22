# Phase 7 — The interface: stories

**Status:** draft 2026-11-22, waiting for Lubo's approval. Research behind it:
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

## S7.0 — The decisions, written down (ADR 0008)

**As** Lubo, **I want** every Phase 7 choice recorded with its reason, **so that** I can
explain each one in an interview and nobody has to guess later.

- [ ] `docs/adr/0008-the-investigator-interface.md`: D1–D8 above, each with the options
      considered, the choice, the reason, and what would change it.
- [ ] PLAN.md Phase 7: "ranked accounts" → D1; "same stack as LuBot" → D5; the change
      recorded under Plan revisions (cause: research 2026-11-22), not applied silently.
- [ ] Stale docs fixed: README "next phase", `pyproject.toml` description (still says GNN),
      CLAUDE.md memory/disk numbers (Postgres cap, MLflow workers, disk free, swap),
      `leakage_audit.md`'s two "numbers to quote", the `k8s/networkpolicy.yaml` header.

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
