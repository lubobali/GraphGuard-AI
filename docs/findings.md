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
