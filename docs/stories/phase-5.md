# Phase 5 — Serving it for real: stories

**Status:** approved by Lubo 2026-11-18. S5.1, S5.2, S5.3, S5.6a, S5.6b and S5.6c done; S5.6d part 1 (logins + grants) done, part 2 (vended credentials) waits for Lubo's AWS step.

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
| L4 | S5.6d — Governance: Dex logins, OpenFGA grants, vended credentials, the sealed test set as a denied permission | 50-150MB | start two containers + one AWS step |
| L5 | S5.6e — Feast over Iceberg → Redis, lineage, marimo worksheets | 0 | no |

Maintenance with Dagster is Phase 8 (L6); Spark on the same tables is Phase 10 (L7).
**Every step has a measurement gate:** it stays only if its measured RAM fits.

---

### S5.6a — Iceberg tables on local disk, Redis rebuilt from them ✅ done 2026-11-18

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
- [x] Integration tests use their **own Redis database** (not db 0), clean up after
      themselves, and **fail rather than silently skip** when Redis is unreachable or
      needs a password (`_redis_available()` skips today — with S5.8a's password it
      would quietly stop testing Redis at all)
- [x] Key-count checks count `gg:acct:*` only — the 3 stray `test:acct:*` keys removed;
      live Redis holds exactly 512,705. Tests use db 15 and clean up (db 15 empty after);
      with no Redis they now **error** (7 errors), and CI skips them only via
      `GRAPHGUARD_SKIP_REDIS_TESTS=1`, reason printed

*The catalog and the warehouse*
- [x] PyIceberg **SQL catalog in its own database** (`lakehouse`, own DB user) inside the
      existing MLflow Postgres — not SQLite, which PyIceberg calls development-only. The
      `lakehouse` user is refused on `mlflow` (no CONNECT); MLflow UI unaffected
- [x] Warehouse on local disk under `/srv/graphguard/lakehouse/` (gitignored); disk use
      measured against the 25GB budget — ~250-400 MB per build, last 5 builds kept
      (~1.2 GB worst case); orphan files cleaned by our own `remove_orphan_files`
- [x] Tables are **Iceberg format v2**, set explicitly (v3 support is uneven in Polars
      and PyIceberg)
- [x] Namespaces `bronze`, `silver`, `gold`, and `sealed`

*The tables*
- [x] `bronze.transactions_raw` — the CSV, typed, nothing else changed — plus
      `source_row`, each row's position in the file: the transaction key the dataset
      lacks, and the order float sums depend on (FINDING-009)
- [x] `silver.transactions` — typed, partitioned by day, the post-Sep-10 tail removed
      exactly as `truncate_tail` does (FINDING-001). *(Wording fixed: FINDING-006's
      artifacts are feature columns, excluded at training, not rows)*
- [x] `gold.account_features_asof` — each account's profile **as of** a time, from the
      **same feature code training uses**
