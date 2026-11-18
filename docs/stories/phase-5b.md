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

## The backlog (moved from Phase 5's S5.8 epic)

**Why:** the box was hacked once. A read-only inventory (2026-11-18) found it well
guarded from the internet — the Hetzner firewall admits only TCP 80/443, SSH is key-only
and reached over Tailscale — but soft inside: no host firewall, and several GraphGuard
parts unhardened. GraphGuard must never be the weak door into LuBot or anything else.

**Split by risk, lowest first.** Each sub-story is expanded fully just before it starts.

| | Sub-story | Touches | Risk |
|---|---|---|---|
| **S5b.1** | Harden GraphGuard's own containers and pod | only GraphGuard | low |
| S5b.2 | Supply chain: CI runner, pinned actions, secret scanning | only GraphGuard | low |
| S5b.3 | Backups: MLflow off the box, with a tested restore | GraphGuard + a new B2 bucket | low, needs Lubo |
| S5b.4 | k3s control plane off the public interface; second wall for the box | box-wide | **high**, with the LuBot session |
| S5b.5 | One Unix user (or container) per job | GraphGuard | medium |
| S5b.6 | Keys and secrets: rotation, the retired AWS key | GraphGuard + AWS | low, needs Lubo |

Facts already established: Hetzner firewall = TCP 80/443 inbound only (Lubo's console,
2026-11-18). Ray dashboard locked by NetworkPolicy (S5.3). Scorer runs as uid 10001.

---

### S5b.1 — Harden GraphGuard's own containers and pod

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

**Out of scope:** k3s flags and kubeconfig permissions (S5b.4 — needs a k3s restart);
the CI runner (S5b.2); backups (S5b.3); anything LuBot's.

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

### S5b.2 — Supply chain *(short until its turn)*
**As the** owner, **I want** CI jobs and commits unable to leak secrets or run tampered
code, **so that** the build pipeline is not a way in.
- Runner job containers: `--cap-drop=ALL`, `no-new-privileges`, a network per job
  (pattern: `lubobali-runner`). Runner today: no Docker socket ✅, limits ✅, shared
  `bridge` network ❌
- `actions/checkout` pinned by commit SHA, not `@v4`
- gitleaks in prek and CI (pattern: lubobali CI)

### S5b.3 — Backups *(short until its turn)*
**As the** owner, **I want** MLflow's history backed up off the box with a restore that
is actually tested, **so that** a dead disk does not erase every experiment.
- Own restic repo in an own B2 bucket (Lubo creates bucket + key; nothing of LuBot's
  backup reused). Daily; restore-check timer (pattern: MissionCopilot)
- The online store needs no backup — it is rebuilt from data (S5b.1 proves how fast)

### S5b.4 — k3s control plane and the box's second wall *(short until its turn)*
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
