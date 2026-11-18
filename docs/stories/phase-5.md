# Phase 5 — Serving it for real: stories

**Status:** approved by Lubo 2026-11-18. S5.1, S5.2 and S5.3 done; S5.6a next.

**How stories are expanded:** one at a time, just before work starts on it (Lubo,
2026-11-18). The next story gets the full treatment — Given/When/Then criteria, Definition
of Done, tasks, estimate, dependencies, out of scope, risks — using what the previous
one taught us. Stories below the current one stay short until their turn.

## Main goal

A scoring endpoint **on k3s** that the Phase 6 stream can call for every transaction:
fast enough (p99 under 50ms), honest about accounts it has never seen, always traceable
to one exact model artifact, and small enough to live beside LuBot production without
taking anything from it.

**Epic / Definition of Done** (PLAN.md, Phase 5): a live endpoint on k3s, p99 measured
under budget there, the cold-account path tested rather than assumed, and the Ray and
Feast decisions recorded.

**Already done** (not re-storied): point-in-time online store with train/serve parity,
staleness measured (FINDING-008), scoring service, Ray Serve p99 7.71ms over HTTP
outside k3s, KubeRay deploy.

**Rules that apply to every story:** nothing named `lubot-*`, `forgejo`, `sentinel-*`
or `aws-job-streamer` is touched. Never `k3s-killall.sh`. Ask before starting any new
container or creating any AWS resource. Every container keeps a hard memory cap.

---

## S5.1 — Bring the k3s endpoint back

**As an** operator, **I want** the scorer pod running on k3s again, **so that** there
is a live endpoint to measure and build Phase 6 on.

Acceptance criteria:
- [x] `graphguard/serving:0.1.2` is present in k3s containerd (re-imported from Docker,
      not rebuilt) — digest `sha256:9e2d3c73…` matches Docker's
- [x] The scorer head pod is `Running` and `Ready`; `just k8s-smoke` returns healthy;
      RayService `Running`, Serve app `RUNNING`
- [x] One scoring request through the cluster service returns a score — and a request
      with two stored accounts returns `cold: false` with staleness, proving the pod
      reaches Redis (512,707 accounts in the store)
- [x] The ~300 dead evicted/completed `kuberay-operator` pods are cleaned up; the one
      running operator is untouched
- [x] LuBot unaffected: same 70 containers before and after (51 `lubot-*` / `forgejo` /
      `sentinel-*`, all Up), Docker's iptables chain 48 → 48 rules, lubot.ai/health,
      staging, git.lubot.ai, lubobali.com all 200 before and after