- [x] `gold.labels` — the label plus the time it became known (for Phase 6's label delay)
      — `label_known_at` is explicitly **null** until Phase 6 sets the policy; keyed by
      `source_row`
- [x] **Test-window rows go only to `sealed`**, which training code never reads;
      `test_set_touch_check` still counts zero unapproved loads — and now also fails on
      any mention of the `sealed` namespace outside `catalog.py`/`tables.py` (proven
      with a probe file)

*Correctness — the leakage contract on the new path*
- [x] **Given** the same transactions, **when** features come from `gold`, **then** they
      equal the features from today's path (parity test) — exact in unit tests; on real
      data the **train and validation feature frames from silver are bit-identical**
      to the CSV path, and gold matches live Redis exactly on counts and dates, with 62
      accounts 1 ulp off in a money sum (parallel chunking; FINDING-009)
- [x] **Given** a transaction at time T, **when** its account features are joined,
      **then** only events strictly before T are used — a unit test for the
      exact-same-timestamp edge
- [x] **Given** the same bronze snapshot, **when** silver and gold are rebuilt twice,
      **then** the contents are identical (determinism) — unit test, and on real data
      via time travel: each table identical to the previous build's snapshot
- [x] One **Pandera schema per layer**, asserted as tests, not only applied at runtime
- [x] All three leakage guards pass

*Versioning and traceability*
- [x] **Time travel**: write, append, read the old snapshot id → the old rows
- [x] Every training run logs to MLflow: table names, **Iceberg snapshot ids**, the
      frozen-split sha256 and the git sha — `build-artifacts` now trains from silver at
      a pinned snapshot and logs the lineage; verified on the real catalog (the
      production model was not retrained — out of scope)
- [x] `expire_snapshots` keeps the last N snapshots; N written down — N = 5, then
      orphaned files are deleted

*Redis, rebuilt from gold*
- [x] **Train and load are separate**: a new `just store-load` fills Redis from
      `gold.account_features_asof` **without retraining**
- [x] After a reload: key count equals before (512,705 real accounts; the "512,707" first written here
      included stray test keys), and 2,000 real validation
      requests return **the same scores** as before the change — **2,000 / 2,000
      identical**, score and both cold flags, max difference 0.0
- [x] The reload is timed and the time written into the runbook — 13.4 s, peak 0.55 GB,
      in place (overwrite then prune: the store is never empty mid-reload)

*Everywhere*
- [x] Peak RAM of the new jobs measured; nothing new runs all the time — build first
      peaked at **3.77 GB**; streaming day files + one-commit `add_files` + staging the
      CSV brought it to **1.12-1.19 GB** (per step 0.9-1.13 GB), below the old 1.42 GB
      job. Not to overlap busy MLflow + Ray at peak
- [x] `just check` green; committed; pushed; remotes match; LuBot untouched (no new
      containers in this story) — 271 tests

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

### S5.6b — The warehouse on our own S3, and DuckDB for SQL ✅ done 2026-11-18

**User story**
**As an** ML engineer, **I want** the lakehouse's files in GraphGuard's own S3 bucket
and a SQL engine that reads them, **so that** the data survives the box (a dead disk no
longer means rebuilding everything), the storage is real cloud object storage the way
Databricks and Snowflake use it, and the tables can be explored with plain SQL.

**Why now:** today every table lives on this box's disk. S3 costs ~$1/month at this
size, uses **zero** RAM or disk here, and is what S5.7 (model loaded from S3) and
S5.6c (Lakekeeper's credential vending) need anyway. Measured from the box: S3
us-east-1 answers in **3.7 ms** to connect, 24 ms to first byte — same region.

**Acceptance criteria**

*AWS — created by Lubo from a checklist (the one step that is his)*
- [x] A **new** bucket for GraphGuard only, us-east-1, Block Public Access on,
      versioning on, default encryption on. Nothing belonging to `aws-job-streamer`
      is read, reused or edited — `graphguard-lakehouse-0dcd18`, global namespace, private,
      versioned, SSE-S3, Object Lock off; lifecycle: noncurrent versions deleted after 7
      days, delete markers cleaned, incomplete uploads aborted after 1 day
- [x] A **new** IAM user `graphguard-lakehouse` whose policy allows only
      `s3:ListBucket` on that bucket and `s3:GetObject/PutObject/DeleteObject` on its
      `lakehouse/` prefix — nothing else in the account — policy `graphguard-lakehouse-s3`,
      no console access, no other policy attached
- [x] Its keys are put into `.secrets/aws.env` (600, gitignored) **by Lubo**; they are
      never pasted into chat, code, git or the image — *deviation, Lubo's call*: the `!`
      prompt cannot run an editor, so Lubo pasted the key in chat and Claude wrote the
      file. It is in no code, git or image; rotating it is recommended (runbook)

*Least privilege, proven — not assumed*
- [x] **Given** the lakehouse keys, **when** they write under `lakehouse/`, **then** it
      works; **when** they write outside it, list another bucket, or touch IAM, **then**
      AWS answers AccessDenied — a test that expects the denial — 5/5 live tests pass
      against real AWS: lakehouse/ read-write-delete allowed; writing elsewhere, listing
      the bucket root, ListBuckets and IAM all denied

*The warehouse moves*
- [x] The catalog's warehouse points at `s3://<bucket>/lakehouse/`; the local path stays
      available for tests and as a fallback — *code done*: S3 automatically once
      `.secrets/aws.env` is filled, local until then; `GRAPHGUARD_LAKEHOUSE_WAREHOUSE`
      forces either. Every lakehouse test runs on local disk **and** a fake S3 (moto)
- [x] `just lakehouse-build` writes all tables to S3; Iceberg metadata, Parquet files
      and orphan cleanup all work against S3 (cleanup re-implemented for S3: list
      the prefix, delete what no snapshot references) — *proven on fake S3*; real bucket
      waits for AWS — real: 35 s (9 s locally; the difference is upload), peak 1.26 GB,
      124 objects / 0.83 GB on S3
- [x] **Given** the same CSV, **when** built to S3 and to local disk, **then** every
      table's contents are identical (row hashes) — all four tables identical
- [x] `just store-load` from the S3 gold gives the same 512,705 accounts and the same
      2,000 scores as today (max difference 0.0) — 512,705 accounts in 13.3 s, peak 0.57
      GB; 2,000 / 2,000 identical to the original baseline
- [x] Time travel works on S3: an older snapshot reads back the older rows
- [x] Local warehouse files deleted only **after** the S3 copy is verified; disk freed
      recorded — 1.2 GB freed after all checks; Redis then reloaded purely from S3

*DuckDB for SQL*
- [x] DuckDB added to the `lakehouse` extra (project-only), with `memory_limit` set
      (512 MB) and a spill directory — DuckDB **2.0.0** (settles the research's version
      conflict); Iceberg + httpfs extensions pre-fetched by bootstrap into `.tools/`
- [x] SQL reads the S3 Iceberg tables: row counts per layer match PyIceberg's — on local
      and fake S3 ✅; real S3 ✅ — all four tables in 1.7 s
- [x] **As-of parity**: DuckDB `ASOF JOIN` with a **strict `>`** gives the same account
      state at a transaction's time as the Polars path, on a sample — and a unit test
      for the exact-same-timestamp edge — on **all 4,061,486** silver rows, counts exact.
      Strict `>` on *time* alone is wrong on 381,911 rows (ties, FINDING-010); strict `>`
      on (time, source_row) matches training
- [x] A small `just sql` (or worksheet script) to run ad-hoc queries, read-only
- [x] DuckDB never names `sealed` (the guard enforces it) — and a test asserts no SQL
      view exposes it

*Measured*
- [x] Build time and peak RAM to S3 vs local; S3 request count and bytes per build;
      monthly cost estimate written down — storage ~$0.02/month for 0.83 GB at S3
      Standard list price; a build is ~125 PUTs (well under a cent); old versions
      expire after 7 days. Far under the $1/month target
- [x] DuckDB query peak RAM stays under its 512 MB cap — 4M-row history query in 8.9 s,
      process peak 1.13 GB including Python, Polars and the 4M-row result frame

*Everywhere*
- [x] `just check` green; CI green (S3 tests skipped in CI by an explicit flag, like
      Redis — CI has no AWS keys); committed; pushed; remotes match; LuBot untouched

**Definition of Done:** every box ticked; the scorer gives identical scores from the
S3-built store; no secret outside `.secrets/`; the denial test proves the keys can do
nothing beyond `lakehouse/`.

**Tasks**
1. Write the AWS checklist + the exact IAM policy JSON (`docs/runbooks/aws-setup.md`);
   **Lubo creates** the bucket, user and keys and fills `.secrets/aws.env`
2. Tests first: S3 round trip, the AccessDenied test, local-vs-S3 identity, S3 orphan
   cleanup, DuckDB ASOF strict-before edge
3. Make the catalog/warehouse S3-aware (PyArrow's S3 filesystem, credentials from
   `.secrets/`); S3 orphan cleanup
4. Build to S3; compare with the local build; time travel check
5. `store-load` from S3; 2,000-score comparison
6. Add DuckDB; SQL counts; ASOF parity on a real sample; `just sql`
7. Measure RAM, time, requests, cost; delete the local warehouse after verification
8. Docs (CLAUDE.md, runbook), `just check`, commit, push

**Estimate:** 5 story points, ~2 sessions. One external wait: Lubo's AWS step.

**Dependencies:** S5.6a ✅. **Lubo:** AWS bucket + IAM user + keys. S5.7 later adds a
separate **read-only** user for the scorer on a `models/` prefix of the same bucket.

**Out of scope:** Lakekeeper and credential vending (S5.6c), DuckDB writes / MERGE
(they need a REST catalog — S5.6c), the scorer reading from S3 (S5.7), backups of
the catalog database (S5.8c).

**Risks**
- *Keys leak* → only in `.secrets/` (600, gitignored); least-privilege policy limits
  the damage to one prefix; versioning lets deleted objects be recovered; the denial
  test proves the limit
- *Orphan cleanup deletes live files on S3* → it only deletes keys no remaining snapshot
  references, and the S3 version is tested before it runs on real data; bucket
  versioning is the safety net
- *Cost surprise* → requests and bytes measured per build; a build is ~40 files, far
  inside free tiers; estimate written down
- *DuckDB's Iceberg extension version quirks* (the research found conflicting version
  notes) → check the installed version; read-only use in this story
- *Build slower over the network* → measured; S3 is in the same region (3.7 ms)
- *Memory*: no new resident process; DuckDB is capped at 512 MB and runs only on demand

### S5.6c — Lakekeeper: a real REST catalog for the lakehouse ✅ done 2026-11-18

**In one line:** replace the Python-only table list with a small catalog server that
every engine talks to through the standard Iceberg REST API — the open-source
counterpart of Databricks' Unity Catalog.

**User story**
**As an** ML engineer, **I want** the lakehouse's tables served by an Iceberg REST
catalog (Lakekeeper), **so that** any engine — PyIceberg, Polars, DuckDB, later Spark —
finds and changes the same tables the same way, DuckDB can write (MERGE), and the
platform has the shape Databricks and Snowflake use.

**Why now:** today the catalog is PyIceberg's SQL catalog: rows in a Postgres database
that only PyIceberg reads. DuckDB can read tables only by being handed a metadata file
path, and cannot write at all without a REST catalog. Every later step — permissions
(S5.6d), Feast (S5.6e), Spark (Phase 10) — assumes one.

**Acceptance criteria**

*Before anything starts*
- [x] **Lubo approves starting the container** (box rule). Compose file and RAM cap
      shown to him first — approved 2026-11-18 ("let's do 6c as expanded"), with the
      limits stated: one container, 256 MB cap, 127.0.0.1 only, hardened

*The service*
- [x] Lakekeeper **v0.15.x**, pinned by image **digest**, in GraphGuard's compose project
      on `graphguard-net`, hard memory cap (start at 256 MB), `restart: unless-stopped`
- [x] Bound to **127.0.0.1 only** — not on the public interface, not reachable from
      other Docker networks or k3s pods — verified by trying from a Docker container and
      a pod, not assumed — public IP: refused; from a k3s pod: host bridge, public IP, name
      and the container's own IP (172.25.0.5:8181 and :9000) all blocked
- [x] Its state lives in its **own database and user** in GraphGuard's existing Postgres
      (like `lakehouse`), refused on `mlflow` and `lakehouse`; no new database server
- [x] Its encryption key and S3 credentials come from `.secrets/` (600, gitignored),
      never the compose file or git
- [x] Hardened like `lubot-prod-backend`: non-root, `read_only`, `cap_drop: ALL`,
      `no-new-privileges`, `pids_limit`, log rotation, healthcheck — verified with
      `docker inspect`: uid 65532, read-only root, cap_drop ALL, no-new-privileges, pids 128
- [x] **Measured**: idle RAM and RAM during a full `lakehouse-build`; kept only if it
      fits the budget (the research's estimate is 30-100 MB — measured, not trusted) —
      **23.5 MB idle, 30-32 MB during a full build** (cgroup, 1 s samples)

*The tables move to it — no data copied*
- [x] A Lakekeeper **warehouse** pointing at `s3://graphguard-lakehouse-0dcd18/lakehouse`
- [x] The existing tables are **registered** in Lakekeeper from their current metadata
      (no rewrite, no copy); snapshot ids and history unchanged — all five, metadata,
      current snapshot, history and location identical
- [x] `open_catalog()` returns the REST catalog; the SQL catalog stays readable as the
      **rollback** for this story, then is retired in writing
- [x] **Given** the same tables, **when** read through Lakekeeper, **then** row hashes equal
      the SQL catalog's
- [x] `just lakehouse-build`, `just store-load` and `just build-artifacts` work through
      Lakekeeper; the 2,000 scores stay identical (max difference 0.0) — build 31 s,
      reload 13 s, 2,000/2,000 identical; `build-artifacts`' read path (lineage + pinned
      silver scan) checked without retraining production
- [x] Time travel through Lakekeeper returns the older snapshot's rows

*DuckDB through the catalog*
- [x] DuckDB `ATTACH`es the Lakekeeper catalog instead of reading metadata file paths;
      `just sql` keeps working; `sealed` still never exposed — *refined*: ATTACH is used
      for writes only, because it exposes every namespace; `just sql` views are looked
      up through Lakekeeper. Full ATTACH for `just sql` after S5.6d denies `sealed`
- [x] **MERGE works**: a test performs `MERGE INTO` on a lakehouse table through
      DuckDB and reads back the change, with a new snapshot. (Real late-label updates
      are Phase 6's label-delay policy; this story proves the capability)
- [x] DuckDB-written files are readable by PyIceberg and Polars (format v2, field ids)

*Tests and guards*
- [x] Unit tests run against an **in-process REST catalog** where possible, or a
      Lakekeeper container started only for the test run; CI skips anything that needs
      a live Lakekeeper by an explicit flag with the reason printed — table logic stays
      unit-tested on throwaway SQL catalogs (catalog-agnostic); 4 live tests on the real
      Lakekeeper in throwaway namespaces; CI skips them with `GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1`
- [x] All three leakage guards pass; `test_set_touch_check` still blocks `sealed`
- [x] `just check` green; CI green; committed; pushed; remotes match; LuBot before/after
      unchanged — *correction 2026-11-18:* CI was **not** green. The first CI run
      that included the lakehouse tests (55d29ad) OOM-killed test workers: 4 xdist workers
      peaked at 2.25 GB against the job's 2 GB cap. My clean-clone check ran without the
      cap, so it could not see this, and I did not look at the real run. Fixed by
      `-n 2` (1.19 GB, measured under a 2 GB cgroup); the real CI run is the check now

**Definition of Done:** every box ticked; Lakekeeper measured and inside the budget;
scores unchanged; the rollback path written down; nothing secret in git.

**Tasks**
1. Write the compose service (digest-pinned, capped, hardened, 127.0.0.1) and the
   `.secrets/lakekeeper.env` layout; **show Lubo; get the OK to start it**
2. Create the `lakekeeper` database and user; bootstrap Lakekeeper (migrate), create
   the warehouse on our S3 bucket
3. Measure idle RAM; verify it is unreachable from a Docker container and a k3s pod
4. Tests first: REST round trip, register-without-copy, hash identity, time travel,
   DuckDB ATTACH + MERGE, sealed hidden
5. Register the existing tables; switch `open_catalog()`; keep the SQL catalog as rollback
6. Run build, store-load and the 2,000-score check through Lakekeeper; measure RAM
   during the build
7. DuckDB via ATTACH; MERGE test
8. Runbook (start, stop, rollback), CLAUDE.md, ADR 0002 (catalog choice: Lakekeeper vs
   Polaris vs SQL catalog, with the measured numbers), commit, push

**Estimate:** 5 story points, ~2 sessions.

**Dependencies:** S5.6b ✅ (S3). Lubo's OK to start one container. Possibly a second IAM
user later, if Lakekeeper should hold credentials separate from the build's (decided in
S5.6d).

**Out of scope:** authentication, role-based permissions, vended credentials, the
sealed namespace as a denied permission (all S5.6d); Feast (S5.6e); Spark (Phase 10).
Until S5.6d, Lakekeeper has no login — which is why it is bound to 127.0.0.1 only.

**Risks**
- *An unauthenticated catalog on a shared box* → 127.0.0.1 only, own Docker network,
  proven unreachable from containers and pods; auth arrives in S5.6d
- *RAM* → hard cap; measured idle and under load; if it does not fit, the SQL catalog
  stays and this is recorded as the decision
- *Register-in-place breaks history* → hash and snapshot-id comparison before switching;
  the SQL catalog is the rollback
- *DuckDB's write support has gaps* (positional deletes only; version notes in the
  research conflict) → proven by a test on a scratch table before any real table is
  written by DuckDB
