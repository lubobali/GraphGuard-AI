# Phase 5b — Box security: stories

**Status:** phase added by R-3 (Lubo, 2026-11-18). Starts after S5.6e, before S5.4.
Stories are expanded one at a time, just before work starts, and each is approved by
Lubo first. S5b.1-4 were S5.8a-d in Phase 5; S5b.5-6 are new.

## Main goal

The box was hacked once. Lock GraphGuard down to at least `lubot-prod-backend`'s
standard, put a second wall behind the Hetzner firewall for the whole box, and hand
LuBot's own findings to the LuBot session — without ever taking lubot.ai, staging,
git.lubot.ai or lubobali.com down.

**Epic / Definition of Done** (PLAN.md, Phase 5b): every item done and guarded by a test
or check that fails on regression, or explicitly handed over / accepted in writing;
every site up throughout; a one-page "how this box is protected" document.

**Rules for every story:** GraphGuard's session never touches `lubot-*`, `forgejo`,
`sentinel-*` or `aws-job-streamer`. Anything box-wide (firewall, k3s restart) is
planned with the LuBot session and applied once, with a rollback. Never
`k3s-killall.sh`.

---

## S5b.0 — Urgent fixes and one coordinated maintenance window ✅ done 2026-11-18

**As the** owner of the box, **I want** the most urgent findings of the 2026-11-18 audit
closed first — without downtime where possible, and in one announced maintenance window
where a restart is unavoidable — **so that** every app is back within minutes, verified
by a before/after check, with a rollback for every step.

Three owners: Lubo (approvals, the window), the LuBot session (box-wide and LuBot
steps), the GraphGuard session (GraphGuard steps, the check script). Done the same day (no paid users, so no night window needed): one reboot, every app
verified back by a before/after check, GraphGuard's 2,000 scores identical. The full story —
steps, criteria, rollbacks, record — is private (`private/security/`), because it names what is
open until it is fixed (CLAUDE.md rule).

---

## The backlog (moved from Phase 5's S5.8 epic)

**Why:** the box was hacked once. Read-only audits (2026-11-18) found it well guarded
from the internet but with work to do inside, for GraphGuard and for the box
(details: private audit, not in this public repo). GraphGuard must never be the weak door into LuBot or anything else.

**Split by risk, lowest first.** Each sub-story is expanded fully just before it starts.

| | Sub-story | Touches | Risk |
|---|---|---|---|
| **S5b.1** | Harden GraphGuard's own containers and pod | only GraphGuard | low |
| S5b.2 | Supply chain: CI runner, pinned actions, secret scanning | only GraphGuard | low |
| S5b.3 | Backups: MLflow off the box, with a tested restore | GraphGuard + a new B2 bucket | low, needs Lubo |
| S5b.4 | k3s control plane off the public interface; second wall for the box | box-wide | **high**, with the LuBot session |
| S5b.5 | One Unix user (or container) per job | GraphGuard | medium |
| S5b.6 | Keys and secrets: rotation, the retired AWS key | GraphGuard + AWS | low, needs Lubo |
| S5b.7 | MLflow server 2 → 3 (one major, matched client), after S5b.3's backups | GraphGuard | medium |

Facts already established: Hetzner firewall = TCP 80/443 inbound only (Lubo's console,
2026-11-18). Ray dashboard locked by NetworkPolicy (S5.3). Scorer runs as uid 10001.

---

### S5b.1 — Harden GraphGuard's own runtime: Redis, Postgres, MLflow, the scorer pod ✅ done 2026-11-18

**As the** owner of a box that was hacked once, **I want** GraphGuard's data services and
scorer pod patched, protected by least-privilege users, and locked down to the standard
Dex, OpenFGA and Lakekeeper already meet, **so that** an attacker who lands anywhere on
the box can neither use GraphGuard's data nor use a GraphGuard service as a step further.

What it delivered, each part proven by a test that fails if it regresses:
- **A backup first**: every GraphGuard database dumped and restored once into a throwaway
  container, row counts compared, before anything restarted
- **Redis**: current patch release; one user per client with only the commands it uses
  (`src/graphguard/serving/redis_acl.py`), no anonymous access, no scripting or admin for
  anyone; the scorer's credentials from a Kubernetes Secret
- **Postgres**: current patch release; each service its own role and only its own
  database, SCRAM only, everything else rejected (`src/graphguard/ops/pg_access.py`);
  MLflow on its own role instead of the superuser, credentials read from a protected file
  and rotated
- **Every container** to one standard, enforced for any future service by
  `tests/test_compose_hardening.py`