Done 2026-11-18. The image is also pinned already (S5.2's first criterion), because the
import pushed disk to 84%, one point under kubelet's default 85% GC threshold.

Rolls up to: "a live endpoint on k3s".

## S5.2 — The image cannot silently disappear again

**As an** operator, **I want** the serving image protected from k3s image garbage
collection, **so that** a disk-full day does not take the endpoint down for weeks
unnoticed.

Acceptance criteria:
- [x] The imported image is pinned (verified label for this k3s version, not assumed) —
      `io.cri-containerd.pinned=pinned`, CRI reports `"pinned": true` (k3s v1.36.3,
      containerd v2.3.2)
- [x] `just image-build` pins on every import, so the fix survives the next version —
      via the new `just image-import` (also usable alone, no rebuild)
- [x] A check (`just k8s-status` or similar) says loudly when the pod is not Ready —
      `just k8s-check` (`graphguard.ops.k8s_health`): exit 1 and a
      `GRAPHGUARD K8S UNHEALTHY:` line per problem for any pod not ready (with the
      waiting reason, e.g. ImagePullBackOff), no live pods, or the image missing or
      unpinned. 10 unit tests; run live, healthy → 0, missing image → 1.
      `just k8s-status` calls it too
- [x] A runbook for when it fires: `docs/runbooks/scorer-down.md`
- [—] **Run on a schedule, with an email on state change** — *moved to the start of
      Phase 6* (Lubo, 2026-11-18). Nothing depends on the endpoint yet; the stream will.
      Plan: cron every 15 min, email only when healthy↔broken changes, sent with Python's
      smtplib (nothing installed box-wide), Gmail app password in `.secrets/`. Phase 8
      monitoring replaces it

S5.2 done 2026-11-18, with the alert deferred as above.
- [x] Old unused images (`serving:0.1.0`, `0.1.1`) removed from Docker, disk recorded
      before and after — removed 2026-11-18 in a box-wide cleanup run by the LuBot
      session (disk 77% → 58%, 51GB → 92GB free); GraphGuard re-verified after: pod,
      RayService, pin, Redis (512,707 keys), MLflow UI and a scoring request all intact

Rolls up to: "a live endpoint on k3s" — one that stays live.

## S5.3 — Keep Ray Serve, and make it fit and safe

**Decision already made (Lubo, 2026-11-18):** Ray Serve stays. This story is not
"Ray or FastAPI"; it is "Ray, proven to fit the budget and closed to attack".

**User story**
**As the** owner of a 4GB memory budget on a box that runs LuBot production, **I want**
Ray Serve's real memory measured, right-sized and its security checked, **so that** the
scorer can run for months beside LuBot without starving it, and I can explain the
trade-off in an interview.

**Acceptance criteria**
- [x] **Given** the scorer is idle, **when** memory is read from the pod's cgroup (not
      from the YAML), **then** the idle figure is recorded — **1,920 MiB** (anon 1,861);
      the model replicas are 2 × 377 MiB, the rest is Ray's own machinery
- [x] **Given** a burst of 2,000 real validation transactions, **when** memory is read
      during the burst, **then** the peak figure is recorded — **1,965 MiB** peak
      (cgroup `memory.peak`); p99 7.83ms through the k3s service on the way (a small load generator
      here; the formal latency run is S5.4)
- [x] **Given** all GraphGuard parts (k3s, Ray, MLflow, its Postgres, Redis), **when**
      their memory is added up, **then** the total is written down against the 4GB
      budget — k3s 792 + Ray 1,965 + kube helpers ~40 + MLflow 96 + MLflow DB 22 +
      Redis 32 + runner 21 ≈ **2.97 GB idle**, ~3.6 GB with MLflow busy. Fits, tightly
- [x] *(not needed — under budget)* **If** the total is over budget, **then** Ray is right-sized — fewer replicas,
      smaller object store, a tighter memory limit — and re-measured until it fits,
      with p99 still under 50ms
- [x] The pod's memory **limit** sits a safe margin above the measured peak (not 3Gi
      by habit), and the **request** matches real use — limit 3Gi → **2560Mi**, request
      2Gi kept (real use ~1.9 GiB). Zero-downtime rollout by KubeRay; peak after 1,928
      MiB, p99 7.57ms warm
- [x] Ray version is ≥ 2.52 (CVE-2025-62593, actively exploited); if not, upgraded
      and re-verified with `just k8s-check` and one scoring request — **2.58.0**, no
      upgrade needed
- [x] The Ray dashboard (port 8265) is reachable only inside the cluster — verified by
      trying from the host, not assumed from the Service type. **Was open to every
      Docker container** (`/api/jobs/` answered 200 from `graphguard-mlflow`). Fixed with
      `k8s/networkpolicy.yaml` (default-deny ingress; KubeRay operator allowed; only
      :8000 open). After: dashboard BLOCKED from Docker, :8000 open, scoring works,
      operator ran 162 serve-status checks in 6 min with 0 errors. The host itself can
      still reach it — kube-router always admits node-local traffic, and the host is
      root already. `just k8s-check` alarms if the policies go missing; `k8s-deploy`
      applies them first
- [x] `docs/adr/0001-serving-runtime.md` written: context, options (Ray Serve, FastAPI,
      BentoML), decision, the measured numbers, consequences
- [x] LuBot unaffected: same containers, lubot.ai 200, before and after any change —
      70 containers and all four sites 200, checked around both the NetworkPolicy and
      the resize

**Definition of Done:** every box above ticked, `just check` green, committed and
pushed with both remotes matching. Rolls up to the phase gate: "the Ray decision
recorded".