- *Lakekeeper is young (0.x)* → digest-pinned; tables stay plain Iceberg on S3, so
  switching catalogs later (Polaris, Unity) needs only re-registration, no data move
- *Another long-running service to keep healthy* → healthcheck; `just k8s-check`-style
  check added for it; runbook

### S5.6d — Governance: logins, grants, and `sealed` as a denied permission *(approved 2026-11-18; part 1 done, part 2 waits for the AWS step)*

**In one line:** every job gets its own login (Dex), the catalog decides what each login
may do (OpenFGA), and each job gets S3 keys that open only the tables it is allowed —
so training **cannot** read the test set, and a test proves it.

**User story**
**As a** model-risk reviewer, **I want** each lakehouse job to run as its own identity
with only the permissions it needs — and the training identity unable to read the
`sealed` test window through the catalog **or** straight from S3 — **so that** "the test
set was never touched" is enforced by the platform and proven by a negative test, not
just promised by a lint guard.

**Why now:** since S5.6c Lakekeeper has no login: anything on the box can read or
change any table, including `sealed`. And every job holds the same S3 key, which opens
all of `lakehouse/` — so even with catalog permissions, a job could skip the catalog and
read sealed files directly. Real governance needs both locks: **who you are** (identity)
and **which files your key opens** (vended, scoped credentials). This is what Unity
Catalog does at Databricks.

