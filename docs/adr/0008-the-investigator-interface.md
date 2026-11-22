# ADR 0008 — The investigator interface: what one alert is, who works it, how it is shown

**Status:** accepted, 2026-11-22 (S7.0)
**Decided by:** Lubo approved the Phase 7 stories and asked for these choices to be made for
him ("make it look real"). Research: `docs/research/AML investigator interface research
2026.md` (notes beside it).

## Context

Phase 7 turns the evaluation into screens a non-technical person can use (PLAN.md gate: a
real person, tested — Lubo's wife). Real AML case managers (Oracle FCCM, Unit21, Lucinity,
Flagright, Hawk, NICE Actimize) share one shape: work queues sorted by due date then risk,
alerts rolled up per customer, plain-language reasons, every decision logged. Managers read
backlog and counts, not AUC; lay readers misread confusion matrices (Shen et al., CSCW 2020).

The numbers the screens rest on (validation window, `docs/analysis/s6.8-rules.json`):

| | |
|---|---|
| Transactions / laundering | 1,015,300 / 1,083 |
| Model, top 5,000 | 542 laundering caught, 541 missed; 127 of 168 rings caught (≥ half their hops), 140 touched (any hop) |
| Rules, top 5,000 | 21 caught |
| Alert line (ADR 0007) | 5,000 per ~50.6 h of traffic ≈ 2,370 a day |

## Decisions

**D1 — One alert is one transaction; the queue groups alerts by sending account.**
Options: per transaction, per account, per case (connected alerts). The model was trained and
evaluated per transaction, so the numbers stay true only at that unit; vendors show one line
per customer, so the queue groups by sender with the count and the top alert. Per-case
grouping needs entity resolution we do not have. *Change if:* a case-level model is trained.

**D2 — The demo team works 100 alerts a day.**
The ADR 0007 alert line (≈2,370/day) is the evaluation's k (5,000 per window), not a team.
100/day matches the late-label simulator (S6.9) and ~20 alerts per analyst per day (industry
illustration), i.e. about five investigators. The slider still covers 1-5,000.
*Change if:* a real team size is known.

**D3 — Keep Ray Serve; the shadow pod runs only while comparing; the new API fits ~256 MiB.**
GraphGuard measures ~4.1 GiB against its ~4 GB budget; the scorer is ~2.0 GiB of it, and the
stream no longer calls it. Replacing it with plain FastAPI would save ~1 GB (estimate, ADR
0001) but removes a Phase 5 deliverable that hiring managers look for, while the box has
~20 GiB available. Cheaper: shadow at 0 replicas when idle (~200 MiB), a small API, a static
frontend (0 MiB). *Change if:* the measured total after S7.6 is over budget.

**D4 — Private demo first; public later, separately.**
Reached over the ssh tunnel like MLflow; the demo video carries it to the world. A public
URL on the box that runs LuBot production needs a box-wide change (web server, TLS) through
the LuBot session and a security review. *Change if:* Lubo wants a public link (own story).

**D5 — Next.js static export + React + TypeScript + Tailwind; React Flow for the ring;
a small FastAPI read API.**
Static files need no Node server (no memory; none of 2026's Next.js server-side advisories
apply). React Flow (MIT, ~88 KB gzip) draws custom account nodes and animated edges; dagre
lays the ring out left to right by time. FastAPI already exists in the stack and has
built-in server-sent events for the live feed. PLAN.md's "same stack as LuBot's frontend"
is read as React/Next.js — LuBot's code is off limits to this project, so not checked.
*Change if:* a page needs server rendering (none planned).

**D6 — The agent's model is chosen at S7.10.** PLAN.md names NVIDIA NIM; its 2026 status is
checked then. A key, if needed, gets a secrets-registry entry and Lubo types it himself.

**D7 — The case page records a verdict (escalate / close + note) in an audit table.**
Real tools log every decision (four-eyes, audit trail). Verdicts never feed training
directly; labels only reach learning through `labels.known_as_of` (FINDING-017).

**D8 — Show the synthetic account names** (bank + entity from the raw accounts file).
"Corporation #4421 at Bank 70" reads like a queue; hex IDs do not. Still synthetic, and the
page says so.

## Rules that follow (for every Phase 7 story)

- Every page says: synthetic data (IBM AMLworld), validation window, date.
- Counts, not percentages, as the main language; PR-AUC only on the About page.
- **No money totals**: amounts are in 15 currencies with no exchange rates.
- The score is shown as rank/percentile, never as a chance (training weighted laundering
  ~1,326×, so 0.23 is not 23%).
- The ring shows only edges **before** the alert (leakage rule 2 applies to pixels); the
  true ring type is an "answer key" tab the agent never sees.
- Model-risk wording follows **SR 26-2** (Apr 2026, replaced SR 11-7 and SR 21-8): guidance,
  not law; it covers the model, not the rules, and leaves generative AI out of scope.

## Consequences

- S7.1 needs a durable demo copy (stream resets truncate the live tables) and a SELECT-only
  role; S7.2 moves the ring list into the lakehouse with the test window sealed.
- The slider and queue numbers are reproducible from `evaluate()` alone.
- If D3's measurement fails, ADR 0001 is reopened, not worked around.
