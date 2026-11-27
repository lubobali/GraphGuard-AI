# Riskline — build plan

Real-time money laundering detection on a transaction graph.

*Originally: "with a graph neural network". Phase 4 measured the GNN losing to a
tuned tabular baseline by 6x, so the production model is XGBoost and the GNN is
the research arm. See "Plan revisions" below.*

**Owner:** Lubo Bali
**Started:** Aug 18, 2026
**Status:** Phases 0-3 complete, Phase 4 comparison done, Phase 5 half built.
Revised by R-2 on 2026-11-18, R-6 on 2026-11-27. Last updated 2026-11-27.
**Progress:** see the checkmarks below, `CLAUDE.md` for the phase table, and
`docs/findings.md` for what the data turned out to actually contain.

---

## Plan revisions

Changes to this plan, with the evidence that forced them. A plan that quietly
rewrites itself to match the result is worth nothing; the point of writing it
first was to be able to see where reality disagreed.

### R-1 — The production model is XGBoost, not the GNN

*2026-08-20, after Phase 4. Affects Phases 5, 7, 8 and the stack table.*

The plan assumed the GNN would win and built the serving design around it:
precompute **embeddings**, store **embeddings** in Feast, monitor **embedding**
staleness, explain with **GNNExplainer**.

Phase 4 measured otherwise. On identical features, the same frozen split, the
same `evaluate()` and the same 20-trial Optuna budget:

| | PR-AUC | Rings @5000 |
|---|---|---|
| GraphSAGE | 0.04470 | 60 / 168 |
| XGBoost | **0.28155** | **127 / 168** |

**What changes.** Serving stores **point-in-time account features**, not
embeddings — the columns XGBoost actually consumes. Explainability for the
production path is **SHAP over those features**; GNNExplainer stays, but scoped
to the GNN arm rather than to production. Staleness is monitored on features
rather than embeddings.

**What does not change.** The architecture is untouched: an online store still
exists for the same reason, train/serve skew is still prevented by one shared
definition, the latency budget is still p99 under 50ms, and the "draw the ring"
screen still works because rings come from the graph and the labelled patterns,
not from the model.

**What is deliberately kept.** The GNN is not deleted. Graph structure was worth
3.3x over identical features without it (FINDING-007), the gap to the tree is a
model-class gap on tabular features, and Phase 10 exists partly to ask whether
more data changes that answer. It is a documented negative result, which is the
rarer and more defensible thing to have.

### R-2 — Re-checked against the world after three months

*2026-11-18, before resuming Phase 5. Affects Phases 4-9, the stack table and the
pitch. Evidence: `docs/research/AML portfolio plan research 2026.md` (five research
tracks, notes beside it). Several sources there are preprints or vendor claims and
are labelled as such.*

The plan was written in August. Before building Phases 5-9 on it, it was checked
against four things: what banks pay for now, what 58 live fraud/AML ML job postings
ask for, recent research on this exact benchmark, and the 2026 state of every tool
in the stack.

**What the evidence said.**

- **The core holds.** XGBoost in production, the leakage contract, precision@k,
  AMLworld. An independent Nov 2026 preprint (arXiv 2611.18914) reached the same
  result we did: a strict point-in-time tree matches the published GNNs, and the
  standard Multi-GNN test graph includes later transactions. Our split already
  excluded the post-Sep-10 simulator tail (FINDING-001) before that paper appeared.
- **Our GNN opponent is too weak.** Published work uses Multi-PNA / MEGA-PNA, not
  vanilla GraphSAGE, and reports minority-class F1, not PR-AUC. As it stands, a
  reviewer can wave the result away and cannot place our numbers.
- **The business problem got sharper.** UK receiving banks pay half of every APP
  scam refund (since Oct 2024), and the FCA's Sep 2026 mule review told firms to look
  past the first receiving account. A ranked queue of rings is exactly that.
- **Postings ask for capabilities, not brands.** 93% production, 59% monitoring,
  50% real-time; Feast, Ray Serve and SHAP each named 0 times out of 58. The open
  door for a switcher is serving/platform roles.
- **Two stack facts changed.** Redpanda stops being source-available from 26.3.1
  (20 Nov 2026). Ray and Feast both had serious 2026 CVEs.

**What changes.**

