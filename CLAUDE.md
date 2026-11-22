# GraphGuard-AI

Real-time money laundering detection with a graph neural network, on the IBM AMLworld
dataset.

**Full build plan:** `PLAN.md`. Read it before starting a phase — this file is the rules,
that file is the work. **Read its "Plan revisions" section too**: the plan has been
changed three times (R-1, the GNN losing Phase 4; R-2, a Nov 2026 re-check against
the market, the research and the stack — see `docs/research/`; R-3, box security as
its own Phase 5b), and revisions
are recorded there with their cause rather than applied silently.

**The production model is XGBoost, not the GNN** (R-1). Serving, explainability and
monitoring all follow the tree. The GNN is kept as a documented negative result and as
the research arm.

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

**Never publish the box's weak spots.** The GitHub repo is public. Audit findings, open
ports, file permissions, exposed credentials, unpatched versions — for GraphGuard, LuBot
or the box — go only in `private/` (gitignored, 700). Public docs say *that* something is
being fixed, never *what is open* (Lubo, 2026-11-18, after a LuBot list was committed).

**GraphGuard's own everything.** Own containers, own Docker network, own volumes, own
ports, own Postgres and Redis (not LuBot's), own S3 bucket, own IAM user scoped to that
bucket only. Everything lives in `/srv/graphguard`.

**Hard memory caps on every container.** Not optional — swap on this box sits at ~99%
full.

**Ask before:** installing anything system-wide, or starting any container.
**Box-wide changes** (Docker, nginx, firewall, reboots) go to the LuBot session first (agreed
2026-11-19). When it reports its services re-bound, run `just edge-baseline`.

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
only. State in `/srv/graphguard/runner/` — gitignored, `700`/`600`, holds the runner
credential. Daemon capped at 1G; **each job container capped at 2G, verified in CI, not
assumed**. One job at a time, 45m timeout.

**CI supply chain (S5b.2).** Jobs run in our own image `graphguard/ci:1`
(`docker/ci.Dockerfile`, pinned Node 22 LTS + git/curl; `just ci-image`) on **a fresh
network per job**, with **no capabilities and no-new-privileges**. The first step of
every job is `scripts/ci/isolation-probe.sh` (`just ci-probe` locally): it fails the
build if the job can reach another container, has capabilities, or cannot reach PyPI.
Actions are pinned to **commit SHAs** (resolved from data.forgejo.org); a test fails on
any tag. **Secrets:** betterleaks (pinned + checksum in `bootstrap.sh`) in pre-commit
(`just secrets-staged`) and on the whole history in CI (`just secrets-history`;
accepted findings in `.betterleaks-baseline.json` or an inline `betterleaks:allow` with
its reason). **Dependencies:** uv `exclude-newer = "P14D"` (nothing younger than 14
days; exemptions per package with a reason), and `just deps-check` (locks current +
OSV-Scanner) in CI. The serving image is rebuilt from the current lock on a
digest-pinned base with Debian security updates (`serving:0.1.3`).

`forgejo-runner.service` (LuBot) and `sentinel-runner.service` are **not ours** — never
touch them.

**Forgejo task IDs are global across the instance.** A task number near ours may belong
to LuBot. Confirm ownership in the runner log (`task N repo is lubo/GraphGuard-AI`)
before inspecting anything.

The old per-job `apt-get` (~7 s of every job) is gone: git and curl are in the job image.

---

## Local services

`just mlflow-up` / `mlflow-down` / `mlflow-status` / `mlflow-logs`.

| | |
|---|---|
| MLflow UI | `127.0.0.1:5010` (localhost only - tunnel over ssh); **MLflow 3.17.2, login required** (S5b.7) |
| MLflow Postgres | `127.0.0.1:5434` |
| Compose project | `graphguard` |
| Network | `graphguard-net` |
| Volumes | `graphguard-mlflow-db-data`, `graphguard-mlflow-artifacts` |
| Memory caps | MLflow 640M (1 worker, job system off: 354 MiB), Postgres 256M, Redis 448M (S6.3), Kafka 768M (S6.4) — measured |

Ports 5000, 5432 and 5433 were already taken on this host, which is why these
are 5010 and 5434. **Credentials live in `.secrets/`** - gitignored, `chmod 600`,
generated locally and never committed. `.secrets/kaggle.json` holds the Kaggle
token, `.secrets/mlflow.env` the Postgres **superuser** password (admin only — no
service uses it), `.secrets/mlflow-app.env` + `mlflow-pgpass` MLflow's own role
(`mlflow_app`, read through `PGPASSFILE`, never in a command line),
`.secrets/lakehouse.env` the stale SQL catalog's role, `.secrets/redis.env` the Redis
users' passwords.

**Data services (S5b.1, runbook `docs/runbooks/data-services.md`).** Redis: users
`scorer` / `loader` / `stream` (S6.3) / `tests` with only the commands each uses, nobody
with scripting, default user off, rules
in `src/graphguard/serving/redis_acl.py` (`just redis-secrets`); the scorer's URL is
the Kubernetes Secret `graphguard-redis` (`just k8s-redis-secret`) — never put it in
the manifest. A Redis restart empties the store: `just store-load`. Postgres: each
service its own role and database, SCRAM only, everything else rejected, superuser
only on the local socket — `src/graphguard/ops/pg_access.py` (`just pg-access`). Admin
`psql` now needs `PGPASSWORD=$POSTGRES_PASSWORD` even inside the container.
**Every compose service** must pass `tests/test_compose_hardening.py` (cap, no
capabilities, no-new-privileges, pids limit, read-only root, non-root, digest, log
rotation, private ports) — a new service that skips it fails the build.

MLflow runs 2 web workers: with the default 4 it idled at 730 MiB of private memory;
with 2 it idles at ~426 MiB and peaks at ~486 MiB (2026-11-18).

---

## The lakehouse (S5.6a, 2026-11-18)

Iceberg v2 tables served by **Lakekeeper** (S5.6c), an Iceberg REST catalog —
container `graphguard-lakekeeper`, **127.0.0.1:8181 only**, ~40 MB, state in its own
`lakekeeper` database in the MLflow Postgres. Runbook `docs/runbooks/lakekeeper.md`,
decision ADR 0002.

**Logins and grants (S5.6d):** every catalog call carries a **Dex** token
(`graphguard-dex`, 127.0.0.1:5556, ~11 MB) and **OpenFGA** holds the grants
(`graphguard-openfga`, no host port, ~45 MB). One identity per job: `builder`
(writes all), `trainer` and `reader` (read silver + gold; bronze metadata only, because
bronze holds the test window — FINDING-011; `sealed` invisible), `admin` (setup).
The policy is `src/graphguard/lakehouse/governance.py` — change access only there,
then `just lakekeeper-init`. `open_catalog("<identity>")`: the REST catalog has no
anonymous access. Since S5b.5 each job runs as its own user holding only its own identity. **Jobs hold no S3 key** (part 2): Lakekeeper vends each a 1-hour STS
key per table, read-only unless it may write, none for bronze to trainer/reader. The
only long-lived key is Lakekeeper's (`.secrets/lakekeeper-aws.env`, user
`graphguard-lakekeeper`, which can only assume role `graphguard-lakekeeper-vending`).
Storage helpers take a **table's** `io.properties`, never the catalog's. Never give a
job a static key again: it silently undoes the S3 lock. Decision: ADR 0003; AWS side:
`docs/runbooks/aws-vending.md`. The S5.6a SQL catalog (`lakehouse`
database) is a stale rollback: `GRAPHGUARD_CATALOG=sql`. Research and roadmap:
`docs/research/Open source lakehouse on one box.md`; later steps S5.6b-e (S3 + DuckDB,
Lakekeeper REST catalog, governance, Feast).

