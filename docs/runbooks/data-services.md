# Runbook — GraphGuard's data services: Redis and Postgres (S5b.1)

Both are GraphGuard's own, on `graphguard-net`, bound to private addresses only, and
locked down like every GraphGuard container (`tests/test_compose_hardening.py`).

## Redis — the online store

| | |
|---|---|
| Image | `redis:7.4.x-alpine`, pinned by digest |
| Users | `scorer` (read accounts), `loader` (fill/prune + the stream's seed), `stream` (the stream's single writer, S6.3: plain commands + MULTI/EXEC, no scripting), `tests` (test keys, db 15); the default user is **off** |
| Rules | `src/graphguard/serving/redis_acl.py` → `.secrets/redis-users.acl` (SHA-256 hashes only), loaded at start |
| Passwords | `.secrets/redis.env` (600); the scorer's URL is the Kubernetes Secret `graphguard-redis` |
| Data | none on disk by design — a restart empties it; `just store-load` refills accounts **and resets the stream's state** (windows, seen pairs, watermarks) from gold in ~22 s |
| Memory | 320mb of data, 448m container cap, `noeviction` — measured peak 224 MB / 303 MiB after a full validation replay (S6.3) |

```
just redis-secrets      # create missing passwords (never overwrites) + rewrite the ACL file
just k8s-redis-secret   # push the scorer's URL to Kubernetes (stdin, never a command line)
docker compose --env-file .secrets/mlflow.env restart redis && just store-load
```

- **Add a command for a user** only in `redis_acl.py` (its tests list exactly what each
  user may run), then `just redis-secrets`, restart Redis, `just store-load`.
- **Rotate a password**: delete its line from `.secrets/redis.env`, `just redis-secrets`,
  restart Redis, `just store-load`, and for `scorer` also `just k8s-redis-secret` and
  `just k8s-deploy` (the pod rolls with zero downtime).
- **Admin access**: there is no admin user on purpose. To inspect, use the `loader`
  password through the environment, never as an argument (arguments show in `ps`):
  ```
  export REDISCLI_AUTH=$(grep '^GG_REDIS_LOADER_PASSWORD=' .secrets/redis.env | cut -d= -f2)
  docker exec -e REDISCLI_AUTH graphguard-redis redis-cli --user loader --no-auth-warning --scan --pattern 'gg:acct:*' | wc -l
  unset REDISCLI_AUTH
  ```
  (`-e REDISCLI_AUTH` without a value copies it from your shell.)
- Health: the container is "healthy" when Redis answers — `NOAUTH` counts.

## Postgres — catalogs and MLflow

| | |
|---|---|
| Image | `postgres:16.x-alpine`, pinned by digest, runs as uid 70 |
| Who reaches what | `src/graphguard/ops/pg_access.py` → `docker/postgres/pg_hba.conf`: each service its own role and database, SCRAM passwords, everything else rejected; the superuser only on the container's local socket |
| Roles | `mlflow_app` (MLflow), `lakekeeper`, `dex`, `openfga`, `lakehouse` (rollback); the superuser is never used by a service |
| Secrets | `.secrets/mlflow.env` (superuser), `.secrets/mlflow-app.env` + `.secrets/mlflow-pgpass` (MLflow, read through `PGPASSFILE`), `.secrets/governance.env`, `.secrets/lakekeeper.env`, `.secrets/lakehouse.env` |

- **Admin psql** (a password is required now, also on the local socket):
  `docker exec -it graphguard-mlflow-db sh -c 'PGPASSWORD=$POSTGRES_PASSWORD psql -U "$POSTGRES_USER" -d postgres'`
- **A new service database**: create role + database (`REVOKE ALL ... FROM PUBLIC`), add
  one line to `SERVICES` in `pg_access.py`, `just pg-access`, restart `mlflow-db`, and
  extend `tests/ops/test_pg_access_live.py`.
- **Minor upgrade** (16.x → 16.y): swap the digest, `up -d --no-deps mlflow-db`; same data
  volume. Dump first (`pg_dump -Fc` per database).
- **Backups**: until S5b.3, take a one-off `pg_dump -Fc` per database before any change
  and restore it once into a throwaway container to prove it.
