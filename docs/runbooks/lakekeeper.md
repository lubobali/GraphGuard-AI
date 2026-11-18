# Runbook — Lakekeeper, the lakehouse catalog (S5.6c), with logins, grants and vended keys (S5.6d)

Lakekeeper is the Iceberg REST catalog: the list of tables, where their files are, and
every snapshot. Since S5.6d every request carries a **Dex** token (who you are) and
**OpenFGA** holds the grants (what you may do). The data itself is on S3 and does not
depend on any of the three being up.

| | |
|---|---|
| Containers | `graphguard-lakekeeper`, `graphguard-dex`, `graphguard-openfga` (compose project `graphguard`, network `graphguard-net`) |
| Addresses | Lakekeeper `127.0.0.1:8181`, Dex `127.0.0.1:5556` (token endpoint `/dex/token`); OpenFGA has **no host port** |
| Versions | Lakekeeper v0.15.1, Dex v2.46.1, OpenFGA v1.14.2 (the version Lakekeeper 0.15 is tested with) — all digest-pinned |
| State | databases `lakekeeper`, `dex`, `openfga` (each its own user, refused on the others) in `graphguard-mlflow-db` |
| Secrets | `.secrets/` (600, gitignored): `lakekeeper.env`, `lakekeeper-authz.env`, `lakekeeper-aws.env` (its AWS key), `dex.env`, `openfga.env`, `governance.env`, `identity-<name>.env` |
| S3 access | **vended**: each job gets a 1-hour STS key per table, read-only unless it may write (setup: `aws-vending.md`) |
| Warehouse | `graphguard` → `s3://graphguard-lakehouse-0dcd18/lakehouse/` |
| Memory | caps 192 / 64 / 128 MB (S5b.1, from measured peaks); private memory ~32 / 8 / 29 MB, the rest reclaimable cache |

## Identities and the policy (`src/graphguard/lakehouse/governance.py`)

| Identity | Used by | bronze | silver | gold | sealed |
|---|---|---|---|---|---|
| `builder` | `just lakehouse-build` | write | write | write | write |
| `trainer` | `just build-artifacts` | describe only | read | read | **invisible** |
| `reader` | `just sql`, `just store-load` | describe only | read | read | **invisible** |
| `admin` | `just lakekeeper-init` | operator | | | |

Bronze is metadata-only for trainer and reader because it is the raw CSV, **test window
included** (FINDING-011): they can load its metadata, and Lakekeeper vends **no key**
for its files. To trainer and reader `sealed` does not exist: it is not listed, and
loading it answers "no such table", not "forbidden".

Two locks, each tested on its own: the **catalog** refuses commits it does not allow,
and **S3** refuses any file the vended key was not scoped to — so a job that skips
the catalog and fetches a `sealed` file by path gets AccessDenied.

## Everyday

```
just lakekeeper-status   # all three healthy, with memory; exit 1 otherwise
just lakekeeper-up       # OpenFGA, Dex, then Lakekeeper; never restarts MLflow/Redis
just lakekeeper-down     # stop all three
just lakekeeper-init     # bootstrap, warehouse, namespaces, missing tables, grants; safe to re-run
just lakekeeper-export   # save each table's metadata location + snapshot id
just identity-secrets    # create any missing secret file; never overwrites
just sql "select ..."    # DuckDB as `reader`, catalog ATTACHed as `lk` + short view names
```

Change who may do what **only in `governance.py`**, then `just lakekeeper-init`.
`check_plan()` refuses a policy that would let trainer or reader reach the test window.

## If it is down

1. `just lakekeeper-status`, then `docker logs graphguard-<name> --tail 50`.
2. Postgres down? `docker ps | grep graphguard-mlflow-db` — all three need it.
3. `just lakekeeper-up`. The scorer keeps working meanwhile: Redis already holds the
   features; only builds, reloads and SQL need the catalog.
4. A job says `401`: Dex is down or its secret changed — `docker logs graphguard-dex`.
   A job says `403` or "no such table": the policy says no; check `governance.py`.
5. S3 `AccessDenied` for a table a job *should* reach: check the vending role still
   exists and `just lakekeeper-init` succeeds (it re-validates storage).

## Rotating a job's secret

Delete its `.secrets/identity-<name>.env` **and** `.secrets/dex.env`, run
`just identity-secrets`, then recreate Dex:
`docker compose --env-file .secrets/mlflow.env up -d --no-deps --force-recreate dex`.

## Moving or rebuilding the catalog (no data moves)

Iceberg tables are files on S3; a catalog only points at each table's current metadata.
S5.6d rebuilt Lakekeeper this way:

1. `just lakekeeper-export` (writes `lakehouse/catalog-export.json`).
2. Fresh catalog database, then `just lakekeeper-up` and `just lakekeeper-init`:
   it **registers** every exported table that is missing. Snapshot ids are unchanged.

## Locked out, or rolling back to S5.6c

The S5.6c catalog database is kept as `lakekeeper_s56c` (no logins, `allowall`). To use
it: stop Lakekeeper, point `LAKEKEEPER__PG_DATABASE_URL_*` at `lakekeeper_s56c`, set
`LAKEKEEPER__AUTHZ_BACKEND=allowall` and drop the `OPENID_*` settings in compose, start
it, and open catalogs with `open_rest_catalog(None)`. Its warehouse still names the
S5.6b key, **deleted after S5.6d** — so first re-send the storage credential with the
vending setup (`lakekeeper.storage_profile` / `storage_credential`), and give clients a
key: `open_rest_catalog(None)` reads `.secrets/aws.env`. Its tables point at the metadata
of 2026-11-18 18:10; re-register from a fresh export if newer builds happened. It is
safe only because Lakekeeper is bound to 127.0.0.1 — but it has no permissions at all,
so treat it as an emergency path. The older SQL catalog (`GRAPHGUARD_CATALOG=sql`) is
staler still.

## Safety notes

- Never publish 8181 or 5556 beyond 127.0.0.1, and never give OpenFGA a host port.
- Never add Dex's `mockCallback` connector: it lets anyone log in. The password DB is
  enabled only because Dex will not start without a connector; it has **zero** users,
  and only the client-credentials grant is allowed.
- Jobs hold **no** S3 key. Never put one back in `.secrets/aws.env` for a job: a
  long-lived key opens every table's files and silently undoes the S3 lock.
- Remote signing stays off (DuckDB cannot use it; vended keys already scope tables).
- All jobs run as root on one box, so a job could read another's secret file. The
  boundary holds for a process that has only its own credentials; per-job users are
  Phase 5b work (S5b.5).