- **The scorer pod**: Pod Security `restricted` enforced on the namespace, read-only and
  non-root, no API token, outbound traffic denied except DNS, Redis and Ray
- **Memory**: caps re-sized from measured peaks to fit the 4 GB budget (MLflow on 2
  workers instead of 4)

Verified: 2,000/2,000 scores identical after every step, p99 still far inside 50 ms, 465
tests. Runbook: `docs/runbooks/data-services.md`. The detailed record stays private.

*Noted on the way (S5.6e, 2026-11-18), for S5b.1:*
- MLflow's database credential handling must be tightened (details: private audit, not in this public repo)
- MLflow could never store an artifact: its volume was root-owned while the server
  runs as uid 10001. Fixed in place (`chown`) and in `docker/mlflow.Dockerfile`; the
  image is rebuilt with the rest of S5b.1
- MLflow **client 3.15 vs server 2.19**: some client calls hit endpoints the server
  lacks (e.g. listing artifacts). Pin the client to the server's major, or upgrade the
  server, in one step with a tested restore (S5b.3)

### S5b.2 — Supply chain and CI: isolated jobs, pinned code, scanned commits ✅ done 2026-11-18

**As the** owner of a box that runs CI for several projects, **I want** GraphGuard's CI jobs
isolated from every other container, stripped of privileges, built only from pinned code,
and every commit and dependency scanned, **so that** a poisoned dependency, action or image
cannot reach anything else on the box, and a leaked secret or a known-vulnerable package
fails the build instead of shipping.

What it delivered (runbook `docs/runbooks/ci.md`):
- Jobs in our own pinned image on **a fresh network per job, with no capabilities**; an
  isolation probe is the first step of every run and fails the build if that regresses
- Actions pinned to **commit SHAs** (a test fails on any tag); no `curl | sh` anywhere
- **Secret scanning** in pre-commit and on the whole history in CI; the full history was
  scanned once — no real secret was ever committed
- **Dependencies:** nothing younger than 14 days is resolved; locks checked and scanned
  for known vulnerabilities in CI; the vulnerable packages found were upgraded
- The **serving image rebuilt** from the current lock on a digest-pinned, patched base
  (0.1.3), rolled out with zero downtime; 2,000/2,000 scores identical

### S5b.3 — Backups *(short until its turn)*
**As the** owner, **I want** MLflow's history backed up off the box with a restore that
is actually tested, **so that** a dead disk does not erase every experiment.
- Own restic repo in an own B2 bucket (Lubo creates bucket + key; nothing of LuBot's
  backup reused). Daily; restore-check timer (pattern: MissionCopilot)
- The online store needs no backup — it is rebuilt from data (S5b.1 proves how fast)

### S5b.4 — k3s control plane and the box's second wall *(short until its turn)*
**As the** owner, **I want** k3s's admin ports reachable from the box only, and a host
firewall behind the Hetzner one, **so that** one mistake in the Hetzner console does not
expose the box.
- Current state (details: private audit, not in this public repo)
- k3s flags (bind address, kubeconfig mode `600`) — needs a k3s **service restart**,
  never `k3s-killall.sh`
- Host firewall: planned with a rollback, applied by ONE session together with the
  LuBot session, every app verified. Never by surprise
- LuBot's own findings handed to the LuBot session, which fixes them (details: private audit, not in this public repo)

---


### S5b.5 — One user per job *(short until its turn)*
**As a** model-risk reviewer, **I want** each lakehouse job to run as its own Unix user
(or its own container) that can read only its own `.secrets/identity-<name>.env`, **so
that** "trainer cannot read the test set" holds even against a trainer process that
goes looking for the builder's secret — the honest limit recorded in ADR 0003.

### S5b.6 — Keys and secrets *(short until its turn)*
**As the** owner, **I want** every key on a rotation runbook and the retired S5.6b AWS
key re-decided, **so that** no long-lived credential exists that nobody is watching.
- The S5.6b key (`graphguard-lakehouse`) is active by Lubo's choice (accepted risk,
  S5.6d): it is the one key that still reaches `sealed` directly on S3
- Dex client secrets, OpenFGA key, DB passwords: rotation steps tested once

### S5b.7 — MLflow server 2 → 3 *(short until its turn)*
**As an** ML engineer, **I want** the MLflow server on a current, supported 3.x release
with the client on the same major, **so that** the experiment record stays maintained and
every client call works. A database migration, so it comes after S5b.3 (backups with a
tested restore): dump, upgrade, compare every experiment and run, roll back if any differ.