**Facts checked before writing (2026-11-18)**
- Dex **v2.46** added the OAuth2 *client credentials* flow (opt-in) — the machine login
  our jobs need. Older Dex had no machine login.
- Lakekeeper's open-source authorizer is **OpenFGA** (a separate service with its own
  database). Its Cedar authorizer is Lakekeeper Plus (paid) — so not an option.
- Lakekeeper vends S3 credentials through **AWS STS**, downscoped to each table's
  location, read-only for readers. PyIceberg and DuckDB both accept vended credentials.

**Identities** (Dex machine clients; each secret only in `.secrets/`)

| Identity | Used by | bronze | silver | gold | sealed |
|---|---|---|---|---|---|
| `builder` | `just lakehouse-build` | write | write | write | write |
| `trainer` | `just build-artifacts` | — | read | read | **none** |
| `reader` | `just sql`, `just store-load` | read | read | read | **none** |
| `admin` | bootstrap and grants only | owner | owner | owner | owner |

(`evaluator`, the one-time read of `sealed` for the final test evaluation, is created
only when that evaluation happens — contract rule 4.)

**Acceptance criteria**

*Before anything starts*
- [x] **Lubo approves starting two containers** (box rule): Dex and OpenFGA, compose
      and caps shown first. Lakekeeper is restarted with auth on — approved 2026-11-18
      ("approve s5.6d do it senior")
