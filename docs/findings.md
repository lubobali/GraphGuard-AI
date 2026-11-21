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

**The number this project quotes is 0.282** - the artifact-free model after 20
Optuna trials on validation. Phase 4's GNN is compared against that, with the
same search budget, or the comparison is rigged. Full audit in
`docs/leakage_audit.md`.

---

## FINDING-007 — The graph helps, but the tuned tree still wins by 6x

*Found: 2026-08-20, Phase 4. Acts on: Phase 8 write-up.*

| Model | PR-AUC | Rings @5000 |
|---|---|---|
| random | 0.00107 | 0 / 168 |
| by amount | 0.00170 | 0 / 168 |
| MLP, graph off | 0.01869 | 34 / 168 |
| GraphSAGE | 0.04470 | 60 / 168 |
| XGBoost | **0.28155** | **127 / 168** |

Same features, same split, same `evaluate()`, same 20-trial Optuna budget.

**The graph contributes measurably.** Within the search, 12 trials ran with
message passing on and 8 with it off: best 0.06198 against 0.01869, and 60
rings against 34. Structure is worth about 3.3x over the same features alone.

**The tree still wins by roughly 6x**, consistent with the literature on
gradient-boosted trees versus neural networks for tabular features.

**The largest single effect was `pos_weight`.** Fixed at the exact class ratio
of 1326 -- correct for XGBoost's `scale_pos_weight` -- gradient descent was
destabilised and the GNN scored 0.0075. Optuna chose 6.34 and it improved 8x.
The same number is right for one model class and catastrophic for the other.

**Most likely place a better result hides:** day-granularity snapshots. A
transaction is scored against a graph frozen at the start of its day and cannot
see same-day neighbours, while the tree's features are exact to the second.
Rings take a median of 3.1 days to complete, so much of the structure does not
exist yet at scoring time. A continuous-time model would not have this
handicap. Stated as a known limitation, not a disproven hypothesis.

Full table and caveats in `docs/model_comparison.md`.

---

## FINDING-008 — Cumulative-count features cannot survive a batch-refreshed store

*Found: 2026-08-27, Phase 5. Acts on: Phase 5 design, Phase 6 stream.*

The model was trained on exact point-in-time features and then scored on the
same validation window using features read from a periodically refreshed online
store, which is what production does:

| Policy | PR-AUC | p@1000 | Rings @5000 | vs exact |
|---|---|---|---|---|
| exact (training path) | 0.28155 | 0.332 | 127/168 | — |
| refresh every 6h | 0.04723 | 0.115 | 69/168 | **-83.2%** |
| refresh every 24h | 0.04713 | 0.112 | 68/168 | -83.3% |

**The tell was that 6h and 24h are nearly identical.** If the cost were
proportional to staleness, four times the staleness would not produce the same
number. That similarity is what prompted looking for a mechanism rather than
accepting "staleness is expensive" as the finding.

**The mechanism.** Every history feature here is a **cumulative count that grows
without bound** -- transfers sent, amount sent, distinct counterparties. A stale
count is *systematically too low*, never too high. The whole feature
distribution shifts downward and the model is scoring inputs unlike its training
distribution, which is a different failure from simply having slightly old
numbers.

Measured on the validation window against a snapshot at its start:

| Feature | Mean value | Mean absolute error |
|---|---|---|
| sender_n_sent_before | 6,238 | 1,108 |
| sender_amount_sent_before | — | 375,482,801 |
| sender_sent_last_24h | 1,256 | 18.7 |

The magnitudes come from the hubs in FINDING-002: the largest account makes
168,672 transfers, so six hours of staleness is thousands of missing rows for
it, while the median account with six transfers across 18 days is barely
affected. A dataset with a heavy degree tail is exactly where batch refresh
fails.

