# Runbook — Lakekeeper, the lakehouse catalog (S5.6c)

Lakekeeper is the Iceberg REST catalog: the list of tables, where their files are, and
every snapshot. The data itself is on S3 and does not depend on Lakekeeper being up.

| | |
|---|---|
| Container | `graphguard-lakekeeper` (compose project `graphguard`, network `graphguard-net`) |
| Address | `http://127.0.0.1:8181` — the box only; blocked from the internet, k3s pods and other Docker networks |
| Version | `quay.io/lakekeeper/catalog:v0.15.1`, pinned by digest |
| State | database `lakekeeper` (own user) in `graphguard-mlflow-db` |
| Secrets | `.secrets/lakekeeper.env` (DB URL, encryption key) — 600, gitignored |
| Warehouse | `graphguard` → `s3://graphguard-lakehouse-0dcd18/lakehouse/` |
| Memory | cap 256 MB; measured ~24 MB idle, 30-32 MB during a full build |
| Login | **none until S5.6d (Dex)** — that is why it listens on 127.0.0.1 only |

## Everyday

```
just lakekeeper-status   # exit 1 unless healthy
just lakekeeper-up       # start (runs the DB migration first); never restarts MLflow/Redis
just lakekeeper-down     # stop
just lakekeeper-init     # bootstrap + warehouse; safe to re-run
just sql "select ..."    # DuckDB over the tracked tables, through the catalog
```

## If it is down

1. `just lakekeeper-status`, then `docker logs graphguard-lakekeeper --tail 50`.
2. Postgres down? `docker ps | grep graphguard-mlflow-db` — Lakekeeper needs it.
3. `just lakekeeper-up`. The scorer keeps working meanwhile: Redis already holds the
   features; only builds, reloads and SQL need the catalog.

## Rollback to the old SQL catalog

The PyIceberg SQL catalog (database `lakehouse`) was the catalog before S5.6c. It is
**stale**: it stopped seeing commits when Lakekeeper took over. To roll back:

1. `export GRAPHGUARD_CATALOG=sql`
2. Point each table in it at Lakekeeper's latest metadata, or simply rebuild:
   `just lakehouse-build` (~35 s), then `just store-load`.

Because the tables are plain Iceberg on S3, moving to any other catalog (the SQL one,
Polaris, Unity) means **re-registering** metadata files, never copying data.

## Safety notes

- Never publish port 8181 beyond 127.0.0.1 and never attach Lakekeeper to another
  Docker network until S5.6d adds authentication.
- Credential vending and remote signing are **off** in the warehouse profile; a unit
  test keeps them off. Clients use the S3 key in `.secrets/aws.env`, which IAM limits
  to `lakehouse/`.
- DuckDB's full `ATTACH` (used for writes) exposes every namespace including `sealed`,
  so only code that must write uses it; `just sql` uses tracked-table views.