**Tasks**
1. Read the cgroup memory of the Ray head pod while idle
2. Write a small burst script (reuses the validation transactions) and read peak memory
3. Read memory for k3s, MLflow, Postgres, Redis; add it up
4. Check the Ray version inside the image; check where 8265 is reachable from
5. If over budget or unpatched: change `k8s/rayservice.yaml` (replicas, object store,
   limits) or the image's Ray pin; redeploy; re-measure
6. Write ADR 0001
7. LuBot before/after check; commit; push

**Estimate:** 3 story points, about one session. Up to 5 if Ray must be upgraded,
because that means rebuilding the image.

**Dependencies:** S5.1 (live pod) ✅. Nothing else. S5.4 depends on this, because p99
must be measured on the final, right-sized Ray.

**Out of scope:** replacing Ray (decided against); the formal p99 report (S5.4);
monitoring dashboards (Phase 8).

**Risks**
- *Ray needs a version upgrade* → image rebuild, ~2.3GB build. Disk is fine now (92GB
  free); the build cache grows again, which is expected
- *Right-sizing makes it slower* → every change is re-checked against p99 < 50ms before
  it is kept
- *Upgrading breaks KubeRay compatibility* → check the KubeRay/Ray version matrix first;
  the current image stays in Docker as the rollback

## S5.4 — p99 measured on k3s, not just on the laptop path

**As a** hiring manager reading the repo, **I want** the latency number measured on
the real k3s deployment, **so that** "p99 under 50ms" is a fact about production, not
about a dev setup.

Acceptance criteria:
- [ ] Given 2,000 real validation transactions, when sent through the k3s service,
      then p50 / p95 / p99 are reported and **p99 < 50ms**
- [ ] Measured through the cluster network path the stream will use, warm-up excluded
      and stated
- [ ] The number and how it was measured are recorded (findings or MLflow), next to
      the earlier 7.71ms outside k3s
- [ ] The CI latency assertion still exists and still fails the build above budget

Rolls up to: "p99 measured under budget there".

## S5.5 — A never-seen account gets a defined, tested answer

**As an** investigator, **I want** a transaction from a brand-new account scored in a
known, documented way, **so that** new accounts — which arrive constantly — are never
an error and never silently treated as "known clean".

Acceptance criteria:
- [ ] Given an account with no stored features, when scored, then the response is
      successful, says `cold = true` for that side, and the score uses the documented
      fallback
- [ ] Given both accounts are cold, the same holds for both
- [ ] Given a warm account, `cold = false` (already observed — now asserted)
- [ ] Given Redis is unreachable, the service **fails loudly** (error / unhealthy), and
      does not quietly report every account as cold — found during S5.1: a cold answer
      and a broken store must never look the same
- [ ] Covered by a unit test and an integration test against real Redis
- [ ] The cold-account rate in the S5.4 run is reported

Rolls up to: "the cold-account path tested rather than assumed".

## S5.6 — A small lakehouse (epic)

*Research: `docs/research/Open source lakehouse on one box.md` (2026-11-18). Catalog
decision (Lakekeeper; Polaris only if measured to fit; PyIceberg SQL catalog as the
zero-RAM fallback) agreed with Lubo the same day.*

**Why:** the account profiles exist only in Redis, which keeps nothing on disk, and the
only way to refill it today is `just build-artifacts` — which **retrains the model** to
do it. There is no versioned copy of the features a model was trained on. A lakehouse
fixes all three, and it is the same shape Databricks and Snowflake use: Iceberg tables,
a REST catalog, object storage, engines as jobs.

| Step | Story | New resident RAM (est.) | Needs Lubo |
|---|---|---|---|
| **L0 + L1** | **S5.6a — Iceberg tables on local disk, Redis rebuilt from them** | 0 | no |
| L2 | S5.6b — Warehouse on our own S3; DuckDB for SQL | 0 | AWS bucket + IAM user |
| L3 | S5.6c — Lakekeeper REST catalog; late labels via MERGE | 30-100MB | start a container |
| L4 | S5.6d — Governance: grants, vended credentials, the sealed test set as a denied permission | 50-150MB | start a container |
| L5 | S5.6e — Feast over Iceberg → Redis, lineage, marimo worksheets | 0 | no |