**Two false starts on the way here, both recorded because both were nearly
reported as results.** The first measurement zero-filled three features the
serving path did not carry -- `sender_sent_last_24h`,
`sender_seconds_since_last_send` and `payment_currency_code` -- and read as an
87% staleness penalty that was actually a missing-feature penalty. The
measurement now raises rather than zero-fills. The second was a diagnostic
comparing *mean* feature values, which matched to within 1% while individual
rows differed by thousands. Aggregate agreement is not row agreement.

**What this changes.** Periodic batch refresh is the wrong design for these
features. Two directions, to be decided in Phase 5:

1. **Incremental counters.** The stream updates each account's counts as
   transactions arrive, so the store is never behind. This is what Phase 6's
   consumer is already positioned to do, and it makes the stream load-bearing
   rather than a demo.
2. **Bounded features.** Replace unbounded cumulative counts with windowed or
   decayed ones, which are bounded and degrade gracefully when stale.

Direction 1 preserves the measured 0.28155. Direction 2 would require retraining
and re-evaluating, and its ceiling is unknown.

**Reproduce:** `just measure-staleness`.

## FINDING-009 — Bit-identical float features across two engines is not a real target

*Found: 2026-11-18, Phase 5 (S5.6a, the lakehouse). Acts on: every parity check from here on.*

Moving the account features from "computed straight into Redis from the CSV" to
"written to an Iceberg gold table, then loaded into Redis" was checked account by
account against the live store. The first comparison found **23,384 of 512,705
accounts different**. Every count, every timestamp and every date matched
exactly; only the two money sums differed, and by at most **2.8 × 10⁻¹⁶
relative** -- the last bit of a 64-bit float.

**Two causes, peeled apart one at a time.**

1. **Row order.** Float addition is not associative, and the CSV is not
   time-sorted, while the lakehouse stored rows by day. Fixed properly: bronze now
   keeps each row's position in the source file (`source_row`, which is also the
   transaction key the dataset never had), and every aggregation reads in that
   order. With it, the **training and validation feature frames built from silver
   are bit-identical to the CSV path** -- 3,046,186 and 1,015,300 rows -- and
   23,384 differing accounts became 62. A unit test reproduces the order effect
   with values chosen so that `0.1 + 0.7 + 0.2 + 1e16 + 0.3 - 1e16 + 0.6` depends
   on the order, and fails without the fix.
2. **Parallel chunking.** The last 62 survive with identical rows in identical
   order. Polars aggregates in parallel and combines partial sums per chunk; a
   CSV scan and an Iceberg scan are chunked differently, so a handful of sums
   round differently. Each path is deterministic run to run; they just do not
   agree with each other in the last bit. A hypothesis that the pattern join
   reordered rows was tested and was wrong.

**What decides it is the model, not the bits.** The store was reloaded from gold
and 2,000 real validation transactions were rescored through the live k3s
endpoint: **2,000 of 2,000 identical** -- score and both cold flags -- maximum
difference **0.0**. A 1-ulp difference can only change a tree's output if a value
sits exactly on a split threshold.

**The rule this leaves.** Parity checks across engines compare integers and
timestamps exactly and floats to a stated tolerance, and are gated on what the
model actually outputs. Order is still preserved, because it removed 99.7% of the
differences for free, and because "same order" is what makes a rebuild from the
same snapshot reproducible. Within one engine, rebuilds are exact: rebuilding the
lakehouse from the same CSV gave tables identical to the previous build, read
back through Iceberg time travel.

## FINDING-010 — "Before" means time, then arrival order: 9.4% of transactions tie

*Found: 2026-11-18, Phase 5 (S5.6b, DuckDB over the lakehouse). Acts on: every SQL or
stream implementation of a history feature, and Phase 6's replay order.*

Timestamps in AMLworld have **minute resolution**, and many accounts send several
transfers in the same minute. Training's history features sort by time and keep
the source file's order for ties (`cum_count() - 1` after a stable sort), so the
second of two same-minute transfers counts the first as "before". That is a real
definition: it treats file order as arrival order.

