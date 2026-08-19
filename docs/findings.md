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