Maintenance with Dagster is Phase 8 (L6); Spark on the same tables is Phase 10 (L7).
**Every step has a measurement gate:** it stays only if its measured RAM fits.

---

### S5.6a — Iceberg tables on local disk, Redis rebuilt from them

**User story**
**As an** ML engineer, **I want** the transactions, features and labels kept in
versioned Iceberg tables (bronze / silver / gold), with Redis rebuilt *from* the gold
table, **so that** every model can be traced to the exact rows it trained on, a Redis
restart is a two-minute reload instead of a retrain, and the platform has one source of
truth.

**Acceptance criteria**

*L0 — baseline, before anything changes*
- [x] Peak memory of today's feature build + Redis fill measured (`/usr/bin/time -v`),
      plus `free -h` and `docker stats`, written down — 2026-11-18:
      - Account-state build (Polars, no write): **2.8s, peak RSS 1.42 GB**, 512,705
        accounts. A job-time peak above the ~1 GB spare, so it must not overlap with
        Ray at peak plus a busy MLflow
      - Redis: `used_memory` 159 MB of `maxmemory` 200 MB (**80%**, noeviction — a fill
        that grows it ~25% would start failing writes); RSS 41 MB with fragmentation
        ratio 0.26, i.e. **most of Redis's memory is in swap** on this swap-full box
      - Redis holds **512,708 keys, not 512,705**: three `test:acct:*` keys left by the
        integration tests, which run against the **live** Redis (db 0, namespace
        `test`). Docker: Redis 45 MiB, MLflow 99 MiB, MLflow DB 23 MiB. Disk 92 GB free
- [ ] Integration tests use their **own Redis database** (not db 0), clean up after
      themselves, and **fail rather than silently skip** when Redis is unreachable or
      needs a password (`_redis_available()` skips today — with S5.8a's password it
      would quietly stop testing Redis at all)
- [ ] Key-count checks count `gg:acct:*` only

*The catalog and the warehouse*
- [ ] PyIceberg **SQL catalog in its own database** (`lakehouse`, own DB user) inside the
      existing MLflow Postgres — not SQLite, which PyIceberg calls development-only
- [ ] Warehouse on local disk under `/srv/graphguard/lakehouse/` (gitignored); disk use
      measured against the 25GB budget
- [ ] Tables are **Iceberg format v2**, set explicitly (v3 support is uneven in Polars
      and PyIceberg)
- [ ] Namespaces `bronze`, `silver`, `gold`, and `sealed`

*The tables*
- [ ] `bronze.transactions_raw` — the CSV, typed, nothing else changed
- [ ] `silver.transactions` — cleaned, typed, partitioned by day, artifacts excluded the
      same way FINDING-006 does
- [ ] `gold.account_features_asof` — each account's profile **as of** a time, from the
      **same feature code training uses**