- [ ] **Lubo does one AWS console step** (~10 min, runbook with copy-paste JSON): an
      IAM role `graphguard-lakekeeper-vending` (S3 `lakehouse/` only) and a new IAM
      user `graphguard-lakekeeper` that may only assume that role. Same account,
      nothing of `aws-job-streamer` touched. STS is free

*The services*
- [x] **Dex v2.46.x** and **OpenFGA** (latest stable), both pinned by digest, in
      compose project `graphguard` on `graphguard-net`, hardened like Lakekeeper
      (non-root, `read_only`, `cap_drop: ALL`, `no-new-privileges`, `pids_limit`, log
      rotation, healthcheck), hard caps (start: Dex 64 MB, OpenFGA 128 MB) — *refined:*
      OpenFGA **v1.14.2**, not the newest v1.22: it is the version Lakekeeper 0.15.1 is
      tested with. Dex needs a connector to start, so its password DB is on with **zero**
      users (never `mockCallback`, which lets anyone in); only client credentials allowed
- [x] Dex on **127.0.0.1:5556 only** (jobs on the host need it for tokens). OpenFGA has
      **no host port at all** — only Lakekeeper reaches it, on `graphguard-net`, with a
      preshared key. Both verified unreachable from the public IP and a k3s pod — public
      5556/8081/8181 blocked; from the scorer pod, both containers' own IPs (5556, 5558,
      8080, 8081), the host bridges and the public IP all blocked
