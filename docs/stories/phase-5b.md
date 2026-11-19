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
| S5b.3 | Backups: MLflow off the box, with a tested restore | GraphGuard + a new S3 bucket | low, needs Lubo |
| S5b.4 | k3s off the internet (no restart) + a front-door watchdog | GraphGuard + one INPUT jump | low |
| S5b.4b | The full host firewall for the box | box-wide | **high**, with the LuBot session |
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

### S5b.3 — Backups off the box, immutable, with a weekly restore drill ✅ done 2026-11-19

**As the** owner of a box that was hacked once, **I want** GraphGuard's experiment history,
catalogs, identities and secrets backed up off the box every night — encrypted, kept
immutable for 30 days, and restored automatically every week to prove it — **so that** a
dead disk, a bad migration or an attacker with root costs at most a day of work, never the
project.

What it delivered (runbook `docs/runbooks/backups.md`):
- **Nightly** (03:20 UTC) restic backup of every service database, MLflow artifacts,
  secrets, the production model and the private records, encrypted on the box, to a new
  S3 bucket with **Object Lock (Governance, 30 days)**; ~13 MB, 4-5 s; time-based retention
- A **backup-only key that cannot destroy history** — deleting or reading old versions,
  shortening or bypassing the lock, changing the bucket: all denied, proven by 11 live tests
- A **weekly drill** (Sundays) that restores into a throwaway offline Postgres and must
  find exactly the backed-up row counts, secrets and model byte-equal; `just backup-status`
  exits 1 when a backup is > 2 days or a drill > 8 days old or failed
- Both run as **sandboxed, capped systemd timers** outside LuBot's night jobs
- A **disaster rebuild** written and walked once: the restored catalog points at exactly
  the live tables, which still load from S3
- The repository password is also kept off the box, by Lubo

### S5b.4 — k3s off the internet, and a watchdog on the front door ✅ done 2026-11-19

**As the** owner of a box whose only wall is one cloud-console setting, **I want** k3s's
ports closed to the internet on the box itself and a daily check that the cloud firewall
and the box's public listeners have not changed, **so that** one wrong click neither
exposes the cluster nor goes unnoticed — **without stopping or restarting any app**.

What it delivered (runbook `docs/runbooks/edge.md`):
- k3s's ports dropped on the public interface, IPv4 and IPv6, in GraphGuard's own chain —
  **nothing restarted**; applied with a 5-minute automatic undo; re-applied at boot;
  self-repairing; removable in one command
- Before and after identical: every site, every container, the k3s pods, 2,000/2,000
  scores, MLflow, Lakekeeper, Dex
- A **daily read-only watchdog** — the cloud firewall (through a token proven unable to
  write), the box's public listeners against a private baseline, the guard itself;
  `just edge-status` exits 1 on any drift. Proven by breaking the guard and opening a
  listener on purpose: both caught
- The cloud firewall was confirmed to cover IPv6 as well as IPv4

### S5b.4b — The box's full host firewall *(later, with the LuBot session)*
A default-deny host firewall for the whole box, written with the LuBot session, applied in
a planned window with an automatic undo, every app verified. Builds on S5b.4's chain,
removal path and watchdog.

---


### S5b.5 — One user per job ✅ done 2026-11-19
**As a** model-risk reviewer, **I want** each lakehouse job to run as its own unprivileged
user that is handed only its own credential, **so that** "trainer cannot read the test
set" holds even against a trainer process that goes looking — the honest limit recorded in
ADR 0003.

What it delivered (runbook `docs/runbooks/job-users.md`):
- Three system users (no shell, no home, no other groups); every lakehouse job runs as
  its own, in a capped, sandboxed systemd unit handed **only its own credential**
- No job can see other jobs' secrets, Docker or k3s; trainer and reader cannot see the raw
  CSVs — **proven from inside each job** by 10 live tests (as trainer: no builder login
  possible, `sealed` and bronze refused, silver still readable)
- Same results as before: all five tables with identical row counts after a rebuild as
  the builder, a **byte-identical model** retrained as the trainer, **2,000/2,000 scores
  identical** after a reload as the reader; caps set from measured peaks
- ADR 0003's honest limit closed for jobs, with what remains written down

### S5b.6 — Keys and secrets ✅ done 2026-11-19 (slim scope)
**As the** owner, **I want** every GraphGuard secret listed with who holds it and how to
rotate it, a check that fails when one is overdue, unknown or loosely permissioned, and
each on-box kind rotated once for real, **so that** no credential exists that nobody is
watching — and a rotation is a rehearsed command.

What it delivered (runbook `docs/runbooks/secrets.md`):
- A **registry of every secret** in code and **`just secrets-status`**, which fails on
  overdue, untracked, missing or wrongly permissioned secrets — its first run found a
  leftover duplicate, now removed
- **`just secret-set`**: console keys are typed into the box with hidden input, never
  pasted into chat
- **Every on-box kind rotated once, for real**, each proven by its holder and rolled back
  automatically on failure: six Postgres roles (sent as SCRAM verifiers, never plain), the
  four Dex client secrets (old ones proven refused), the OpenFGA key, and the three Redis
  users — measured under load: two sub-second blips at the Redis restarts, and **zero
  errors while the scorer rolled** onto the new password; 2,000/2,000 scores identical
- Backups now read the database password from the secrets folder, so a rotation never
  breaks them; a backup and the restore drill passed after the last rotation
- Cloud-console keys kept by decision (a demo project); recorded as an accepted risk

### S5b.7 — MLflow server 2 → 3 *(short until its turn)*
**As an** ML engineer, **I want** the MLflow server on a current, supported 3.x release
with the client on the same major, **so that** the experiment record stays maintained and
every client call works. A database migration, so it comes after S5b.3 (backups with a
tested restore): dump, upgrade, compare every experiment and run, roll back if any differ.

