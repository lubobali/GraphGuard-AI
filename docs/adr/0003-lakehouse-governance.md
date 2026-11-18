# ADR 0003 — Lakehouse governance: Dex logins, OpenFGA grants, vended S3 keys

**Status:** accepted, 2026-11-18 (S5.6d)
**Decided by:** Lubo (Dex chosen 2026-11-18; story approved), on the measurements below

## Context

After S5.6c, Lakekeeper had no login: anything on the box could read or change any
table, `sealed` included, and every job held one S3 key that opened all of
`lakehouse/`. "Training never touched the test set" rested on a lint guard and good
behaviour. The goal was to make it a property of the platform, the way Unity Catalog
or Snowflake grants make it one, and to prove it with tests that expect denials.

Governance needs three answers: **who** is calling, **what** they may do, and **which
files** their key opens. A catalog that answers the first two but leaves a shared
storage key in place is a lock with the back door open.

## Options

| Question | Chosen | Alternatives considered |
|---|---|---|
| Who (identity) | **Dex v2.46.1** — OIDC, client-credentials grant (new in 2.46), Go, **11 MB** | Keycloak (Java, hundreds of MB); AWS Cognito (no container, but console work and an internet round trip per login) |
| What (authorization) | **OpenFGA v1.14.2** — Lakekeeper's open-source authorizer, **45 MB**, no host port | Cedar (Lakekeeper Plus, paid); `allowall` (none) |
| Which files (storage) | **AWS STS vended keys**, 1 hour, scoped per table by Lakekeeper's session policy | Remote signing (DuckDB cannot use it); a static key per job (cannot scope per table, never expires) |

OpenFGA is pinned to 1.14, not the newest 1.22, because it is the version Lakekeeper
0.15.1 is tested with.

## Decision

- Four machine identities in Dex: `builder`, `trainer`, `reader`, `admin`.
- The access policy is code (`governance.py`), applied idempotently by
  `just lakekeeper-init`: builder writes everything; trainer and reader read silver and
  gold, get `describe` only on bronze, and nothing on `sealed`. `check_plan()` refuses
  any policy that would let them reach the test window, including by inheritance from
  a warehouse-level grant.
- **Bronze is treated as test data too** (FINDING-011): it is the raw CSV.
- The warehouse vends keys through the role `graphguard-lakekeeper-vending`. The only
  long-lived key is Lakekeeper's own; by itself it can only assume that role.

## Evidence (all on the live system, all kept as tests)

- No token, a garbage token, and a forged RS256 token with the right issuer and
  audience: **401**.
- trainer/reader: `sealed` is not listed and loads as "no such table"; commits are
  **403** from the catalog; data files are **AccessDenied** from S3 (read-only keys).
- trainer's silver key fetching a `sealed` or bronze file **by path**: AccessDenied.
  Even builder's silver key cannot read a `sealed` file.
- Bronze loads with **no key** for trainer and reader; DuckDB as reader gets
  "Forbidden" when refreshing credentials for it.
- Nothing else changed: the build (34 s, 1.2 GB), store-load (512,705 accounts),
  `just sql`, training's silver read (4,061,486 rows, same hash as builder's) and
  **2,000/2,000 live scores identical** — all run with the old key file removed.
- RAM: Dex 11-12 MB, OpenFGA 44-46 MB, Lakekeeper 39 → 45 MB peak with authz on.

## Consequences

- Three always-on services instead of one (~100 MB together), all on 127.0.0.1 or no
  port at all, each with its own database and user; `just lakekeeper-status` checks all.
- A Dex or OpenFGA outage stops builds, reloads and SQL — not scoring (Redis holds the
  features).
- Rebuilding the catalog means a fresh bootstrap and re-registering tables from an
  export (done once here; no data moved). Ownership and grants come from
  `governance.py`, so they are rebuilt by one command.
- **Honest limit:** every job runs as root on one box, so a job could read another
  job's secret file. The boundary holds for a process that has only its own
  credentials. Per-job Unix users or containers are Phase 5b work (S5b.5).
- The final test-set evaluation will need an `evaluator` identity with a one-time
  grant on `sealed` — created only then (contract rule 4).