- [ ] `gold.labels` — the label plus the time it became known (for Phase 6's label delay)
- [ ] **Test-window rows go only to `sealed`**, which training code never reads;
      `test_set_touch_check` still counts zero unapproved loads

*Correctness — the leakage contract on the new path*
- [ ] **Given** the same transactions, **when** features come from `gold`, **then** they
      equal the features from today's path (parity test)
- [ ] **Given** a transaction at time T, **when** its account features are joined,
      **then** only events strictly before T are used — a unit test for the
      exact-same-timestamp edge
- [ ] **Given** the same bronze snapshot, **when** silver and gold are rebuilt twice,
      **then** the contents are identical (determinism)
- [ ] One **Pandera schema per layer**, asserted as tests, not only applied at runtime
- [ ] All three leakage guards pass

*Versioning and traceability*
- [ ] **Time travel**: write, append, read the old snapshot id → the old rows
- [ ] Every training run logs to MLflow: table names, **Iceberg snapshot ids**, the
      frozen-split sha256 and the git sha
- [ ] `expire_snapshots` keeps the last N snapshots; N written down

*Redis, rebuilt from gold*
- [ ] **Train and load are separate**: a new `just store-load` fills Redis from
      `gold.account_features_asof` **without retraining**
- [ ] After a reload: key count equals before (512,707), and 2,000 real validation
      requests return **the same scores** as before the change
- [ ] The reload is timed and the time written into the runbook

*Everywhere*
- [ ] Peak RAM of the new jobs measured; nothing new runs all the time
- [ ] `just check` green; committed; pushed; remotes match; LuBot untouched (no new
      containers in this story)

**Definition of Done:** every box ticked, nothing weakened; the scorer gives identical
scores from the rebuilt store; rolls up to the Phase 5 gate without degrading it.

**Tasks**
1. L0 baseline measurements
2. Add `pyiceberg` (and its SQL extra) to the project via `uv` — project-only, the
   lockfile updated, nothing installed box-wide
3. Create the `lakehouse` database and user in the existing Postgres; credentials in
   `.secrets/`
4. Tests first: parity, strict-before as-of edge, determinism, time travel, Pandera per
   layer, the sealed-namespace rule
5. Write bronze → silver → gold with Polars, through PyIceberg
6. Split `build_artifacts` into train and `store-load`; load Redis from gold; compare
   key count and 2,000 scores
7. Log snapshot ids to MLflow; add `expire_snapshots`
8. Measure RAM and disk; update the runbook; commit; push

**Estimate:** 8 story points, 2-3 sessions. The biggest of Phase 5, because it changes
how data flows.

**Dependencies:** S5.3 ✅. The existing Postgres. Nothing outside GraphGuard; no new
container.

**Out of scope:** S3 and DuckDB (S5.6b), Lakekeeper (S5.6c), permissions (S5.6d), Feast
(S5.6e), Redis persistence settings (S5.8a), retraining the production model.

**Risks**
- *Polars 1.43.2's Iceberg writer is marked unstable* → write through PyIceberg with
  Arrow tables, which is the stable path; do not upgrade Polars inside this story
  (that is its own step, behind the determinism test)
- *Features from the new path differ slightly* → the parity test catches it before the
  scorer ever sees it; differences get investigated, never tolerated
- *The catalog lives in MLflow's Postgres* → one database to back up (S5.8c), and a
  separate DB user so neither can touch the other's tables
- *Disk*: compressed Parquet for 5M rows is expected in the low hundreds of MB, measured
  in task 8
- *Upsert memory*: PyIceberg upserts used ~80GB for 34M rows in one report → tables are
  append-only by design; late labels wait for DuckDB MERGE in S5.6c

### S5.6b — Warehouse on our own S3; DuckDB *(short until its turn)*
Move the warehouse to our own S3 bucket (own IAM user, Lubo signs off). Add DuckDB 2.0
for SQL, with an as-of parity check against Polars. Same results from S3 as from disk.

### S5.6c — Lakekeeper REST catalog *(short until its turn)*
Lakekeeper as the catalog, capped, internal only; existing tables registered. Late labels
updated with DuckDB `MERGE INTO`. Stays only if its measured RAM fits; otherwise the SQL
catalog remains.

### S5.6d — Governance *(short until its turn)*
Grants and vended credentials. The sealed test set becomes a **permission denial with a
negative test**: the training identity cannot read `sealed`.

### S5.6e — Feast, lineage, worksheets *(short until its turn)*
Feast (library) over Iceberg → Redis, asserted equal to the Polars output (ADR 0002 on
Feast). OpenLineage audit records. marimo worksheets, started only when needed.

## S5.7 — The running model is traceable to one artifact

**As a** model-risk reviewer, **I want** the service to load its model from S3 at
startup and report exactly which artifact it runs, **so that** every score can be tied
to one versioned, checksummed model.

Acceptance criteria:
- [ ] GraphGuard's **own** S3 bucket and IAM user scoped to that bucket only; nothing
      belonging to `aws-job-streamer` is read or edited (Lubo approves before any AWS
      resource is created)
- [ ] At startup the service downloads the model bundle by version, verifies its
      sha256, and refuses to start on a mismatch
- [ ] `/health` reports model version and sha256
- [ ] The CI startup stage imports the app, loads the model from S3, and answers one
      scoring request
- [ ] Credentials live outside git (k8s secret / `.secrets/`), never in the image

Rolls up to: the plan's "model pulled from S3 at startup" requirement.

## S5.8 — Lock down GraphGuard, and keep the whole box safe (epic)

**Why:** the box was hacked once. A read-only inventory (2026-11-18) found it well
guarded from the internet — the Hetzner firewall admits only TCP 80/443, SSH is key-only
and reached over Tailscale — but soft inside: no host firewall, and several GraphGuard
parts unhardened. GraphGuard must never be the weak door into LuBot or anything else.

**Split by risk, lowest first.** Each sub-story is expanded fully just before it starts.

| | Sub-story | Touches | Risk |
|---|---|---|---|
| **S5.8a** | Harden GraphGuard's own containers and pod | only GraphGuard | low |
| S5.8b | Supply chain: CI runner, pinned actions, secret scanning | only GraphGuard | low |
| S5.8c | Backups: MLflow off the box, with a tested restore | GraphGuard + a new B2 bucket | low, needs Lubo |
| S5.8d | k3s control plane off the public interface; second wall for the box | box-wide | **high**, with the LuBot session |

Facts already established: Hetzner firewall = TCP 80/443 inbound only (Lubo's console,
2026-11-18). Ray dashboard locked by NetworkPolicy (S5.3). Scorer runs as uid 10001.

---

### S5.8a — Harden GraphGuard's own containers and pod

**User story**
**As the** owner of a box that was hacked once, **I want** every GraphGuard container
and pod locked down to the standard of `lubot-prod-backend`, **so that** if any one of
them is ever broken into, the attacker gets as little as possible and cannot reach
further.

**Acceptance criteria**

*Redis — the online store*
- [ ] **Given** a client with no password, **when** it runs any command, **then** Redis
      answers `NOAUTH`. The password lives in `.secrets/redis.env` (600, gitignored)
- [ ] The scorer gets the password from a **Kubernetes Secret**, never from the YAML,
      the image or git; host tools get it from `.secrets/`
- [ ] **Before any Redis restart**, the reload is proven: `just build-artifacts` (or a
      new `just store-load`) refills all accounts, timed and written down — Redis keeps
      nothing on disk by design, so a restart empties it
- [ ] **Given** Redis was restarted, **when** the store is reloaded, **then** the key
      count matches before (512,707) and a stored account scores `cold: false`

*Compose containers (Redis, MLflow, MLflow Postgres)*
- [ ] `cap_drop: [ALL]`, adding back only what each image's entrypoint is shown to need
- [ ] `security_opt: [no-new-privileges:true]`
- [ ] `pids_limit` and log rotation (`max-size`, `max-file`) on each
- [ ] Images pinned by **digest**, not just tag
- [ ] Each container healthy after the change; MLflow UI 200; runs and experiments still
      listed; Postgres data intact

*The scorer pod*
- [ ] `securityContext`: `runAsNonRoot: true`, `runAsUser: 10001`,
      `allowPrivilegeEscalation: false`, `capabilities: drop [ALL]`,
      `seccompProfile: RuntimeDefault`
- [ ] `readOnlyRootFilesystem: true` with a writable `emptyDir` for `/tmp` (Ray writes
      `/tmp/ray`). **If** Ray needs to write anywhere else, that path gets its own
      `emptyDir` — or, if it cannot be made to work, the exception is written down
      with the reason, never silently dropped
- [ ] After: `just k8s-check` healthy, p99 under 50ms, dashboard still blocked from Docker

*Everywhere*
- [ ] LuBot before/after: same containers, all sites 200
- [ ] `just check` green; committed; pushed; remotes match

**Definition of Done:** every box ticked, nothing weakened to make it pass, rolls up to
the Phase 5 gate (a live endpoint) without degrading it.

**Tasks**
1. Time the store reload on the current Redis *before* changing it (dry run into a
   scratch DB number, so live keys are untouched)
2. Generate the Redis password into `.secrets/redis.env`; create the k8s Secret
3. Make `store.py`'s default URL read the password from env/`.secrets/` (test first:
   URL with password parsed, no password still works for unit tests)