- [x] State in **own databases and users** in GraphGuard's Postgres (`dex`, `openfga`),
      each refused on the others; no new database server — tried: each user reaches only
      its own of `dex`, `openfga`, `lakekeeper`, `mlflow`, `lakehouse`
- [x] **Measured:** idle RAM and RAM during a full build for all three services; kept
      only if they fit (story budget 50-150 MB for the two new ones) — **Dex 11 MB,
      OpenFGA 44-45 MB (56 MB together)**; Lakekeeper 31 → 39 idle, 42 MB peak with authz

*Who you are (authentication)*
- [x] Lakekeeper trusts Dex (`OPENID_PROVIDER_URI`, audience set); `AUTHZ_BACKEND`
      changes from `allowall` to `openfga` — fresh bootstrap with OpenFGA (switching keeps
      no grants); S5.6c database kept as `lakekeeper_s56c`; all 5 tables **re-registered**
      from an export, metadata and snapshot ids identical
- [x] **Given** no token, **when** any catalog call is made, **then** 401
- [x] **Given** a token signed by a different key, or expired, **then** 401 — forged
      RS256 token with the right issuer and audience, and a garbage token: both 401
- [x] `open_catalog()` takes an identity and logs in with client credentials; the
      secret never appears in logs, reprs or MLflow (tested) — REST without an identity
      is refused; `Identity` repr, Dex errors and the lineage dict are tested secret-free

