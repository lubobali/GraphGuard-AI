# Leakage audit — Phase 3 tabular baseline

Required by the Phase 3 gate: every top feature justified in writing, and
anything suspiciously strong traced back to its source. Contract rule 5: a
feature that looks too good gets investigated, not celebrated.

**Model:** XGBoost, 18 features, trained on the frozen training window
(3,046,186 rows), scored on validation (1,015,300 rows). Test still unopened.

---

## Headline result

| | With all features | Artifacts removed | Artifacts removed, tuned |
|---|---|---|---|
| PR-AUC | 0.35991 | 0.24814 | **0.28155** |
| precision@50 | 1.00000 | 1.00000 | 0.96000 |
| precision@100 | 0.98000 | 0.94000 | 0.95000 |
| precision@1000 | 0.37500 | 0.29400 | 0.33200 |
| rings caught @5000 | 146 / 168 | 121 / 168 | 127 / 168 |

**The number this project quotes is PR-AUC 0.28155**, from the tuned
artifact-free model. Tuning was 20 Optuna trials on validation, every trial
logged to MLflow, search space declared in `graphguard.models.search`.

*Caveat, stated rather than buried:* the tuned run used 300 trees and the
untuned one 400, so the two are not perfectly controlled. The tuned model won
with fewer trees, which understates rather than inflates the gain.

Both clear the dumb baselines by a wide margin (random 0.00103, by-amount
0.00170). **The number that should be quoted is 0.248**, not 0.360.

---

## Feature-by-feature justification

Ranked by XGBoost gain on the full model.

| # | Feature | Gain | Verdict |
|---|---|---|---|
| 1 | `payment_format_code` | 45.1% | **ARTIFACT** |
| 2 | `is_cross_currency` | 12.5% | **ARTIFACT** |
| 3 | `sender_distinct_out_before` | 11.1% | legitimate |
| 4 | `is_self_transfer` | 7.4% | **ARTIFACT** |
| 5 | `sender_seconds_since_last_send` | 4.3% | legitimate |
| 6 | `in_out_ratio_before` | 4.0% | legitimate |
| 7 | `amount_ratio` | 1.8% | legitimate |
| 8 | `is_same_bank` | 1.6% | legitimate |
| 9 | `sender_sent_last_24h` | 1.6% | legitimate |
| 10 | `log_amount` | 1.5% | legitimate |

### 1. `payment_format_code` — ARTIFACT, 45.1% of gain

| Format | Rows | Laundering | Rate | Share of all laundering |
|---|---|---|---|---|
| ACH | 599,689 | 3,828 | 0.638% | **84.7%** |
| Cheque | 1,864,331 | 324 | 0.017% | 7.2% |
| Credit Card | 1,323,324 | 206 | 0.016% | 4.6% |
| Cash | 490,891 | 108 | 0.022% | 2.4% |
| Bitcoin | 146,091 | 56 | 0.038% | 1.2% |
| **Reinvestment** | 481,056 | **0** | **0%** | 0% |
| **Wire** | 171,855 | **0** | **0%** | 0% |

85% of laundering is ACH, which is 12% of the data. Two formats covering
653,000 rows contain no laundering at all, so the model can discard 12.9% of
the negative class with certainty.

**Why this is not real.** IBM's generator emits laundering hops almost
exclusively as ACH and never as a wire transfer. Real laundering uses wires
heavily -- correspondent banking and cross-border wires are the classic
layering channel. This feature is learning the simulator, not the crime.

### 2. `is_cross_currency` — ARTIFACT, 12.5% of gain

No laundering row converts currency *within* the row (0.0% vs 1.3% of ordinary
traffic). Laundering chains in this data do hop currencies, but between hops,
never inside one. That is a property of how the generator writes rows.

### 3. `sender_distinct_out_before` — LEGITIMATE, 11.1% of gain

Distinct counterparties the sender has paid before this transaction. Strictly
point-in-time: bounded by `as_of` and excluding the current row, with tests
pinning that an account's first transfer sees zero.

Direction is worth noting: by median, laundering accounts have **fewer**
counterparties than ordinary ones (2 vs 3, FINDING-005). The model is not
learning "busy account is suspicious".

### 4. `is_self_transfer` — ARTIFACT, 7.4% of gain

18% of ordinary traffic is an account paying itself ("Reinvestment"); 0.2% of
laundering is. Same root cause as #1: the generator never emits a self-transfer
as a laundering hop.

### 5-10. Legitimate

`sender_seconds_since_last_send`, `in_out_ratio_before`, `sender_sent_last_24h`
are point-in-time history aggregates, all bounded by `as_of` and excluding the
current row, all covered by tests in `tests/features/test_graph.py`.
`amount_ratio`, `is_same_bank` and `log_amount` are row-level: every value comes
from the transaction being scored, so there is no future to see.

---

## Leakage checks performed

| Check | Result |
|---|---|
| Split is temporal, frozen, checksum-guarded | pass |
| Feature builders bounded by `as_of` | pass, enforced by `leakage_guard.py` |
| Aggregates exclude the current row | pass, pinned by test |
| Label column absent from the feature matrix | pass, pinned by test |
| Category encodings fitted on training window only | pass, pinned by test |
| Test window never loaded | pass, enforced by `test_set_touch_check.py` |
| Any single feature dominating | **investigated -- three artifacts found** |

---

## What must be said in the write-up

The three artifact features are **not leakage**. All three are knowable at
decision time and a real bank would have them. They are worse in a different
way: they are properties of IBM's simulator that would not hold in real data,
so a model leaning on them would not transfer.

Phase 8 must state plainly that the defensible number is **PR-AUC 0.248 with
the artifacts removed**, and that the 0.360 figure is inflated by the generator.

Phase 4's GNN must be compared against **the artifact-free tabular model**, or
the comparison is rigged in the GNN's favour.