4. Compose: password, `cap_drop`, `no-new-privileges`, `pids_limit`, logging, digests —
   one container at a time, each verified before the next
5. Restart Redis, reload, verify count and a warm score
6. Pod `securityContext` + read-only root + `emptyDir`; roll out (KubeRay, zero
   downtime); verify
7. LuBot check; `just check`; commit; push

**Estimate:** 5 story points, 1-2 sessions.

**Dependencies:** S5.3 ✅. Nothing outside GraphGuard.

**Out of scope:** k3s flags and kubeconfig permissions (S5.8d — needs a k3s restart);
the CI runner (S5.8b); backups (S5.8c); anything LuBot's.

**Risks**
- *A Redis restart empties the store* → reload proven and timed first (task 1); the
  scorer is briefly "everything cold" during the reload — acceptable now, nothing
  depends on it yet. Also ties to S5.5: an empty store must not look like a healthy one
- *Postgres entrypoint needs capabilities `cap_drop: ALL` removes* → add back only the
  ones it fails without, one at a time, from the error
- *Ray refuses a read-only root* → `emptyDir` per path it needs; if it truly cannot,
  record the exception in ADR 0001 rather than fake it
- *MLflow restart loses nothing* (its data is in Postgres and a volume) — confirmed by
  listing runs before and after

