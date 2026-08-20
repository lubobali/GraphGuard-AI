# Findings

Things measured in this data that change how the project must be built. Each
one is dated, evidenced, and names the phase that has to act on it.

---

## FINDING-001 — The last 8 days are majority-laundering

*Found: 2026-08-19, Phase 0. Acts on: Phase 2 (the split).*

HI-Small is documented as covering **Sep 1-10, 2022**. The file actually runs
to **Sep 18**. The dataset author acknowledges this in the Kaggle discussion and
describes the extra transactions as "all laundering".

Measured, they are not all laundering, but they are close enough to be
dangerous:

| Period | Transactions | Laundering | Rate |
|---|---|---|---|
| Sep 1-10 | 5,077,237 | 4,522 | 0.03% - 0.21% per day |
| Sep 11-18 | 1,108 | 655 | **57% - 73% per day** |

**The trap.** The tail is 0.02% of all rows but holds **12.6% of every positive
example in the dataset**. A temporal split that puts the tail in the test window
produces a test set that is majority-positive. Precision@k against it would look
extraordinary and mean nothing.

**What must happen in Phase 2.** The split is by time (leakage contract rule 1),
so this cannot be dodged by splitting on row count. The options, to be decided
and written down before the split is frozen:

1. Truncate the dataset at the documented end of the period (Sep 10) and discard
   the tail. Loses 12.6% of positives.
2. Keep the tail but exclude it from evaluation, treating it as a known artefact
   of the generator rather than as transactions.
3. Keep it and report metrics both with and without it.

Whichever is chosen, the reason goes in the README. A reviewer who knows this
dataset will look for it.

**Reproduce:** `just data-summary` shows the 17-day range against the documented
10. Per-day rates come from grouping on `timestamp.dt.date()`.

---

## FINDING-002 — The highest-degree accounts are hubs, not criminals

*Found: 2026-08-19, Phase 1. Acts on: Phase 3 (features), Phase 4 (the model).*

Degree distribution over the 5,078,345 transfers between 515,080 accounts:

| Percentile | Degree |
|---|---|
| 50% | 6 |
| 75% | 27 |
| 90% | 51 |
| 99% | 119 |
| max | 169,756 |

Most accounts are tiny: half make six transfers or fewer across the whole
18-day window. The distribution then has an extreme tail.

The five largest senders are all at one bank, **Oasis Thrift**, and the
accounts file labels them as small entities:

| Account | Sent | Labelled | Laundering rate |
|---|---|---|---|
| 100428660 | 168,672 | Sole Proprietorship #41 | 0.14% |
| 1004286A8 | 103,018 | Partnership #2370 | 0.15% |
| 100428978 | 20,497 | Sole Proprietorship #36613 | 0.14% |

A sole proprietorship sending 168,672 transfers in 18 days is one every nine
seconds. These are hub or settlement accounts in the generator, not one-person
businesses.

**Why it matters.** Their laundering rate matches the dataset base rate of
0.102%. The most connected accounts in the data are unremarkable. Any feature
built on raw degree - "this account sends to many others" - will rank these
first and bury real cases. Degree has to be normalised, or the hubs handled
explicitly, before it is usable.

This is also the first concrete argument for the graph model: what separates
laundering here is not how *much* an account transacts but the *shape* it
transacts in.

**Reproduce:** `degree_summary()` in `graphguard.analysis.graph_stats`, and
grouping the transactions by `from_account`.

---

## FINDING-003 — 38% of laundering is not in any labelled pattern

*Found: 2026-08-19, Phase 1. Acts on: Phase 2 (metrics), Phase 8 (the write-up).*

`HI-Small_Patterns.txt` contains **370 laundering attempts** covering **3,209
transactions** in 8 shapes:

| Shape | Attempts | Transactions | Avg size |
|---|---|---|---|
| CYCLE | 54 | 287 | 5.3 |
| GATHER-SCATTER | 51 | 716 | 14.0 |
| BIPARTITE | 49 | 263 | 5.4 |
| FAN-OUT | 48 | 342 | 7.1 |
| SCATTER-GATHER | 44 | 626 | 14.2 |
| STACK | 43 | 466 | 10.8 |
| RANDOM | 41 | 191 | 4.7 |
| FAN-IN | 40 | 318 | 8.0 |

The transactions file marks **5,177** transactions as laundering. So:

- **3,209 (62%)** belong to a labelled ring
- **1,968 (38%)** are laundering but in no labelled pattern

**Why it matters.** Pattern-level recall - "did we catch the whole ring, not one
hop of it" - can only be computed over the 62%. Reporting it as though it covers
all laundering would overstate what is being measured. Phase 2 must state the
denominator explicitly, and Phase 8 must say so in the write-up.

The dataset author notes this: not all laundering follows one of the 8 AMLSim
patterns.

**Ring shape, measured:**

| | Median | Max |
|---|---|---|
| Transfers per ring | 6.5 | 32 |
| Accounts per ring | 8 | 45 |
| Days end to end | 3.1 | 8.4 |

A ring is small and slow: about 8 accounts over 3 days. Every individual hop is
an ordinary transfer for an ordinary amount - the examples inspected by hand
were EUR 10,476, USD 15,471, EUR 12,196. Nothing in a single row is unusual.