The natural SQL way to write the same feature -- an ASOF join on "strictly earlier
in time" -- treats same-minute transfers as simultaneous. Measured over all
4,061,486 silver transactions, that version disagrees with training on:

| Feature | Rows that would differ |
|---|---|
| `sender_n_sent_before` | **381,911 (9.4%)** |
| `receiver_n_received_before` | 100,534 (2.5%) |

Nothing would have failed. The SQL would have looked correct, and the features it
produced would have quietly differed from what the model was trained on -- the
exact train/serve skew this project exists to prevent.

**The fix uses `source_row`** (added for FINDING-009): DuckDB orders by
(timestamp, source_row), the same tie-break as training. With it, both counts match
training **on all 4,061,486 rows**. A regression test keeps the strictly-earlier
version around solely to show that it disagrees on a tie.

**What it means for Phase 6.** The replayed stream must deliver same-minute
transfers in source order, or the online features will not match training.

**A second, smaller thing found on the way.** Money sums agree bit for bit on 2.7M
rows and within 8.9 × 10⁻⁸ relative on the rest. That gap is larger than the 1-ulp
noise of FINDING-009, and the cause is in training's formula, not DuckDB's:
training computes `cum_sum() - amount_paid` ("running total including me, minus
me"). When `amount_paid` is huge, subtracting it back loses the low digits of the
remainder. DuckDB sums only the earlier rows, so it is the more precise of the two.
The model is unaffected at this scale; changing training's formula would mean
retraining, which is its own decision.

---

## FINDING-011 — Bronze holds the test window, so locking `sealed` alone is a hollow lock

*Found: 2026-11-18, Phase 5 (S5.6d, writing the access policy). Acts on: every grant,
view or export over the lakehouse.*

S5.6a put the test window in its own namespace, `sealed`, and a guard fails the build
if code outside two files names it. S5.6c added "`sealed` is never exposed to SQL" as
an acceptance criterion, and it held: no view named `sealed` existed.

But `bronze.transactions_raw` is the **raw CSV — all 5,078,345 rows, test window
included** — and `just sql` exposed it as the view `bronze_transactions_raw`. Anyone
running SQL could read every test-window transaction with one `WHERE timestamp >= …`.
The guard could not see it, because the code never names `sealed`; the test checked
view *names*, not the rows behind them.

**No result is affected.** Training reads silver (train + validation only, verified
as the `trainer` identity: same 4,061,486 rows, same hash), and the test set has never
been scored. This was an open door, not a leak that happened.

**Fix (S5.6d):** `trainer` and `reader` get only `describe` on bronze — its snapshot
id for lineage, no data; `governance.check_plan()` refuses any policy that gives them
more, and refuses any warehouse-level grant (it would inherit down into `sealed`).
`just sql` no longer creates a bronze view, and a test asserts **no SQL view returns a
row at or after the validation end** — checking the rows, not the names.

**Lesson:** protect the *data*, not the *name*. The test window lives in two places
(bronze and sealed), and every access rule has to cover both.

---

## FINDING-012 — `.gitignore`'s `models/` hid the XGBoost training code from git since Phase 3

*Found: 2026-11-18, Phase 5 (S5.6d, a new repo-hygiene test). Acts on: reproducibility
("one command from a clean clone") and every CI result since 2026-08-20.*

The line `models/` (meant for the model-artifact folder at the repo root) matches a
folder named `models` **at any depth**, so it also ignored `src/graphguard/models/`
and `tests/models/`: the tabular pipeline, the Optuna search space, `train_tabular`,
`tune_tabular` and their 19 tests. **None of the 9 files was ever committed.** Lint
skipped them too (ruff honours `.gitignore`), and CI never ran their tests.

CI stayed green because no CI-collected test imported them, although tracked code
does (`build_artifacts.py`, `measure_staleness.py`, `run_gnn.py`). So a fresh clone
could not run `just build-artifacts`, `just train-tabular` or `just tune-tabular`.

It is the same trap as S5.6a's `lakehouse/` line (fixed in S5.6c), found the same way
the second time only because a test now looks for it.

**Fix:** the rule is anchored to `/models/`; the 9 files are committed after a secret
scan, with 5 cosmetic lint fixes (unused imports, long lines; no logic touched); their
19 tests pass. `tests/test_repo_hygiene.py` now fails the build if any `.py` file
under `src/`, `tests/` or `scripts/` is gitignored or skipped by ruff — and was shown
to fail when the bad pattern is put back.

**Results stand.** The Phase 3 numbers came from this code running on the box, logged
to MLflow; what was missing was the published copy, not the experiment.

## FINDING-013 — p99 holds to 150 tx/s on k3s; at 200 tx/s the scorer saturates, and 94% of its CPU is Ray Serve, not the model

*S5.4, 2026-11-19. Raw numbers: `docs/perf/s5.4-latency.json`; MLflow experiment
`graphguard-perf`.*

**How it was measured.** Open loop — each request leaves on a fixed schedule and its
latency counts from when it was *due*, so a stall cannot hide (no coordinated omission).
From a load-generator pod inside k3s, calling the scorer's Service by name: the path the
Phase 6 stream will use. 2,000 real validation transactions in time order; 15 s warm-up
excluded; 60 s measured; 3 repetitions per rate (the host run beside each for comparison).
On the locked system (after Phase 5b), image `serving:0.1.3`, 2 Serve replicas on a head pod
capped at 2 CPU.

| tx/s | p50 | p99 (3 runs) | p99.9 | errors | scorer CPU |
|---|---|---|---|---|---|
| 10 | 7.4 ms | 13.3 – 13.8 ms | ≤ 17.8 ms | 0 | 0.23 cores |
| 50 | 6.8 ms | 12.3 – 14.8 ms | ≤ 19.3 ms | 0 | 0.66 |
| 75 *(1 short run)* | 6.2 ms | 10.7 ms | — | 0 | 0.79 |
| 100 *(1 short run)* | 5.8 ms | 12.6 ms | — | 0 | 0.94 |
| 150 *(1 short run)* | 6.6 ms | **21.8 ms** | — | 0 | 1.47 |
| 200 | 1.2 – 6.6 **s** | **4.7 – 9.9 s** | ≤ 10.0 s | 0 | **1.96 (cap 2)** |

The data's own load: 5.6 tx/s on average, 13.5 tx/s in a busy minute (p99), **187 tx/s in
the busiest minute** of the 18 days.

**What it means.**
- At every rate the stream sustains on average and in a busy minute, **p99 is 13-15 ms**,
  well inside 50 ms. The earlier 7.7 ms (one request at a time, from the host) was the p50
  of an idle server; the honest p99 under load is about twice that.
- **Capacity is 150-175 tx/s.** Past it, requests queue and latency jumps from milliseconds
  to seconds — with zero errors, which is exactly what a closed-loop test would have missed.
- **The cost is not the model.** Our own code (one Redis round trip, feature assembly,
  XGBoost) costs **0.6 ms of CPU** and p99 3.8 ms in process, single-threaded as in the pod.
  In the pod each request costs **~10 ms of CPU**: about 94% is Ray Serve's HTTP proxy,
  routing and serialisation.
- Side finding: on the host, XGBoost spread one-row predictions across all 8 cores — 65 ms
  of CPU per request and *slower* (p50 10.3 ms). The pod is single-threaded (Ray sets the
  thread count from the replica's CPU), so production was not affected; the host-side tools
  now pin one thread.

**Consequences.**
- The S5.4 acceptance criterion "p99 < 50 ms at 200 tx/s" is **not met**. It is recorded as
  failed, not lowered.
- For Phase 6: the stream should not pay an HTTP + Ray Serve hop per transaction. A
  consumer that scores in process (or in micro-batches) costs ~0.6 ms of CPU per
  transaction — hundreds of times the headroom — and Kafka absorbs a busiest-minute burst.
  The HTTP endpoint stays for interactive use, where 150 tx/s is ample.
- The options for the HTTP path itself (more CPU, Serve batching, a lean server instead of
  Ray — ADR 0001's decision would be revisited) are a decision for Lubo, not taken here.

## FINDING-014 — New accounts launder at 14-30× the base rate; the model handles one new side, but is blind when both are new

*S5.5, 2026-11-19, validation window only. Raw: `docs/analysis/s5.5-cold-accounts.json`.*

By the serving definition the online store holds account states as of `train_end`; a side
of a transaction is *cold* when its account has no history before then, and the scorer
then uses all-zero history features.

| Validation (1,015,300 tx) | Share | Laundering rate | Median score | Their launderers in the top-5,000 queue |
|---|---|---|---|---|
| Both sides known | 99.80% | 0.104% | 0.0002 | 23% |
| Sender new | 0.098% | **1.50%** (14×) | 0.063 | **47%** |
| Receiver new | 0.092% | **1.39%** (13×) | 0.005 | **38%** |
| **Both new** | 0.006% (63 tx) | **3.17%** (30×) | **0.0008** | **0%** (0 of 2) |

**What it means.** New accounts are rare but dirty. Where *one* side is new, the zero
history is itself informative to the model — it scores those transactions far higher than
warm traffic, and their launderers reach the queue twice as often. Where *both* are new,
the model has nothing and scores near zero: a transaction between two never-seen accounts
is treated as clean, and the two launderers among the 63 were both missed. The sample is
small; the direction is not ambiguous.

**Decision (Lubo, 2026-11-19).** Every response carries `cold_policy`. One side new:
`scored: sender new` / `scored: receiver new` — the score stands. Both new:
`review: both accounts new` — Phase 6's rules layer and Phase 7's queue put it in front of
an investigator whatever the score (~27 a day at validation rates). A model that knows
"new" as a feature, rather than reading zeros, is a Phase 8 retraining candidate.

**Also fixed here.** An empty store (after a Redis restart, before the refill) used to
make every account look new — 54 such answers were seen during the S5b.6 rotation. Now
`store-load` writes a marker last; without it the scorer answers 503 "not loaded", and
with Redis down 503 "unavailable", never a cold score. Drill: Redis stopped → 503 →
restarted and refilled → healthy in 24 s; 2,000/2,000 scores identical after.

## FINDING-015 — The online snapshot disagreed with training in two places; "approx" hid both

*Found: 2026-11-21, Phase 6 (S6.2). Acts on: the stream (S6.3+), the online store.*

Before building a stream that keeps features live, the snapshot it starts from was compared
with training **exactly** (`==`), not with `pytest.approx` as the old parity test did.
Measured on train + validation (the test window was not read):

| Gap | Training | Snapshot (before) | Affected at `train_end` |
|---|---|---|---|
| Money totals | "before" = `(S + a) − a`, S the sequential running total | `sum()` (compensated rounding) | 78,902 senders, 125,112 receivers — last digit |
| 24 h send count | window `(t − 24h, t)`: a send exactly 24 h earlier is **out** | `>=` — counted it | 280 senders (315 sends) |

The proof test (`tests/serving/test_exact_parity_real.py`) fails on the old code with 79,003
of 130,418 senders and 117,585 of 186,037 receivers mismatching, and passes on the new code
with zero. Training itself did not change (train and validation features identical,
4.06M rows), so the production model stays `xgb-ab9ee07e6bd8`; of 2,000 validation scores
one moved (8.7e-8), and it was the 24 h fix making the online score equal training's.

**Two lessons.** `approx` in a parity test hides exactly the errors a stream accumulates:
a last-digit gap in a running total never shrinks. And "the same tie order" was true only
by luck — Polars kept same-minute ties in source order without being asked; every history
sort now says `maintain_order=True`.