*What you may do (authorization)*
- [x] Grants applied **from code** (one file listing the table above), idempotent —
      re-running changes nothing; the grants are the documentation — `governance.py`;
      8 grants on 4 targets, `lakekeeper-init` run twice with the same result
- [x] **Given** `trainer`, **when** it loads `sealed.transactions`, **then** 403; when it
      lists namespaces, `sealed` is not there — *stronger than 403:* "no such table", so
      the catalog does not even confirm it exists; same for `reader`
- [x] **Given** `trainer` or `reader`, **when** it writes any table, **then** 403 —
      append, create table and create namespace all `ForbiddenError`
- [x] **Given** `builder`, **then** build, re-build and orphan cleanup all succeed —
      full `just lakehouse-build` 36 s, peak 1.26 GB, snapshots kept and orphans cleaned

*Which files your key opens (vended credentials)*
- [ ] Warehouse switched to `sts-enabled: true` with the vending role; Lakekeeper holds
      the only long-lived S3 key (`graphguard-lakekeeper`, which can only assume the role)
- [ ] Jobs read and write S3 **only with vended credentials** — `.secrets/aws.env` is no
      longer read by any job
- [ ] **Given** `trainer`'s vended credentials for silver, **when** it fetches a `sealed`
      data file directly from S3 by path, **then** AccessDenied — the bypass is closed
- [ ] **Given** `reader`'s credentials, **when** it PUTs an object, **then** AccessDenied
- [ ] The old `graphguard-lakehouse` access key (the one pasted in chat) is **deleted in
      IAM** after everything passes — this also closes the key-rotation item

*Nothing else changes*
- [x] `just lakehouse-build` (builder), `just build-artifacts` read path (trainer),
      `just store-load` (reader) all work; **2,000/2,000 scores identical** — max
      difference 0.0; trainer reads the same 4,061,486 silver rows with the same hash as
      builder; store-load 512,705 accounts in 13.4 s
- [ ] `just sql` switches to full DuckDB `ATTACH` as `reader` — `sealed` is now hidden
      by permission, not by our view list (the S5.6c deferral, closed) — *waits for part
      2:* until vending, DuckDB's own S3 key could read bronze's files through ATTACH.
      Meanwhile `just sql` dropped its bronze view (FINDING-011) and a test checks that
      **no view returns a test-window row**
- [x] `test_set_touch_check` stays exactly as strict (defence in depth, not replaced) —
      one file added to its allowlist with a reason: `governance.py`, which names `sealed`
      only to deny it

*Tests and guards*
- [x] Config builders (Dex clients, grants plan, warehouse profile) unit-tested;
      every negative case above is a **live test**, skipped in CI only by the existing
      `GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1` with the reason printed — 26 unit tests
      (policy, secrets, Dex/compose agreement), 16 live governance tests