**This is the project's core argument, now measured rather than asserted:** the
signal does not exist in any single row. It exists in the relationship between
rows, spanning a median of 8 accounts. A row-level model cannot see it, because
there is nothing there to see.

**Reproduce:** `parse_patterns()` in `graphguard.analysis.patterns`.

---

## FINDING-004 — The dumb baselines fail, so the data is not trivially easy

*Found: 2026-08-19, Phase 2. Acts on: Phase 3 and 4 (every comparison).*

Both baselines scored on **validation** (1,015,300 rows, 1,083 laundering, 168
labelled rings). Test remains sealed - contract rule 4.

| | PR-AUC | p@500 | p@5000 | Best lift | Rings caught |
|---|---|---|---|---|---|
| base rate | 0.00107 | - | - | 1.00x | - |
| random | 0.00103 | 0.000 | 0.0002 | 0.19x | 0 / 168 |
| by amount | 0.00170 | 0.002 | 0.0020 | 1.87x | 0 / 168 |

**The harness sanity-checks out.** A random ranking should score exactly the
base rate in PR-AUC. It scores 0.00103 against a base rate of 0.00107. That is
evidence `evaluate()` is not quietly wrong, which matters more than the
baseline numbers themselves.

**Ranking by amount does not work.** PLAN.md flags the risk that the synthetic
patterns might be too obvious - "if rank by amount already does well, the
simulator's patterns are too obvious and we switch to the LI variants". It does
not do well: best lift 1.87x, and not one of the 168 rings caught. **The project
stays on HI-Small.**

This is consistent with FINDING-003: laundering hops are ordinary amounts. The
hand-inspected examples were EUR 10,476 and USD 15,471, indistinguishable from
ordinary business transfers. A size-based ranking has nothing to grip.

**The floor every later model must clear:** PR-AUC 0.0017, and any ring at all.

---

## FINDING-005 — Two features look too good, and both are probably artifacts

*Found: 2026-08-20, Phase 3. Acts on: Phase 3 leakage audit, Phase 8 write-up.*

Median feature values by class over the training window (medians, not means -
means here are dominated by the hub accounts of FINDING-002):

| Feature | Normal | Laundering |
|---|---|---|
| distinct counterparties so far | 3 | 2 |
| sends in last 24h | 3 | 2 |
| log amount | 7.33 | 8.85 |
| **is_self_transfer** | **18.0%** | **0.2%** |
| **is_cross_currency** | **1.3%** | **0.0%** |

**Laundering accounts are less busy, not more.** By median they have fewer
counterparties and fewer recent sends than ordinary accounts. The intuition
that launderers are hyperactive is wrong in this data, and any feature built on
that assumption will point the wrong way.

**The two flagged features.** Contract rule 5 says a feature that looks too good
gets investigated rather than celebrated. Neither is leakage - both are known at
decision time - but both look like properties of the generator rather than of
laundering:

- `is_self_transfer`: 18% of ordinary traffic is an account paying itself
  ("Reinvestment" rows). The generator appears never to emit a self-transfer as
  a laundering hop. A model can therefore exclude 18% of the negative class for
  free.
- `is_cross_currency`: no laundering row converts currency *within* the row.
  Laundering chains do hop currencies, but between hops, never inside one.

**What must happen.** The Phase 3 leakage audit has to report feature importance
with and without these two. If the model's performance collapses without them,
the result is an artifact of the simulator and must be reported as such. Phase 8
must say plainly that these two would not exist in real bank data.

**Reproduce:** group the training split by `is_laundering` and take medians of
the columns from `graphguard.features.basic` and `graphguard.features.graph`.

---

## FINDING-006 — 85% of laundering is ACH, and Wire contains none at all

*Found: 2026-08-20, Phase 3. Acts on: Phase 4 comparison, Phase 8 write-up.*

`payment_format` alone carries 45% of the tabular model's gain. The reason:

| Format | Rows | Laundering | Share of all laundering |
|---|---|---|---|
| ACH | 599,689 (11.8%) | 3,828 | **84.7%** |
| Reinvestment | 481,056 | **0** | 0% |
| Wire | 171,855 | **0** | 0% |

IBM's generator emits laundering hops almost exclusively as ACH and never as a
wire transfer. Real laundering uses wires heavily; correspondent banking is the
classic layering channel. The feature is learning the simulator, not the crime.

**Measured impact.** Retraining without `payment_format`, `is_cross_currency`
and `is_self_transfer`:

| | With | Without |
|---|---|---|
| PR-AUC | 0.35991 | **0.24814** |
| precision@1000 | 0.375 | 0.294 |
| rings caught @5000 | 146/168 | 121/168 |

**The model does not collapse.** It loses about 31% of PR-AUC, which is real
and must be reported, but 0.248 is still 146x the by-amount baseline and still
catches 121 of 168 rings. The artifacts inflate the result; they do not
manufacture it. The remaining signal comes from the point-in-time history
features.

**The number this project quotes is 0.248**, and Phase 4's GNN is compared
against the artifact-free model. Full audit in `docs/leakage_audit.md`.