| Table | Holds |
|---|---|
| `bronze.transactions_raw` | the CSV, typed, plus `source_row` (the transaction key) |
| `silver.transactions` | train + validation, tail removed, partitioned by day |
| `sealed.transactions` | the test window — named only in `lakehouse/catalog.py` and `tables.py`; `test_set_touch_check` fails anywhere else |
| `gold.account_features_asof` | account states as of `train_end`, by the serving definition |
| `gold.labels` | labels + `label_known_at` (null until Phase 6's label-delay policy) |
| `gold.account_recent_sends` | each send in the 24 h before `train_end` — the stream's seed for the 24 h count (S6.2) |
| `gold.account_edges` | every (from, to) pair seen before `train_end` — the stream's seed for distinct counts (S6.3) |

```
just lakehouse-build   # CSV -> Iceberg on S3, ~35s, peak ~1.3GB, keeps last 5 snapshots, cleans orphans
just build-artifacts   # trains from silver, logs snapshot ids + split sha + git sha to MLflow
just store-load        # Redis from gold on S3, ~13s, peak ~0.6GB, in place, no retraining
```

**Storage (S5.6b, live 2026-11-18):** GraphGuard's own S3 bucket
`graphguard-lakehouse-0dcd18` (us-east-1, same AWS account, new bucket), prefix
`lakehouse/`, policy `graphguard-lakehouse-s3` reaching nothing else — live tests
prove the denials. Since S5.6d it is used through the vending role; the S5.6b user
`graphguard-lakehouse` and its `.secrets/aws.env` key are retired. 0.83 GB, ~$0.02/month;
old versions expire after 7 days. The local warehouse is gone; force local with
`GRAPHGUARD_LAKEHOUSE_WAREHOUSE=file:///...` if S3 is ever unreachable. Every lakehouse
test also runs on a fake S3 (moto). Setup steps: `docs/runbooks/aws-setup.md`.

**SQL:** `just sql "select ..."` — DuckDB 2.0 as `reader` with the catalog ATTACHed as
`lk` (vended keys), plus views `silver_transactions`, `gold_account_features_asof`,
`gold_labels`. `sealed` does not exist for reader and bronze is Forbidden — by
permission, not by a list. Capped at 512MB. History in SQL must order by **(timestamp, source_row)**, never time
alone: 9.4% of transactions tie on the minute (FINDING-010). In Polars every history sort
says `maintain_order=True`, and parity tests compare with `==`, never approx (FINDING-015).

**Lakekeeper:** `just lakekeeper-status | lakekeeper-up | lakekeeper-down | lakekeeper-init
| lakekeeper-export | identity-secrets` (status/up/down cover Dex and OpenFGA too).
DuckDB ATTACH (`sql.attach_catalog`) logs in as the catalog's identity, so its writes
(MERGE) need `builder`.

**Feature store, lineage, worksheets (S5.6e):** we keep **our own store** (Polars →
gold → `just store-load` → Redis). Feast 0.68 was measured in its own uv project
`featurestore/` — identical online values, but 3.96 GB RAM to fill (ours 0.58 GB) and it
**cannot build the training features** without leakage on same-minute ties. ADR 0004.
`just feast-trial | feast-parity | feast-test` re-run that evaluation (capped; never the
live Redis; never add Feast to the main lock — it downgrades the scorer's Redis client).
**Lineage:** build, store-load and build-artifacts emit OpenLineage events to
`lakehouse/lineage/events.jsonl` (training's also go to its MLflow run); `just lineage`.
**Worksheet:** `just notebook` — marimo as `reader`, 127.0.0.1:2718 with a token, 1 GB cap.
**Supply chain:** new dependencies are pinned to releases ≥ 2 weeks old;
`[tool.uv] constraint-dependencies` in pyproject records each cap and why.

**Gitignore trap (FINDING-012):** a bare folder name in `.gitignore` or ruff's
excludes matches at any depth. `lakehouse/` and `models/` both hid real source code.
Anchor root folders (`/models/`); `tests/test_repo_hygiene.py` fails the build if any
`.py` under src/, tests/ or scripts/ is gitignored or skipped by lint.

**Do not run lakehouse jobs while MLflow is busy with heavy training** — Ray at peak +
busy MLflow + a ~1.1GB job would reach the 4GB budget. Aggregations read silver **in
source order** (`scan_in_source_order`); FINDING-009 explains why and what parity
across engines can and cannot mean.

---

## MLflow 3 and its login (S5b.7, 2026-11-19)

Server and client are both **3.17.2** — `tests/test_mlflow_version.py` fails if the image,
`docker/mlflow-requirements.txt` (hash-locked) and `uv.lock` disagree. Upgrades go through
`just mlflow-rehearse` first (runbook `docs/runbooks/mlflow.md`). **Login required:**
`admin` (Lubo: `just mlflow-admin-password` in his own terminal), `trainer`
(build-artifacts, via systemd), `research` (root scripts, tests); code logs in through
`graphguard.tracking.use_login()`. Grants in `src/graphguard/ops/mlflow_auth.py`.
Backend URIs must say `postgresql+psycopg2://`. **Never run a bare `uv sync`** — it strips
the extras; use `./scripts/bootstrap.sh` or `uv sync --extra dev --extra gnn --extra
lakehouse --extra notebooks --locked`.

## Secrets (S5b.6, 2026-11-19)

Every `.secrets/` file is registered in `src/graphguard/ops/secrets_registry.py`;
**`just secrets-status`** (with the other health checks) fails on overdue, untracked,
missing or wrongly permissioned secrets — a new secret file needs a registry entry.
**Never ask Lubo to paste a key into chat:** he types it in his own terminal with
`just secret-set <file>`. Rotate on-box secrets with `just rotate-pg <role>`,
`rotate-identities`, `rotate-openfga`, `rotate-redis` (each proves the holder works and
rolls back on failure), then `just backup`. Runbook `docs/runbooks/secrets.md`.
Cloud-console keys are kept by Lubo's decision (accepted risk, private record).

## One user per job (S5b.5, 2026-11-19)

`just lakehouse-build | build-artifacts | store-load | sql | notebook` run as
`gg-builder` / `gg-trainer` / `gg-reader` in sandboxed systemd units
(`src/graphguard/ops/jobs.py`), each handed only its own credential via
`$CREDENTIALS_DIRECTORY` — `graphguard.config.secrets_dir()` is the one place code finds
secrets. Jobs cannot see `.secrets/`, `private/`, Docker, k3s; trainer and reader cannot
see the raw CSVs. A job that needs a new path gets **that path** in its profile, never
the repo. Live proof: `tests/ops/test_jobs_live.py`. Admin setup and tests stay root.
Runbook `docs/runbooks/job-users.md`.

## The front door (S5b.4, 2026-11-19)

k3s's ports are dropped on `eth0` (v4 + v6) in our own chain `GRAPHGUARD-EDGE`, one jump
first in `INPUT`, matching the public interface only — `src/graphguard/ops/edge.py`,
`graphguard-edge.service` (boot). Daily read-only watchdog `graphguard-edge-check.timer`
(06:00 UTC): cloud firewall via `.secrets/hetzner-readonly.env` (Read-only token), public
listeners vs `private/edge/baseline.json`, guard present. **`just edge-status`** with the
other health checks. Remove: `just edge-remove`. A new public listener from another
project is reported to its session, never changed by us; accept on purpose with
`just edge-baseline`. Runbook `docs/runbooks/edge.md`.

## Kafka (S6.4, 2026-11-21)

`graphguard-kafka`: Apache Kafka 4.4.0, one KRaft node, `127.0.0.1:9092` (host) and
`10.42.0.1:9094` (pods), **SCRAM login required**, deny by default; heap 384m, cap 768m
(peak 422 MiB at 1M messages). Logins / topics / ACLs only in
`src/graphguard/stream/kafka_admin.py` → `just kafka-setup` (removes anything else).
`just kafka-status | kafka-up | kafka-down | rotate-kafka`; first start: `kafka-init`,
`kafka-up`, `kafka-bootstrap`, `kafka-setup`. Topics keep **arrival-time** retention (the
replay's 2022 event times live in the message body). **Tests never write to or empty the stream's topics**: live tests use the `probe.*` mirror (the S6.11 soak caught them deleting live records). Keep the JVM hardening flag in
`KAFKA_OPTS` (test-enforced; why and when to drop it: `private/security/`). ADR 0006.

## Shadow scoring (S6.10, 2026-11-21)

`graphguard-shadow` (k3s, `k8s/shadow.yaml`): the challenger scores the champion's own
feature vectors from `decisions` → `decisions_shadow`; decides nothing. `just
k8s-shadow-deploy | shadow-report`; challenger: `python -m graphguard.stream.shadow train |
publish`, pin its version + hash in `k8s/shadow.yaml`. Labels for comparison are biased
toward the champion (FINDING-017) — the report says so.

## Late labels (S6.9, 2026-11-21)

`python -m graphguard.stream.labels measure | publish [--as-of T]`: labels arrive through
investigation (100 alerts/day, 1-14 days) or external report (30-60 days); no label =
unknown. Topic `labels` (login `labeler`), consumer table `labels`,
`gold.labels.label_known_at`. **Anything that learns uses `labels.known_as_of(t)` only.**
`just lakehouse-build` resets `label_known_at` to null — re-run `labels publish` after.

## Chaos and rules (S6.7, S6.8, 2026-11-21)

`python -m graphguard.stream.chaos [--only NAME]` — 6 scenarios (speeds, faults, pod kill,
crash between Redis and Postgres, broker restart), each must be exact. Rules:
`src/graphguard/stream/rules.py`, thresholds from TRAINING only → generated
`rule_thresholds.py` (`python -m graphguard.stream.rules` also writes
`docs/analysis/s6.8-rules.json`); queue order + alert line in ADR 0007. On AMLworld rules are
a baseline/safety net, not an alert source (FINDING-016). A consumer code change = a new image
tag (never rebuild a tag the scorer runs) + roll both.

## The consumer (S6.6, 2026-11-21)

`graphguard-consumer` (k3s Deployment, `k8s/consumer.yaml`, image 0.1.12): Kafka →
live features → model in process → Postgres `stream` (decisions + offset + outbox in one
transaction), one writer (advisory lock, `Recreate`). `just consumer-logs |
k8s-consumer-deploy | k8s-stream-secret | stream-reset`. End-to-end proof:
`python -m graphguard.stream.e2e --n 20000 [--faults chaos] --consumer pod` — every
decision once, scores == the offline evaluation. Postgres also listens on `10.42.0.1:5434`
(pg_hba: pods reach only `stream`). **CI:** `just ci-wait [sha]` waits for green with a
read-only Forgejo token — check it after every push instead of asking Lubo.

## The replayer (S6.5, 2026-11-21)

`just replay --run <name> --speed 600|1|max [--faults chaos] [--limit N]` — job `replay`
(gg-reader): validation window only (asserted), training's order, JSON messages
(`stream/messages.py`, **no label**), seeded faults logged to `stream-runs/<run>/`,
checkpoint resume. Empty the topic between runs with the admin login (delete records).

## Live features for the stream (S6.3, 2026-11-21)

`src/graphguard/stream/updater.py`: each event returns both accounts' state **before** it,
then applies it — one writer, the batch computed in Python (`plan()`, pure), written in
**one MULTI/EXEC**. No Lua (S5b.1 stands; ADR 0005). Redis keys `gg:acct:*` (+ watermark
`wm`), `gg:edge:*` (seen pairs), `gg:win:*` (24 h send times), `gg:ev:*` (pending
before-states, 6 h). **`just store-load` resets the stream to the snapshot** (seed from
`gold.account_recent_sends` + `gold.account_edges`). Proof: the whole validation window
(1,015,300 events) equals training on every feature (`tests/stream/test_full_replay_real.py`,
slow; `python -m graphguard.stream.proof --redis URL` for a throwaway Redis — never the live
one). Redis: 320mb data / 448m cap, measured.

## The scorer alert (S6.1, 2026-11-21)

`graphguard-alert.timer` every 5 min: `k8s_health.collect_problems()` + the scorer's
`/health` asked from inside its pod. **Email only on state change** (2 checks in a row must
agree; reminder once a day while broken; failed mail retried), via AWS SES — IAM user
`graphguard-alerts` may send only from Lubo's verified address to the same address (live
test `tests/ops/test_alert_live.py`). Key `.secrets/alerts-aws.env`, addresses
`.secrets/alerts-mail.env` (never in the repo). `just alert-status | alert-drill |
alert-pause 2h | alert-resume`; **`just health`** runs every health check (backups, edge,
secrets, alert, k3s). Code `src/graphguard/ops/alert.py` (pure `step`); runbook
`docs/runbooks/scorer-down.md`. Planned scorer work: `just alert-pause` first.

## Backups (S5b.3, 2026-11-19)

Nightly 03:20 UTC `graphguard-backup.timer`, Sundays 05:10 UTC
`graphguard-restore-check.timer` (units in `systemd/`, `just backup-install`). restic
0.19.1 (bootstrap) → bucket `graphguard-backups-0dcd18`, **Object Lock Governance 30
days**, key `.secrets/backup-aws.env` (user `graphguard-backup`, cannot delete versions or
touch the lock — `tests/ops/test_backup_live.py`), repository password
`.secrets/backup-restic-password` **and in Lubo's password manager**. Code
`src/graphguard/ops/backup.py`; the DB list comes from `pg_access.SERVICES`, so a new
service DB is backed up automatically. `just backup | restore-check | backup-status`
(exit 1 when stale or failed — run it with the other health checks). Disaster rebuild:
`docs/runbooks/backups.md`. Never switch retention to count-based (`--keep-last`): an
attacker can push real snapshots out by planting fakes.

---

## k3s

Installed 2026-08-27 for Phase 5 serving. Single node, named `graphguard`.

```
k3s kubectl get nodes          # node status
systemctl status k3s           # the service
/usr/local/bin/k3s-uninstall.sh  # full rollback if ever needed
```

**Installed with `--disable traefik --disable servicelb --disable metrics-server`.**
That is not tidiness: k3s's built-in load balancer binds host ports 80 and 443, and
nginx is already serving lubot.ai, staging.lubot.ai and git.lubot.ai on those ports.
Leaving servicelb enabled would have put k3s in a fight with production nginx.

**Admin kubeconfig is `600`** (`--write-kubeconfig-mode 600`, was 644 until S5b.0). The
flag is on the unit's command line, which beats `/etc/rancher/k3s/config.yaml` — any
reinstall or upgrade through the install script must pass it again.

**It needed a box-wide kernel change.** `fs.inotify.max_user_instances` was at the
default 128 with 134 instances already in use by ~118 Docker containers, so k3s could
not allocate a watcher and failed with "too many open files". Raised to 1024 in
`/etc/sysctl.d/99-graphguard-inotify.conf`. Additive only, no restarts required, and
audited against LuBot beforehand: LuBot neither reads nor sets that sysctl, ships no
conflicting sysctl.d file, and had no inotify errors in its logs. The `99-` prefix makes
it load after the `10-*` platform defaults.

**Verified not to have disturbed Docker.** All 18 named LuBot services present after
install, 13 networks unchanged, Docker's 94 iptables rules intact, lubot.ai and
git.lubot.ai still answering. iptables grew from 188 to 320 rules, all of it k3s's own
`KUBE-*` chains.

**The scorer's model (S5.7, image 0.1.12 since S6.11).** Downloaded from S3 at startup by the version
and SHA-256 pinned in `k8s/rayservice.yaml`; any mismatch → it refuses to start (the old
one keeps serving). New model: `just model-publish`, change those two lines, apply.
Runbook `docs/runbooks/models.md`. The image carries no model.

**The scorer's answers (S5.5).** 200 with a score and `cold_policy`
(`warm` / `scored: sender new` / `scored: receiver new` / `review: both accounts new` —
FINDING-014); **422** for missing or malformed input; **503** when Redis is down
("unavailable") or has no store marker ("not loaded") — `/health` too. After any Redis
restart the scorer stays 503 until `just store-load` (which writes the marker last).

**The scorer pod is restricted (S5b.1).** Namespace `graphguard` enforces Pod Security
`restricted` (`k8s/namespace.yaml`): non-root uid 10001, read-only root with `/tmp` as
an `emptyDir`, no capabilities, seccomp, no service-account token. Egress is denied
except DNS, Redis and Ray-internal (`k8s/networkpolicy.yaml`; note Redis is allowed at
its post-DNAT address `172.25.0.0/16:6379` — Docker rewrites `10.42.0.1:6380` before
the policy is checked). `just k8s-check` fails if an ingress or egress policy is missing.

**Do not run `k3s-killall.sh` casually.** It rewrites the whole iptables table via
`iptables-restore`, and Docker's rules live there. Stop the service and clear stale
processes surgically instead.

---

## How we work

**One step at a time.** Do a step, stop, say what was done and what is next. Do not run
ahead through a whole phase.

**Every phase starts with agile stories (R-2).** Before reading or writing any code for
a phase: restate the main goal, write the phase's stories in `docs/stories/phase-N.md`
(As a / I want / so that, checkable acceptance criteria, linked to the phase's "Done
means"), and **get Lubo's approval**. Only then read the code and start the RECR loop.
The acceptance criteria become the first tests. Big choices get a one-page ADR in
`docs/adr/`.

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
- xdist — `-n 2 --dist=loadgroup` (was 4; 4 workers peaked at 2.25 GB, over the CI job's
  2 GB cap — 2026-11-18), **identical flags in prek and CI** (drift is a known
  LuBot failure mode)
- CI installs with **uv from the committed lockfile** — same lockfile as the container
- Unit and integration as separate stages
- Startup check as its own stage (`just startup-check`, added in S5.7): the serving app
  imports, **loads the model through the S3 path** (fake S3 in CI — no cloud key there),
  verifies it against the pinned hash, and answers one scoring request

**ML-specific, which LuBot does not need:**
- **Determinism** — same seed + same data = byte-identical model
- **Data contracts** — Pandera schemas asserted as tests, not just applied at runtime
- **Behaviour fixtures** — hand-built subgraphs (clean fan-out, clean cycle, obviously
  innocent account) the model must score correctly
- **Metamorphic tests** — ×10 every amount and the ranking should hold; rename an account
  and nothing changes
- **Train/serve parity** — same transaction through batch and online paths, asserted
- **Latency budget in CI** — the build fails if feature assembly + inference (production-sized
  model, in process) passes 10 ms at p99, a fixed share of the 50 ms budget
  (`tests/serving/test_latency_budget.py`, added in S5.4 — before that the assertion was
  promised here but did not exist). The end-to-end p99 is measured on k3s, open loop, by
  `python -m graphguard.serving.perf_k8s run` (FINDING-013); CI cannot run k3s
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
| 4 | The graph model — GraphSAGE done; Multi-PNA rematch + minority F1 (R-2) | **comparison done** (2026-08-20), rematch open |
| 5 | Serving — online store, Ray Serve on k3s, p99 < 50ms | **done** (2026-11-19) — S5.1-S5.7; p99 13-15 ms at stream rates, 150 tx/s HTTP capacity (FINDING-013) |
| 5b | Box security — GraphGuard hardened, host firewall, per-job users (R-3) | **done** (2026-11-19) — S5b.0-S5b.7; the full host firewall (S5b.4b) cancelled with the LuBot session: binding + watchdog instead |
| 6 | The stream — Kafka 4 (was Redpanda), rules layer, label delay | **done** (2026-11-22) — S6.1-S6.11: alert, exact live features (FINDING-015, ADR 0005), Kafka (ADR 0006), replayer, consumer on k3s, chaos 6/6, rules (FINDING-016, ADR 0007), late labels (FINDING-017), shadow; overnight soak exact on 1,015,300 transactions |
| 7 | The interface — queue, ring, slider, measured investigator agent | not started |
| 8 | Monitoring, retraining DAG, champion/challenger, model-risk card | not started |
| 8b | Make it findable — demo, video, post | not started |
| 9 | Second dataset — TransXion robustness check (R-2) | not started |
| 10 | Scale to 180M, optional and honest | not started |

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

Still open in Phase 4: GNNExplainer, minority-class F1 in `evaluate()`, and the
Multi-PNA rematch (R-2). SageMaker is cut by R-2; S3 moves to Phase 5.

**Phase 5 gate — met 2026-11-19.** Stories in `docs/stories/phase-5.md`. A live scorer on
k3s (Ray Serve, restricted pod), its model pulled from S3 at startup and verified against a
hash pinned in git (S5.7); p99 measured open loop from inside the cluster — 13-15 ms at the
stream's rates, 22 ms at 150 tx/s; at 200 tx/s the HTTP path saturates, and ~94% of its
CPU is Ray Serve, not the model (FINDING-013 — so Phase 6's consumer scores in process);
new accounts measured and given a rule (both new → review, FINDING-014); a broken or empty
store answers 503, never a cold score (S5.5); the lakehouse, logins, grants and vended keys
(S5.6a-e). Phase 5b hardened the box in between (`docs/stories/phase-5b.md`). Next:
**Phase 6 — the stream**, starting with the scorer alert (PLAN.md).

**Phase 6 gate — met 2026-11-22.** Stories in `docs/stories/phase-6.md`. The whole
validation window (1,015,300 transactions) replayed overnight at 6x through Kafka 4 → the
consumer on k3s (live features in Redis, model in process) → Postgres: every transaction
decided exactly once, **0 score and 0 rules mismatches** with the offline evaluation, 0 dead
letters, the shadow scored all 1,015,300, lag back to 0 (max 385), memory flat (consumer 324
MiB, shadow 194, Redis 300, Kafka 483, Postgres 239). Decision latency p99 6.3 s — the reorder
buffer that absorbs late events, not scoring. Run 1 failed and found two real bugs (tests
writing into the live stream; the shadow skipping on a lost position) — both fixed first.
Next: **Phase 7 — the interface**.

**Scoring rules from here on.** Every model goes through
`graphguard.evaluation.evaluate.evaluate()` - one entry point, so no two models
are measured differently. Everything is scored on **validation**. The test split
stays sealed until the final evaluation (contract rule 4), and
`test_set_touch_check` counts the call sites.

Update this table when a phase gate actually passes — not when the code merely runs.