---

### S5.8b — Supply chain *(short until its turn)*
**As the** owner, **I want** CI jobs and commits unable to leak secrets or run tampered
code, **so that** the build pipeline is not a way in.
- Runner job containers: `--cap-drop=ALL`, `no-new-privileges`, a network per job
  (pattern: `lubobali-runner`). Runner today: no Docker socket ✅, limits ✅, shared
  `bridge` network ❌
- `actions/checkout` pinned by commit SHA, not `@v4`
- gitleaks in prek and CI (pattern: lubobali CI)

### S5.8c — Backups *(short until its turn)*
**As the** owner, **I want** MLflow's history backed up off the box with a restore that
is actually tested, **so that** a dead disk does not erase every experiment.
- Own restic repo in an own B2 bucket (Lubo creates bucket + key; nothing of LuBot's
  backup reused). Daily; restore-check timer (pattern: MissionCopilot)
- The online store needs no backup — it is rebuilt from data (S5.8a proves how fast)

### S5.8d — k3s control plane and the box's second wall *(short until its turn)*
**As the** owner, **I want** k3s's admin ports off the public interface and a host
firewall behind the Hetzner one, **so that** one mistake in the Hetzner console does not
expose the box.
- Today: k3s API `*:6443`, kubelet `*:10250`, flannel `0.0.0.0:8472/udp` (all blocked
  by Hetzner, but bound publicly); kubeconfig `644`
- k3s flags (bind address, kubeconfig mode `600`) — needs a k3s **service restart**,
  never `k3s-killall.sh`
- Host firewall: planned with a rollback, applied by ONE session together with the
  LuBot session, every app verified. Never by surprise
- LuBot findings handed over (theirs to fix): Docker socket in the backend, runner host
  networking and token perms, staging `.env` 644, admin ports on 0.0.0.0, open
  credential rotations

---

## Order

S5.1 → S5.2 → S5.3 → **S5.6a** → S5.6b-e → S5.8a-d → S5.4 → S5.5 → S5.7

Lakehouse before lockdown (Lubo, 2026-11-18): build the Redis reload once, the right
way, then harden. The box stays as it is meanwhile — internet blocked by Hetzner, Ray
dashboard locked (S5.3).

S5.1-S5.2 first because nothing can be measured on a dead pod. S5.3 before S5.4 because
if Ray goes, the latency must be measured on what replaces it. S5.7 last because it
needs AWS setup and Lubo's sign-off.