- [ ] A clean-clone run passes (as in S5.6c); `just check` green; CI green; committed;
      pushed; remotes match; LuBot before/after unchanged

*Found on the way (part 1)*
- **FINDING-011:** bronze is the raw CSV, test window included, and `just sql` exposed
  it. Locking `sealed` alone was a hollow lock. Trainer and reader now get only
  `describe` on bronze, `check_plan()` refuses more, and the SQL bronze view is gone
- **FINDING-012:** `.gitignore`'s `models/` had kept the XGBoost training code (9 files,
  19 tests) out of git since Phase 3 — the S5.6a `lakehouse/` trap again. Anchored to
  `/models/`, committed after a secret scan; `tests/test_repo_hygiene.py` now fails the
  build if any source file is gitignored or skipped by lint
- **CI memory:** the first CI run with the lakehouse tests was OOM-killed (4 xdist
  workers, 2.25 GB against a 2 GB cap) — fixed with `-n 2` before this story started

**Definition of Done:** every box ticked; training is denied `sealed` at the catalog
**and** at S3, shown by tests; one long-lived S3 key left, held only by Lakekeeper; the
old key deleted; RAM measured and inside budget; ADR 0003 written; nothing secret in git.

**Tasks**
1. Compose for Dex and OpenFGA (digest-pinned, capped, hardened); `.secrets/` layout;
   **show Lubo; get the OK to start them**
2. Runbook `docs/runbooks/aws-vending.md` with copy-paste JSON; **Lubo does the AWS step**
3. Tests first: 401s, 403s, S3 AccessDenied, grants idempotent, secrets never logged
4. Databases and users; start Dex and OpenFGA; measure; verify unreachable
5. Switch Lakekeeper to OIDC + OpenFGA (re-bootstrap if needed — see risks); apply grants
6. `open_catalog(identity)`; move build / train / store-load / sql to their identities
7. Turn on vending; remove `aws.env` from every job; run the S3 bypass tests
8. Full build, reload, 2,000-score check; measure RAM; delete the old IAM key
9. ADR 0003 (Dex + OpenFGA + STS vending vs alternatives, with numbers), runbook
   updates, CLAUDE.md, commit, push

**Estimate:** 8 story points, ~3 sessions (the biggest step of S5.6).

**Dependencies:** S5.6c ✅. Lubo: OK for two containers; one AWS console step; deleting
the old key at the end. (Feast moves to ADR 0004.)

**Out of scope:** human login to the Lakekeeper web UI (browser redirects through an
SSH tunnel — a later nice-to-have); row or column masking (neither authorizer does it);
the `evaluator` identity (final evaluation only); separate Unix users per job (S5.8 —
see risks); Redis and MLflow auth (S5.8).

**Risks**
- *Honest limit — one box, one Unix user:* every job runs as root, so a job could read
  another job's secret file. The platform enforces the boundary for every engine
  that goes through it, and the denial is real for any process holding only its own
  credentials. Process isolation (own Unix user or container per job) is written down
  as S5.8 work, not claimed here
- *Switching `allowall` → OpenFGA on a running catalog* may need a fresh bootstrap → the
  Lakekeeper DB is recreated and the tables **re-registered** (no data move, done once
  in S5.6c); snapshot ids compared before and after
- *Issuer mismatch:* Lakekeeper (in Docker) and jobs (on the host) reach Dex at
  different addresses, but the token issuer must be one string → issuer set to Dex's
  name on `graphguard-net`; the host only calls the token endpoint; tested
- *Vended credentials with Polars and our streaming writer* (PyArrow fs + `add_files`)
  may not pick them up → proven on a scratch table first; fallback: builder alone keeps
  a scoped static key, recorded in the ADR
- *Dex client credentials is new (v2.46)* → digest-pinned; tested end to end; Keycloak
  (heavier, Java) is the documented fallback
- *RAM* → hard caps; measured; if OpenFGA does not fit, the story stops and the choice
  is recorded
- *Locking ourselves out* → `admin` secret kept in `.secrets/`; runbook has the
  recovery path (back to `allowall` on 127.0.0.1, as S5.6c ran)

### S5.6e — Feast, lineage, worksheets *(short until its turn)*
Feast (library) over Iceberg → Redis, asserted equal to the Polars output (ADR 0004 on
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