| # | Change | Where |
|---|---|---|
| 1 | Redpanda → **Apache Kafka 4.x** (KRaft, single node, hard memory cap) | Phase 6, stack |
| 2 | Add **minority-class F1** (threshold picked on validation) next to precision@k and PR-AUC | metric, `evaluate()` |
| 3 | **GNN rematch with Multi-PNA** (or MEGA-PNA), strict point-in-time, same 20-trial budget. GraphSAGE stays as history | Phase 4 |
| 4 | **Measure Ray Serve's real memory on k3s**, then keep it (patched, dashboard internal only) or replace it with FastAPI on k3s | Phase 5 |
| 5 | Feast **as a library only**, or keep our own store and say why. No Feast servers | Phase 5 |
| 6 | Investigator **agent with a measured error rate**: tools over MCP, a transaction ID behind every claim, a deterministic checker, traced and evaluated in MLflow | Phase 7 |
| 7 | **Rules layer** as baseline and safety net; **label delay** in the replay | Phases 6, 8 |
| 8 | Model card written as a **model-risk package**; Airflow only if a capped setup fits, else Dagster; champion/challenger kept small | Phase 8 |
| 9 | Pitch: **receiving-bank mule-network detection**, with the honesty caveats | pitch, Phase 8b |
| 10 | **Second dataset (TransXion, KDD '26)** as a robustness check, new Phase 9. Scale moves to Phase 10 | Phases 9, 10 |
| 11 | Cut **SageMaker** (the tree needs no GPU). Alert-volume forecast becomes optional | Phase 4, 8 |
| 12 | Short **architecture decision records** (`docs/adr/`) for every big choice | all phases |
| 13 | **A small lakehouse**: Iceberg tables (Parquet underneath, PyIceberg + SQLite catalog, local disk then our own S3 bucket) as the offline store; Redis loaded *from* it as the online copy. Polars reads them now, Spark reads the same tables in Phase 10. Added 2026-11-18 after Redis was found to keep nothing on disk | Phase 5 (S5.6), 10 |

**What does not change.** XGBoost serves. The leakage contract, the frozen split and
the sealed test set. Precision@k and the capacity slider as the headline. AMLworld
HI-Small with "synthetic" said first. SHAP and the drawn ring. MLflow and the k3s
work already done. The GraphSAGE result, kept as documented history. One step at a
time.

**And a process change.** Every phase from here starts with written agile stories,
approved before any code is read or written for it. See "How we work".

### R-3 — Box security becomes its own phase (5b)

*2026-11-18, during Phase 5. Decided by Lubo. Affects Phase 5's order and adds Phase 5b.*

The lockdown was one story (S5.8, four sub-stories). The read-only audit of the box
showed it is bigger than that: it covers the whole box, not only GraphGuard (host
firewall, k3s's public ports, per-job users), and part of it is LuBot's to fix and
must be planned with the LuBot session. It is now **Phase 5b — Box security**, with
its own stories (`docs/stories/phase-5b.md`; S5.8a-d became S5b.1-4).

**Where it goes:** after S5.6e, before S5.4. S5.6e is the last Phase 5 step that changes
how services connect (Feast may fill Redis), so after it the inventory is final and is
locked once. S5.4 must measure p99 on the **locked** system, since a Redis password, TLS
or firewall rules can each add latency. Phase 6's Kafka is then born inside the rules.
The "touch Redis once" reason for doing the lakehouse first (S5.6) is already met:
`just store-load` rebuilds Redis from gold in 13 s.

### R-4 — The interface follows real case managers (Phase 7)

*2026-11-22, before Phase 7. Research `docs/research/AML investigator interface research
2026.md`; decisions in ADR 0008, made for Lubo at his request. Affects Phase 7 only.*

- **What one alert is:** a transaction (what was evaluated), shown grouped by sending
  account — not "ranked accounts", which no model here scores.
- **Counts at a fixed workload, no money totals:** amounts are in 15 currencies with no
  exchange rates, so "laundering value caught" cannot be shown as money.
- **The demo team works 100 alerts a day** (the slider covers the rest); ADR 0007's 5,000 per
  window stays the evaluation's k.
- **"Same stack as LuBot's frontend"** becomes Next.js static export + React + React Flow and
  a small FastAPI read API (LuBot's code is off limits to this project).
- **Model risk:** SR 11-7 was replaced by SR 26-2 (April 2026); the About page follows it.
- **Private first:** the demo is reached over the ssh tunnel; a public URL is its own later
  step through the LuBot session.
- **The tester** for the gate is named: Lubo's wife.

Unchanged: three pages, SHAP reasons, the ring, the slider, the measured agent, the gate.

### R-5 — A bank simulated end to end: UX for newcomers, a real workflow, a go-live day

*2026-11-23, Phase 7. Cause: Lubo's first look at the site (60 questions; recorded in
`docs/stories/phase-7.md`). Research `docs/research/AML demo UX and AI innovation.md`.*

- **Phase 7 grows** by S7.12-S7.17 before the S7.11 gate: a first screen that says what the
  system does in counts, trustworthy reasons, a numbered money picture, a real decision
  workflow (codes, second review, history, training feedback), a manager page, and an AI
  second reviewer that argues against the person's decision with checked facts (precomputed).
- **Go-live = the sealed test window.** When the model is final (Phase 8), the locked test
  window (8-10 Sep, ~1M rows, ~2.3 days) is replayed **once, at real speed** through the live
  stream. That replay is both the bank's first day and the honest final score; no model change
  after it. Contract rule 4 holds: the window is opened once.
- Bigger data stays Phase 10.

### R-6 — Findable before monitoring: Phase 8b moves ahead of Phase 8

*2026-11-27, end of Phase 7. Decided by Lubo. Cause: AWS re:Invent the following week; he
wants a live demo and a finished-looking repo to show there.*

- **Phase 8b runs before Phase 8.** The demo goes public on the validation window, as built in
  Phase 7. The README says plainly that the numbers are **validation** numbers and that the test
  window is still sealed. The plan's "drift alert followed by a retrain" story is told as *next*,
  not claimed.
- **The S7.11 test on a real person is replaced by an AI stand-in.** Lubo's wife could not do it.
  A reviewer with no project context gets only screenshots and answers the same questions. This
  is written down as **not a real-person test**, and a real person is still owed (the first
  stranger who uses the public URL and tells us counts).
- **Unchanged:** Phase 8, then the go-live replay of the sealed window (R-5), opened once. After
  it, the README's numbers gain the test score.

---

## Why this project exists

His resume has zero model training on it. Everything he has built sits *on top of*
models other people trained. This is the project that closes that gap, and it has to
close it convincingly enough to survive a technical interview with an ML engineer.

So the bar is not "a model that runs". The bar is: **a senior ML engineer reads the
repo and cannot find the shortcut.** Most portfolio ML projects fail that read in
under two minutes, because of leakage, an unfair baseline, or a metric that flatters
the result.

---

## The problem, stated properly

Money laundering does not look suspicious one transaction at a time. It looks like a
**shape**: one account splits money across several, those funnel into one, sometimes
through a cycle, sometimes stacked in layers. Every individual hop is an ordinary
transfer for an ordinary amount.

That is why this is a graph problem and not a tabular one. A row-level model
structurally cannot see a shape that spans six accounts.

**What the system does:** watches a stream of bank transfers and produces a ranked
queue of accounts worth investigating, fast enough to act on, with a reason attached
to each one.

**What it does not do:** decide anything by itself. A human investigator works the
queue. The model decides the *order*.

**Who has this problem in 2026 (R-2):** the bank that *receives* scam and laundering
money. In the UK the receiving bank pays half of every APP scam refund, and the FCA's
Sep 2026 mule review says cash-out happens at the 2nd to 5th account and firms must
look beyond the first one. Finding **mule networks** — the rings money passes
through — is that job. Three caveats, said every time: the data is synthetic, it does
not model APP scams specifically, and a real bank only sees its own part of the
network.

---

## The metric, decided before any model exists

**Primary: precision@k**, where k = how many alerts a team can actually work in a day.

Not AUC. At a 0.1% fraud rate you can score 0.99 AUC and still hand investigators a
worthless queue. Precision@k asks the only question that matters: of the k accounts we
told a human to look at, how many were really laundering?

**Secondary:** PR-AUC (honest under imbalance), and recall of *whole patterns* rather
than individual edges — catching 1 transaction in a 12-hop ring is not catching the ring.

**Comparability (R-2):** minority-class F1, with the threshold picked on validation.
Not a headline — it is the metric the AMLworld literature reports (0.63-0.76 on
HI-Small), and without it nobody can place our numbers next to theirs.

**Money view:** k is investigator capacity, and the tradeoff is cost of an investigator
hour against the cost of laundering that slipped through. That is the slider in the UI.

---

## The leakage contract

Written down first because it is the thing most likely to quietly invalidate everything
downstream. Every phase must hold to it.

1. **Split by time, never randomly.** Train on the earliest window, validate on the
   middle, test on the latest. Frozen once, at the start of Phase 2, before any model
   is trained.
2. **The graph at time T contains only edges before T.** No exceptions. Building the
   graph over the full history and then splitting is leakage even though the split
   looks correct.
3. **No feature may use information that did not exist at decision time.** Account
   degree means degree *as of that moment*, not final degree.
4. **The test window is opened once.** Every tuning decision is made on validation. If
   the test set is touched more than once, it is not a test set anymore.
5. **Any feature that looks too good gets investigated, not celebrated.** A single
   feature carrying most of the signal is usually leakage, not luck.

If any of these is violated, the result is void and gets rebuilt. No exceptions, no
"good enough for a portfolio".

---

## Data

**IBM AMLworld** — `ealtman2019/ibm-transactions-for-anti-money-laundering-aml` on Kaggle.

Six files, two families: HI (higher illicit ratio) and LI (lower). Each in small,
medium, large.

| File | Transactions | Runs on |
|---|---|---|
| HI-Small | ~5M | Hetzner, CPU. **Start here** |
| HI-Medium | ~32M | Hetzner, tight, Polars + sampling |
| HI-Large | ~180M | One box gives up. Spark + GPU |

Confirm exact row counts and column names on download rather than trusting this table.

**It is synthetic**, generated by IBM's multi-agent simulator for a NeurIPS paper. Say
so out loud, first, every time. The reason it exists is that no bank can legally
publish labeled laundering rings, which is exactly why every paper in this area uses
it. Hiding that is the only thing that would make it a weakness.

**It also ships labeled pattern files** — the ground truth rings, by type. That is what
makes pattern-level recall possible, and it is the main reason this dataset beats the
alternatives.

---

## Stack

| Layer | Choice | Why this and not the obvious thing |
|---|---|---|
| Packaging | **uv** | already what LuBot runs, including in CI. `uv.lock` pins exact versions, which is what makes the Phase 0 reproducibility gate real. Used in local, CI, **and** the Docker image, or it recreates the drift the CI-mirrors-prod rule exists to prevent |
| Dataframes | **Polars** | pandas would work at 5M and stop working at 32M. Spark at 5M would be slower and waste ~2GB on a JVM; it enters in Phase 10 on the same Iceberg tables |
| Offline store / table format | **Apache Iceberg** (PyIceberg, SQLite catalog, Parquet files) | versioned snapshots and time travel: a model is traceable to the exact feature snapshot it trained on, and the online store can be rebuilt from it. No Spark or servers needed on this box (R-2) |
| **Graph neural network (GNN)** | **PyTorch Geometric** | the standard GNN library; GraphSAGE, inductive, neighbor sampling. Written as the centerpiece; Phase 4 measured it losing to the baseline, so it is the research arm and XGBoost serves (R-1) |
| Baseline → **production model** | **XGBoost** | still the right answer for tabular, and the honest opponent. It won Phase 4 by 6x and is what gets served (R-1) |
| Tracking | **MLflow** | every run recorded, or the comparison is anecdote. Model Registry handles promotion |
| Tuning | **Optuna** | hyperparameter search that is recorded and reproducible, not a notebook full of guesses |
| Orchestration | **Airflow** | the retraining pipeline as a real DAG. He has shipped Airflow before, so this is existing ground, not new learning |
| Data quality | **Pandera** | schema and expectation checks on every pipeline stage; bad data fails loudly instead of quietly training a worse model |
| Explainability | **SHAP** (production) + **GNNExplainer** (GNN arm) | which features and which hops drove the score. Non-optional in a regulated domain. SHAP explains the model that actually serves; GNNExplainer explains the research one (R-1) |
| Narratives | **LLM investigator agent** (NVIDIA NIM) | drafts the case report an investigator reads. Tools exposed over **MCP**, a transaction ID behind every claim, a deterministic checker, traced and evaluated in **MLflow GenAI** (R-2) |
| Feature store | **Our own store** (Polars → Iceberg gold → Redis) — Feast measured and not adopted (ADR 0004) | solves train/serve skew structurally. Feast is still pre-1.0 and its servers had critical 2026 CVEs, so no feature or registry server runs (R-2) |
| Serving | **Ray Serve on k3s**, kept only if its measured memory fits; else FastAPI on k3s | real model serving on real Kubernetes. Ray ≥ 2.52 and dashboard internal only, because of CVE-2025-62593 (R-2) |
| Artifacts | **AWS S3** | trained models, feature snapshots, and evaluation outputs versioned in S3 rather than on a disk that could die |
| ~~GPU training~~ | ~~AWS SageMaker~~ | cut by R-2: the production model is a tree and needs no GPU |
| Stream | **Apache Kafka 4.x** (KRaft) | was Redpanda; Redpanda stops being source-available from 26.3.1. Kafka 4 needs no ZooKeeper, so it is now one process too, and it is the only stream tool named in the 58 postings (R-2) |
| Online store | **Redis** | account feature + counter lookups inside the latency budget |
| Records | **Postgres** | every decision and the features behind it |
| Drift | **Evidently** | standard, and stops us hand-rolling charts |
| Frontend | **Vite + React + Tailwind** | same stack as LuBot, nothing new to learn |

**Not using Databricks in v1.** 5M rows fits in RAM. Spark enters in Phase 10, when
HI-Large genuinely does not fit on one machine. "I added Spark when the data outgrew
the box" is a better sentence than "I used Spark."

---

## Isolation from LuBot and from aws-job-streamer

**Two things are off limits and Riskline touches neither.**

**`aws-job-streamer` is off limits.** It is a live public resume artifact and its AWS
resources are not to be modified, reused, or shared. Riskline gets its **own S3 bucket,
its own IAM user with its own keys, and its own tags**. No existing bucket, role, or
policy is edited. If a Riskline change would touch a job-streamer resource, that is a
bug in the plan, not a shortcut to take.

**LuBot is sacred.** Riskline shares nothing with it.

- Own compose project, own Docker network, own volumes
- Own system user, own path (`/srv/riskline`)
- Own Postgres and Redis instances, not LuBot's
- Own ports, own subdomain (`riskline.lubot.ai`)
- **Hard memory caps on every container** — the box has swap in use and a history of
  memory pressure
- Nothing in this project may restart, read, or write anything named `lubot-*`

Budget: ~4GB RAM, ~25GB disk. Box currently has 19GB available and 98GB free.

---

## Phases

Each phase has a **done means** that can be checked. A phase is not finished because
the code runs. It is finished when the gate passes.

### Phase 0 — Ground ✅ DONE (2026-08-19)

Set up the box and get the data on it. No modeling.

- ✅ Isolated project skeleton, own compose file, memory caps
- ⏸️ **k3s** — DEFERRED to Phase 5. Not in the Phase 0 gate and not needed until serving.
  Idle services cost RAM on a box that is already tight
- ⏸️ **AWS** — DEFERRED to Phase 4. Not in the Phase 0 gate and not needed until there is
  a trained model to store
- ✅ `kaggle` CLI (project-local), HI-Small downloaded to the server — 487MB, 3 files
- ✅ Loaded with Polars — 5,078,345 transactions, 515,080 accounts, Sep 1-18, 0.102%.
  Found two columns both named `Account`; found the file runs 8 days past its
  documented end (FINDING-001)
- ✅ **Full test environment before any modelling code.** pytest strict mode, marker
  taxonomy, ruff with complexity caps, prek hooks, Forgejo CI on its own isolated
  runner, xdist flags defined once in the justfile and called by both
- ✅ **The three lint guards**, wired into prek and CI. Each proven to block a real
  commit, not just to run
- ✅ MLflow up on its own Postgres — own compose project, network, volumes, ports
  5010/5434 bound to localhost, both memory-capped

- **Reproducibility from day one:** **uv** with a committed `uv.lock`, every seed fixed,
  every path in config not hardcoded, one command to set up from a clean clone. The same
  lockfile is used by CI and the Dockerfile. If a result cannot be reproduced it does not
  count

**Done means:** `just check` runs tests and lint clean, one command prints the
dataset's shape, date range, and class balance, and a clean clone reaches that state
with a single setup command.

*Rough time: 2-3 sessions.*

### Phase 1 — Understand the data before touching a model ✅ DONE (2026-08-19)

The phase most people skip, and the reason their results are meaningless.

- ✅ Graph statistics — median degree 6, p99 119, max 169,756. The biggest accounts are
  hubs laundering at the base rate, not criminals (FINDING-002)
- ✅ Pattern file parsed; a fan-out, a cycle and a scatter-gather reconstructed and read
  by hand
- ✅ Median ring: 6.5 transfers, 8 accounts, 3.1 days. Every hop an ordinary amount
- ✅ 62% in a labelled ring, 38% not (FINDING-003). Pattern recall can only ever be
  computed over the 62%, and the denominator is reported

**Done means:** he can describe, without notes, what a laundering ring looks like in
this data and why a row-level model cannot see it. If he cannot say that, the GNN
result later is not defensible.

### Phase 2 — The evaluation harness, before any model ✅ DONE (2026-08-19)

Build the scoreboard before there is anything to score. This is the ordering that
separates a senior workflow from a Kaggle notebook.

- ✅ Temporal split frozen to `data/splits/frozen_split.json`, checksum guarded on every
  commit. Verified deterministic and verified the guard fails on a tampered file
- ✅ precision@k, PR-AUC, pattern recall reported two ways (strict and hit-rate)
- ✅ Cost function: investigator hours against laundering value missed
- ✅ Both scored on validation. Random PR-AUC 0.00103 (= base rate, which is the harness
  sanity check), by-amount 0.00170. Neither caught any of the 168 rings (FINDING-004)
- ✅ Single `evaluate()` entry point in `graphguard.evaluation.evaluate`

**Done means:** the dumb baselines are scored and their numbers are recorded in MLflow.
Everything after this is measured against them.

### Phase 3 — Tabular baseline, built to actually win ✅ DONE (2026-08-20)

The baseline gets a real effort. A weak baseline makes the GNN result worthless.

- ✅ Point-in-time row features: amount, log amount, currency, cross-currency, payment
  format, hour, weekday, self-transfer, same-bank
- ✅ **Hand-built graph features** — sends so far, distinct counterparties so far, 24h
  velocity, in/out ratio, time since last send. All bounded by `as_of` and all excluding
  the current row. The baseline gets graph information too
- ✅ **Pandera schemas** on the raw and feature stages, asserted as tests as well as
  applied at runtime
- ✅ XGBoost tuned with **Optuna**, 20 trials on validation only, every trial logged to
  MLflow. PR-AUC 0.24814 untuned to **0.28155** tuned
- ✅ Leakage audit in `docs/leakage_audit.md`. Found three generator artifacts carrying
  65% of the gain — 85% of laundering is ACH and Wire contains none (FINDING-006).
  Retrained without them and quote the lower number

**Done means:** beats both dumb baselines on precision@k, and the leakage audit is
written down with each top feature justified. Test set still unopened.

### Phase 4 — The graph model 🔨 IN PROGRESS (comparison done 2026-08-20)

- ✅ Transaction graph as day snapshots with **time-respecting edges**. The frame is cut
  by `as_of` before the node mapping is built, so no later edge reaches even the index
- ✅ GraphSAGE, **inductive**. Accounts appearing for the first time get a node with zero
  features rather than an error
- ✅ Neighbour sampling via LinkNeighborLoader (needs pyg-lib, pinned in the lockfile)
- ✅ Imbalance handled with `pos_weight`, **searched rather than fixed**. The exact class
  ratio of 1326 is right for a tree and catastrophic for gradient descent; Optuna chose
  6.34 and the GNN improved 8x. Largest single effect in the phase
- ✅ Same `evaluate()` entry point, same frozen split
- ✅ Tuned with **Optuna**, 20 trials, the same budget the baseline received
- **GNNExplainer** on flagged accounts: which neighbours and which hops drove the score.
  Scoped to the GNN arm after R-1 — the served model is the tree, so Phase 7's "why this
  alert" comes from SHAP. Still worth having: in a regulated domain a model that cannot
  explain itself cannot be deployed, and this is what would be needed if the GNN ever
  became the production model
- ~~Train on SageMaker when CPU gets slow~~ — cut by R-2. The tree serves and needs no
  GPU; the rematch below runs on CPU or, if it truly must, a GPU rented for hours
- **Minority-class F1 in `evaluate()`** (threshold picked on validation), reported for
  every model so far, on validation (R-2)
- **The rematch: Multi-PNA (or MEGA-PNA) under our strict point-in-time protocol**, same
  frozen split, same `evaluate()`, same 20-trial Optuna budget. GraphSAGE was too weak an
  opponent for the result to be taken seriously; IBM's code is public. GraphSAGE stays
  as documented history (R-2)
- **Protocol finding written up**: cite arXiv 2611.18914 as independent support and
  answer arXiv 2609.37155 as the counter-claim. If budget allows, show the effect: one
  GNN run with a full-history graph and one point-in-time, both on validation (R-2)

**Done means:** a fair comparison table against Phase 3 on precision@k, pattern-level
recall **and minority-class F1**, including the strong GNN, not only GraphSAGE.

**And if the GNN loses:** that is a finding, and it gets written up as one. "The graph
model did not beat a well-built tabular baseline at this scale, and here is why" is a
stronger, rarer answer than a rigged win. Do not tune the GNN against the test set to
avoid this outcome.

### Phase 5 — Serving it for real

The hard engineering. You cannot walk a graph in 30ms.

- ✅ Precompute **point-in-time account features** in batch — counterparties so far,
  velocity, in/out ratio, the columns XGBoost consumes — into an online store (Redis
  underneath), with train/serve parity asserted. Originally written as embeddings; the
  production model is the tree, so the payload is features (R-1). Built as our own store,
  not Feast — see the decision bullet below
- ✅ At scoring time: fetch both accounts' features, combine with the fresh transaction
  features, score
- ✅ Staleness measured (FINDING-008) and the cold flag returned by the service
- ✅ Latency budget: **p99 under 50ms** measured on Ray Serve outside k3s — 7.71ms over
  HTTP, 22.08ms in-process. **Still to measure on k3s**
- ✅ Ray Serve deployed on k3s via KubeRay. **Currently broken**: the image was deleted
  by k3s's image GC during a disk-full period (pod in ImagePullBackOff since ~Oct 30)
- ✅ **Get the k3s endpoint healthy again**, and stop image GC from deleting it again
  (S5.1-S5.2)
- ✅ **A small lakehouse, step 1** (S5.6a): Iceberg bronze/silver/gold (+ `sealed` for the
  test window) on local disk, catalog in our own Postgres; Redis rebuilt from gold
  without retraining (2,000/2,000 scores identical); every training run logs the
  snapshot ids it read. FINDING-009
- ✅ **The lakehouse, steps 2-4** (S5.6b-d): our own S3 bucket and DuckDB SQL; Lakekeeper
  as the Iceberg REST catalog (ADR 0002); Dex logins, OpenFGA grants and per-table
  vended S3 keys, with `sealed` and bronze denied to training (ADR 0003,
  FINDING-011). FINDING-010, FINDING-012
- ✅ **Measure Ray's real memory on k3s** and decide: kept Ray Serve, right-sized,
  dashboard locked by NetworkPolicy (S5.3, ADR 0001)
- ✅ **Feast decision** (S5.6e, ADR 0004): **our own store kept.** Feast 0.68 matched our
  online values exactly but needed 3.96 GB to fill (ours 0.58 GB) and cannot build the
  training features without leakage on same-minute ties. OpenLineage on every job;
  a marimo worksheet as `reader`
- **Then Phase 5b (box security)** before the remaining Phase 5 steps below (R-3)
- **Cold-account path tested** as an explicit test, not only observed in a measurement
- **Model pulled from S3 at startup**, so the running version is always traceable to a
  specific artifact. Needs the project's own bucket and IAM user (AWS was deferred)
- Stateless services on Kubernetes, stateful ones (Postgres, Redis, Kafka) stay in
  Docker with their own volumes. That split is deliberate and worth being able to explain

**Done means:** a live endpoint **on k3s**, p99 measured under budget there, the
cold-account path tested rather than assumed, and the Ray and Feast decisions recorded.

### Phase 5b — Box security (added by R-3)

The box was hacked once. GraphGuard must never be the weak door into LuBot or anything
else on it, and the whole box should end up locked at least to LuBot's standard.

- **GraphGuard's own containers and pod** hardened like `lubot-prod-backend`: Redis
  password and persistence, every container non-root / read-only / no capabilities
  (S5b.1)
- **Supply chain**: CI runner job isolation, actions pinned by SHA, gitleaks in prek
  and CI (S5b.2)
- **Backups off the box** with a tested restore: MLflow, the catalog databases (S5b.3)
- **k3s off the public interface** and a **host firewall** behind Hetzner's, planned
  with the LuBot session, applied once, every app verified, with a rollback (S5b.4)
- **One Unix user (or container) per job**, so a job cannot read another's secrets —
  the honest limit recorded in ADR 0003 (S5b.5)
- **Keys and secrets**: rotation runbook; the retired S5.6b AWS key (kept active as an
  accepted risk) re-decided; nothing secret in any repo, checked by a scanner (S5b.6)
- **LuBot's own findings** handed to the LuBot session, which fixes them (details: private audit, not in this public repo).
  GraphGuard's session never touches LuBot

**Done means:** every item above either done and verified by a test or a check that
fails when it regresses, or explicitly handed over / accepted in writing; LuBot,
staging, git.lubot.ai and lubobali.com up throughout; a one-page "how this box is
protected" document a reviewer can read.

### Phase 6 — The stream

> **Decided 2026-11-19 (S5.4, FINDING-013):** the stream consumer scores **in its own
> process** (or in micro-batches), not through an HTTP call to the scorer per transaction.
> Our scoring code costs ~0.6 ms of CPU per transaction; the Ray Serve HTTP hop costs ~10
> ms and caps the HTTP path at ~150-175 tx/s on 2 CPU. Kafka absorbs bursts (the busiest
> minute is 187 tx/s). The HTTP endpoint stays for interactive use. Lubo chose this over
> more CPU or replacing Ray Serve.

- ✅ **(S6.1, done 2026-11-21)** **First: the scorer alert.** Once the stream depends on the scorer, an outage must
  reach a human. `just k8s-check` on a cron, an **email only on state change**
  (healthy↔broken), runbook `docs/runbooks/scorer-down.md`. Moved here from S5.2; Phase
  8 monitoring replaces it
- **Kafka 4.x** (KRaft, single node, hard memory cap — measured before committing), one
  topic, transactions replayed **in true time order**, accelerated. Was Redpanda (R-2)
- Consumer scores each one and writes the decision plus its features to Postgres
- **A simple rules layer** next to the model — the baseline it must beat and a safety net
  if it fails. Production systems are hybrids of rules, ML and investigators (R-2)
- **Label delay** in the replay: an investigator's verdict arrives days after the alert,
  not instantly. Anything downstream that learns from labels must see them late (R-2)
- Say "replayed stream" plainly. It is what payment companies do to test models, and
  replaying in true order is what gives point-in-time correctness for free

**Done means:** transactions flowing continuously, decisions landing in Postgres, rules
and model both scoring, and the system surviving being left running overnight.

✅ **Phase 6 gate met 2026-11-22** (S6.1-S6.11, `docs/stories/phase-6.md`): the whole validation
window (1,015,300 transactions) replayed overnight through Kafka → consumer on k3s → Postgres;
every transaction decided once, scores and rules equal the offline evaluation, shadow complete,
memory flat under caps (`docs/analysis/s6.11-soak-run2.json`).

### Phase 7 — The interface

Next.js (static export) + React + React Flow, a small FastAPI read API (R-4, ADR 0008).
Written for a person who does not know what a model is. Synthetic data, said on every page.

- **Alert queue** — alerts (one per transaction) grouped by sending account, highest risk
  first, with a due time, what to look at and why (R-4)
- **The ring, drawn** — the actual subgraph that triggered it. This is the screen that
  makes the whole project land, because you can see the shape
- **Capacity slider** — how many alerts a day can you work, and what does that cost you
  in missed laundering. Real numbers from the real evaluation, in counts (transactions and
  rings), never money totals (15 currencies, R-4). Default: a 100-alert-a-day team
- **Why this alert** — the features that drove the score, from **SHAP** over the
  production model, alongside the accounts and hops from the subgraph. Written as
  GNNExplainer; the tree serves, so SHAP explains the thing that actually decided (R-1)
- **Investigator agent, with a measured error rate** (was "case summary", R-2). It
  calls our own tools — score, ring, SHAP, account history — exposed over **MCP**, and
  drafts the case report an investigator reads. Every sentence cites a transaction ID; a
  deterministic checker rejects any ID, amount or date not in the data. Measured on a
  small hand-checked set: **unsupported-claim rate** (gate: zero) and typology recall
  against AMLworld's pattern labels, traced and logged in MLflow. The agent drafts, the
  human decides — it never files or closes anything. Published SAR-drafting research
  reports no such metrics, so measuring it is the point. Runs on NVIDIA NIM
- **Pages: three, no more.** Queue (with the slider) → Case (ring, why, agent report) →
  About (diagram, the result, links)

**Done means:** someone non-technical looks at it and can say what the system does and
what they would do next — tested on a real person, not on yourself (Lubo's wife) — and the agent's
unsupported-claim rate is measured and at zero on the eval set.

### Phase 8 — Monitoring, and the honest write-up

- Feature staleness, score distribution, alert volume, drift via Evidently
- Train/serve parity check — same transactions through both paths, compared
- **Retraining as a DAG**, not a cron job: pull new labelled data (arriving late, per
  Phase 6) → rebuild features → retrain → evaluate against the frozen split → register in
  MLflow → promote or reject. A rejected model must not be able to reach production by
  accident. **Airflow only if a minimal, memory-capped setup fits beside k3s and MLflow;
  otherwise Dagster** — measured, not assumed (R-2)
- **Champion / challenger, kept small.** MLflow aliases plus a shadow-scoring comparison:
  the new model scores everything but decides nothing, and is promoted only if it beats
  the champion on precision@k. The honest version of "A/B testing" (R-2: only 2 of 58
  postings name it, so it stays lean). **First challenger: the model without `weekday`**
  (FINDING-018: a simulator calendar artifact; dropping it measured 0.28253 vs 0.28155)
- *Optional:* **alert volume forecast** — a small time-series model predicting tomorrow's
  alert count for staffing. Demoted by R-2 to keep the project finishable
- README: the architecture, the leakage contract, the fair-baseline argument, the
  metric choice, **and what did not work**
- **Model card as a short model-risk package** (R-2): purpose, data, limits, validation,
  monitoring, kill switch — the shape a bank's model-risk team expects. What it is for,
  what it is not for, who it can hurt when it is wrong. An AML system accuses people. A
  false positive freezes someone's account. Naming that is not paperwork, it is the
  difference between someone who has thought about deploying a model and someone who has
  only trained one
- One paragraph on why **transaction foundation models** are out of scope: their wins
  come at tens of billions of events, not 5M (R-2)

**Done means:** the README could be handed to a skeptical ML engineer and survive.

*Rough time: 3-4 sessions.*

### Phase 8b — Make it findable

The project only helps if people see it. Built deliberately, not as an afterthought.

- **Live demo URL** with the stream visibly running. This is the link that gets clicked
- **90-second answer** written and rehearsed: what the problem is, why a graph, what the
  result was, what you would do differently. Rehearsed out loud, not just written.
  Interviews are lost by rambling through a good project
- **Demo video**, 2-3 minutes, screen recording with voice
- **LinkedIn post** in his own voice, no polish, one honest finding as the hook
- **Resume bullet** with the real number in it
- One diagram someone can understand in ten seconds
- **Lead with the evaluation story and the serving numbers, not the tool list** (R-2):
  the protocol finding, p99 under load, train/serve parity, a drift alert followed by a
  retrain, the agent's measured error rate. Aimed at ML platform / serving roles and
  LLM-compliance roles — the clearest openings for a switcher in a senior-heavy market
- Pitch as **receiving-bank mule-network detection**, with the three caveats (R-2)

**Done means:** a stranger can reach the live demo, understand what it does, and find
the repo, without you explaining anything.

*Rough time: 2 sessions.*

### Phase 9 — A second dataset, honestly (added by R-2)

Does the result survive a different generator, or is it a fact about IBM's simulator?

- **TransXion** (KDD '26) — same 11-column CSV header as AMLworld, a different generator
  family, ~3M transactions over 2025, 245MB. The existing loader reads it
- Update payment-format and currency vocabularies and the Pandera schemas; leave the
  person/merchant profile tables out at first, to keep the comparison fair
- **Freeze a new temporal split** before any model touches it; tune on its validation
  window only; its test window opened once
- Re-audit for generator artifacts, the way FINDING-005/006 did for AMLworld
- No ring labels there, so drop pattern recall; keep precision@k, PR-AUC, minority F1
- The data files carry no licence: use, do not re-host

**Done means:** the same pipeline and the same models on TransXion, with a table that
says plainly whether the tree-vs-GNN result held. If done before 8b, it goes in the
write-up.

### Phase 10 — Scale, optional and honest

Only when everything above works end to end, and after Phase 9.

- HI-Large, 180M transactions. One box stops being enough
- **Spark reads and writes the same Iceberg tables** Polars uses — "the same tables, two
  engines". Spark on Databricks (or a rented cluster) for graph construction and
  feature building
- Rent a GPU for a few hours for training
- Report what actually broke at 36x the data, because something will

**Done means:** the same pipeline, at 180M, with the failures documented.

---

## How we work

From `Testing_Best_Practices.txt` and the project CLAUDE.md — RECR loop:

1. Write the test first
2. Implement one task
3. Check it
4. Repeat

Mock only external things. Never weaken a test to make it pass. Zero failures before
moving forward — no "pre-existing failures" excuse.

**One phase at a time.** He asks questions, we go slow, nothing gets skipped or half
shipped. If a phase turns out to be wrong, we redo it rather than build on it.

### Every phase starts with agile stories (added by R-2)

Before any code is read or written for a phase, its stories are written down and
approved by Lubo. Order: **main goal → stories → approval → read the code → RECR loop.**

- Each story in the standard form: **As a** *[investigator / bank / hiring manager /
  operator]*, **I want** *[capability]*, **so that** *[business value]*
- Each has **acceptance criteria** written as checkable statements (Given / When / Then
  where it helps). They become the first tests in the RECR loop
- Each names the **Definition of Done** it rolls up to — the phase's "Done means"
- Small enough for one or two sessions; anything bigger gets split
- Stories live in `docs/stories/phase-N.md`, and are ticked off there as they pass

A phase's "Done means" is the epic. The stories are how it gets there.

**Architecture decisions** (R-2): every significant choice — Ray vs FastAPI, Feast vs
our own store, Kafka vs Redpanda, Airflow vs Dagster — gets a one-page record in
`docs/adr/NNNN-title.md`: context, options, decision, consequences.

---

## Testing and quality environment

Built in Phase 0, before any modelling code exists. This mirrors the LuBot setup rather
than inventing a new one, then adds the parts that only matter for ML.

### Carried over from LuBot

- **pytest in strict mode** — `--strict-markers --strict-config`, `xfail_strict = true`.
  A typo'd marker fails at collection instead of silently skipping a test
- **Marker taxonomy** — category markers (`unit`, `db`, `gpu`, `slow`) plus orthogonal
  labels (`integration`, `regression`). Default run deselects the slow ones so the fast
  loop stays fast
- **Ruff** with bugbear and complexity caps (`E,F,I,W,B,PLR0912,PLR0915,C901`), set to a
  ceiling that passes today and tightened as code gets refactored
- **prek pre-commit hooks** running ruff lint, ruff format, and the unit suite, scoped to
  `.py` changes so doc commits do not pay for a full run
- **xdist** — `-n 2 --dist=loadgroup` (4 until 2026-11-18, when the suite outgrew the CI job's 2 GB cap), with the **exact same flags in prek and CI**.
  Drift between the two is a known failure mode from LuBot and gets an explicit comment
- **Forgejo CI** installing with **uv from the committed lockfile**, cached, the same
  lockfile the container uses — so CI cannot pass on a dependency set production does not
  have
- **Bootstrap test DB schema mirroring prod**, so integration tests run against the real
  schema rather than one hand-maintained for tests
- **App startup check** as its own CI stage. LuBot verifies the FastAPI app actually
  imports and loads. Riskline's version is stronger: the serving app must import **and
  load the model from S3 and answer one scoring request**. A model that trains fine and
  cannot be loaded is a failure worth catching in CI, not in front of an interviewer
- **Unit and integration as separate stages**, so a fast failure fails fast
- **Boy Scout rule** — characterization tests before touching anything, no refactoring
  sprints
- **Coverage as a blind-spot finder, not a target number**

### Custom lint guards — the LuBot pattern applied to ML

LuBot's CI runs five of these as their own stages — SEAM RULE, per-tenant lint, monolith
size, OR-primary architecture, and a ruff complexity guard across all app code. They
enforce design decisions automatically instead of hoping a reviewer remembers. Same idea
here, because the rules that matter most are the ones nobody remembers at 3am:

- **`leakage_guard.py`** — the important one. Fails the commit if a feature function
  reads a dataframe without a time cutoff, or references a column on the forbidden list
  (anything only knowable after the fact). Allowlist for the handful of legitimate
  exceptions, same shape as the LuBot allowlists. **The leakage contract stops being a
  document nobody rereads and becomes a hook that fails the build**
- **`split_integrity_check.py`** — fails if the frozen split file changed. Once Phase 2
  writes it, a diff means someone re-rolled the split, which invalidates every number
  measured against it
- **`test_set_touch_check.py`** — the test set is opened once. This counts how many places
  load it and fails above the allowlist

### ML-specific tests LuBot does not need

- **Determinism** — same seed and same data produce a byte-identical model. Without this,
  "the GNN beat the baseline" cannot be reproduced tomorrow
- **Data contracts** — Pandera schemas asserted as tests, not just applied at runtime
- **Behaviour fixtures** — a handful of hand-built subgraphs (a clean fan-out, a clean
  cycle, an obviously innocent account) that the model must score correctly. These test
  behaviour, not accuracy, and they catch a broken pipeline that metrics would hide
- **Metamorphic tests** — multiply every amount by 10 and the ranking should stay stable.
  Rename an account and nothing should change. Cheap tests that catch real bugs
- **Train/serve parity** — the same transaction through the batch path and the online path
  must produce the same features. Asserted, not eyeballed
- **Latency budget in CI** — p99 under 50ms is an assertion that fails the build, not a
  number in a README that quietly rots
- **The evaluation harness is itself tested first.** If `evaluate()` is wrong, every
  result in the project is wrong and nothing downstream would reveal it

### Agent rules (Matt Harrison p.307, unchanged)

Test behaviour not structure. Do not over-assert. No randomness, time, or network in unit
tests. If a test fails, fix the implementation. **If the agent weakens a test to make it
pass, reject it** — and in this project that includes quietly relaxing a leakage guard.

---

## The things most likely to go wrong

Written down now so they are not surprises later.

**Temporal leakage sneaks in through the graph.** The most likely failure, and the
hardest to see. Mitigation: rule 2 is checked in Phase 4 with an explicit test, not by
eye.

**The GNN does not beat the baseline.** Genuinely possible at 5M rows. Mitigation: it
gets written up honestly, and Phase 9 tests whether it holds on a second dataset and Phase 10 whether more data changes it.

**The synthetic data turns out to be too easy.** If everything scores 0.99, the project
is boring and proves nothing. Check for this early, in Phase 2, when the dumb baselines
are scored. If "rank by amount" already does well, the simulator's patterns are too
obvious and we switch to the LI variants, which have a lower illicit ratio and are
deliberately harder. Better to find that out in Phase 2 than Phase 4.

**CPU training is too slow to iterate.** Likely at some point. Mitigation: rent a GPU
for a few hours, roughly $0.50/hr. No hardware purchase.

**Stored features go stale and nobody notices.** Mitigation: staleness is a monitored
metric in Phase 8, not an assumption in Phase 5.

**Scope creep into a second problem.** Card fraud and laundering are different problems.
This project is laundering only. Card fraud is a different repo, later, or never.
