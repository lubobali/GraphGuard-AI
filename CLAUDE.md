# GraphGuard-AI

Real-time money laundering detection with a graph neural network, on the IBM AMLworld
dataset.

**Full build plan:** `PLAN.md`. Read it before starting a phase — this file is the rules,
that file is the work.

> **Naming note:** PLAN.md calls this project "Riskline" (`/srv/riskline`,
> `riskline.lubot.ai`). That name is dead. The project is **GraphGuard-AI**, it lives in
> `/srv/graphguard`, and it is one project, not two.

---

## Why this exists

Lubo has shipped a lot of AI systems but has never trained and deployed a model. That gap
blocks him in ML interviews. This project closes it.

**The bar is not "it runs."** The bar is that a senior ML engineer reads this repo and
cannot find the shortcut. Most portfolio ML projects fail that read in two minutes —
leakage, an unfair baseline, or a metric that flatters the result. This one has to survive
it.

Consequences that follow from that bar:

- The dataset is **synthetic** (IBM's simulator). Say so out loud, first, every time.
- The tabular baseline gets a **real** effort, including graph features. A weak baseline
  makes the GNN result worthless.
- **If the GNN loses, that gets written up as a finding.** Do not tune the GNN against the
  test set to avoid that outcome.
- Primary metric is **precision@k**, not AUC. At a 0.1% fraud rate, 0.99 AUC can still be
  a worthless queue.

---

## The leakage contract

The thing most likely to quietly invalidate everything downstream. Every phase holds to it.

1. **Split by time, never randomly.** Earliest window trains, middle validates, latest
   tests. Frozen once at the start of Phase 2, before any model is trained.
2. **The graph at time T contains only edges before T.** Building the graph over full
   history and then splitting is leakage, even though the split looks correct.
3. **No feature may use information that did not exist at decision time.** Account degree
   means degree *as of that moment*, not final degree.
4. **The test window is opened once.** Every tuning decision is made on validation.
5. **A feature that looks too good gets investigated, not celebrated.** One feature
   carrying most of the signal is usually leakage, not luck.

**If any rule is violated, the result is void and gets rebuilt.** No exceptions, no "good
enough for a portfolio."

Three lint guards enforce this mechanically, so it is a build failure and not a document
nobody rereads: `leakage_guard.py`, `split_integrity_check.py`, `test_set_touch_check.py`.

---

## Hard rules on this box

This server runs **LuBot production**. ~15 `lubot-*` containers are live right now.

**Off limits — never touch, restart, read, or write:**

- anything named `lubot-*`, `forgejo`, `sentinel-*`
- anything under `/srv/lubot-*`
- **`aws-job-streamer`** and every AWS resource it owns. It is a live public resume
  artifact. No existing bucket, role, or policy gets edited.

**GraphGuard's own everything.** Own containers, own Docker network, own volumes, own
ports, own Postgres and Redis (not LuBot's), own S3 bucket, own IAM user scoped to that
bucket only. Everything lives in `/srv/graphguard`.

**Hard memory caps on every container.** Not optional — swap on this box sits at ~99%
full.

**Ask before:** installing anything system-wide, or starting any container.

Budget: ~4GB RAM, ~25GB disk. Box has 8 cores, ~19GB RAM available, ~96GB disk free.
Keep it that way.

---

## CI and remotes

**Forgejo repo:** `lubo/GraphGuard-AI` (private) at https://git.lubot.ai/lubo/GraphGuard-AI
Separate repo from `lubot`, `lubot-publisher`, `sentinel-ai`.

**`git push` goes to BOTH remotes.** `origin` fetches from GitHub and has two push URLs
(GitHub + Forgejo). After a push that matters, confirm they match:

```
git ls-remote origin refs/heads/main   # GitHub
git ls-remote forgejo refs/heads/main  # Forgejo
```

If one remote fails, git does **not** roll back the other — they can drift.

**Workflows must use `runs-on: graphguard`.** Not `ubuntu-latest` (queues forever), and
never LuBot's runner.

**The runner:** `graphguard-runner.service`, own systemd unit, registered to this repo
only. State in `/srv/graphguard/runner/` — gitignored, `chmod 600`, holds the runner
credential. Daemon capped at 1G; **each job container capped at 2G, verified in CI, not
assumed**. One job at a time, 45m timeout, image `node:20-bookworm-slim`.

`forgejo-runner.service` (LuBot) and `sentinel-runner.service` are **not ours** — never
touch them.

**Forgejo task IDs are global across the instance.** A task number near ours may belong
to LuBot. Confirm ownership in the runner log (`task N repo is lubo/GraphGuard-AI`)
before inspecting anything.

**Known cost, not yet fixed:** the job installs `git` and `curl` via apt on every run
(~7s of a 14s build). Replace with a prebuilt image once the real CI exists.

---

## Local services

`just mlflow-up` / `mlflow-down` / `mlflow-status` / `mlflow-logs`.

| | |
|---|---|
| MLflow UI | `127.0.0.1:5010` (localhost only - tunnel over ssh) |
| MLflow Postgres | `127.0.0.1:5434` |
| Compose project | `graphguard` |
| Network | `graphguard-net` |
| Volumes | `graphguard-mlflow-db-data`, `graphguard-mlflow-artifacts` |
| Memory caps | MLflow 1200M, Postgres 512M |

Ports 5000, 5432 and 5433 were already taken on this host, which is why these
are 5010 and 5434. **Credentials live in `.secrets/`** - gitignored, `chmod 600`,
generated locally and never committed. `.secrets/kaggle.json` holds the Kaggle
token, `.secrets/mlflow.env` the database password.

MLflow idles at ~695MB, so its cap is 1200M rather than the 768M first tried -
at 768M it sat at 91% of its limit and would have been OOM-killed under load.

---

## How we work

**One step at a time.** Do a step, stop, say what was done and what is next. Do not run
ahead through a whole phase.

**RECR loop:**
1. Write the test first
2. Implement one task
3. Check it
4. Repeat

**Non-negotiable:**
- **Never weaken a test to make it pass.** That explicitly includes quietly relaxing a
  leakage guard.
- **Zero failures before moving forward.** No "pre-existing failures" excuse.
- Mock only external things.
- If a phase turns out to be wrong, redo it rather than build on it.

Lubo is learning ML as we go. Explain concepts in simple terms when they come up — short
answers, not essays.

---

## Testing environment

Stood up in Phase 0, before any modelling code exists.

**From LuBot:**
- pytest strict mode — `--strict-markers --strict-config`, `xfail_strict = true`
- Marker taxonomy — categories (`unit`, `db`, `gpu`, `slow`) plus labels (`integration`,
  `regression`). Default run deselects slow ones
- Ruff — `E,F,I,W,B,PLR0912,PLR0915,C901`, ceiling that passes today, tightened later
- prek hooks — ruff lint, ruff format, unit suite, scoped to `.py` changes
- xdist — `-n 4 --dist=loadgroup`, **identical flags in prek and CI** (drift is a known
  LuBot failure mode)
- CI installs with **uv from the committed lockfile** — same lockfile as the container
- Unit and integration as separate stages
- Startup check as its own stage: the serving app must import, **load the model from S3,
  and answer one scoring request**

**ML-specific, which LuBot does not need:**
- **Determinism** — same seed + same data = byte-identical model
- **Data contracts** — Pandera schemas asserted as tests, not just applied at runtime
- **Behaviour fixtures** — hand-built subgraphs (clean fan-out, clean cycle, obviously
  innocent account) the model must score correctly
- **Metamorphic tests** — ×10 every amount and the ranking should hold; rename an account
  and nothing changes
- **Train/serve parity** — same transaction through batch and online paths, asserted
- **Latency budget in CI** — p99 under 50ms is an assertion that fails the build
- **`evaluate()` is tested first.** If it is wrong, every result in the project is wrong
  and nothing downstream would reveal it

**Reproducibility:** uv with committed `uv.lock`, every seed fixed, every path in config.
One command from a clean clone. If a result cannot be reproduced, it does not count.

---

## Where we are

| Phase | What | Status |
|---|---|---|
| 0 | Ground — skeleton, data, test env, guards, MLflow | **done** (2026-08-19) |
| 1 | Understand the data before touching a model | **done** (2026-08-19) |
| 2 | Evaluation harness + frozen split + dumb baselines | **done** (2026-08-19) |
| 3 | Tabular baseline (XGBoost), built to actually win | **done** (2026-08-20) |
| 4 | The graph model (GraphSAGE, inductive) | **comparison done** (2026-08-20) |
| 5 | Serving — Feast, Ray Serve on k3s, p99 < 50ms | not started |
| 6 | The stream — Redpanda, replayed in true time order | not started |
| 7 | The interface — alert queue, the ring drawn, capacity slider | not started |
| 8 | Monitoring, Airflow retraining, champion/challenger, write-up | not started |
| 8b | Make it findable — demo, video, post | not started |
| 9 | Scale to 180M, optional and honest | not started |

**Phase 0 gate — met 2026-08-19.** `./scripts/bootstrap.sh` takes a clean clone to
working, `just check` runs 32 tests + lint + the three guards clean, and
`just data-summary` prints 5,078,345 transactions / 515,080 accounts /
2022-09-01 to 2022-09-18 / 0.102% laundering.

**k3s and AWS were deferred**, not skipped. Neither is in the Phase 0 gate and
neither is needed before Phase 4-5. On a box this tight, idle services are a cost
with no benefit yet.

**Phase 1 gate — met 2026-08-19.** A ring is a shape across a median of 8 accounts
over 3 days: money split out, passed through, sometimes returned in a full circle.
Every individual hop is an ordinary amount (EUR 10,476, USD 15,471 in the examples
inspected). The signal does not exist in any single row, so a row-level model has
nothing to see. See `docs/findings.md` FINDING-002 and FINDING-003.

**Phase 2 gate — met 2026-08-19.** Split frozen at
`data/splits/frozen_split.json` (sha256 guarded on every commit). Both dumb
baselines scored on validation and logged to MLflow: random PR-AUC 0.00103,
by-amount 0.00170, neither catching any of the 168 labelled rings. See
FINDING-004.

**Phase 3 gate — met 2026-08-20.** Tuned artifact-free XGBoost reaches PR-AUC
**0.28155** on validation against 0.00170 for the best dumb baseline, catching
127 of 168 rings at k=5000. The leakage audit is written in
`docs/leakage_audit.md` with every top feature justified, and three generator
artifacts identified and excluded (FINDING-006). Test set still unopened.

**Phase 4 must compare the GNN against the tuned artifact-free tabular model**,
with the same Optuna trial budget. Comparing against the 0.360 figure, or
against an untuned baseline, would rig it.

**Phase 4 comparison — done 2026-08-20.** GraphSAGE reaches PR-AUC 0.04470 and
60/168 rings against XGBoost's 0.28155 and 127/168, on the same features, split,
entry point and 20-trial budget. The graph itself contributes 3.3x over the same
model with message passing disabled (0.06198 vs 0.01869 across the search), so
structure earns its place even though the tree wins overall. The dominant effect
was `pos_weight`: the exact class ratio of 1326 is correct for a tree and
destabilises gradient descent, and Optuna's 6.34 improved the GNN 8x. Full table
and caveats in `docs/model_comparison.md`, recorded as FINDING-007.

Still open in Phase 4: GNNExplainer, and S3/SageMaker which remain deferred.

**Scoring rules from here on.** Every model goes through
`graphguard.evaluation.evaluate.evaluate()` - one entry point, so no two models
are measured differently. Everything is scored on **validation**. The test split
stays sealed until the final evaluation (contract rule 4), and
`test_set_touch_check` counts the call sites.

Update this table when a phase gate actually passes — not when the code merely runs.
