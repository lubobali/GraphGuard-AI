# Runbook — MLflow (S5b.7)

MLflow **3.17.2**, server and client the same version (`tests/test_mlflow_version.py` fails
the build otherwise). Image `graphguard/mlflow:3.17.2` from `docker/mlflow.Dockerfile`:
digest-pinned base, Debian security updates, every package installed by hash from
`docker/mlflow-requirements.txt`.

| | |
|---|---|
| UI / API | `127.0.0.1:5010` (ssh tunnel), **login required** |
| Backend | Postgres `mlflow` as role `mlflow_app` (`postgresql+psycopg2://` — SQLAlchemy 2.1 would pick a driver the image does not ship) |
| Logins | Postgres `mlflow_auth` (own role; backed up and drilled like every database) |
| Workers | 1 web worker, background job system off (`MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false`: it runs 7 extra processes for GenAI features we do not use) — 354 MiB, cap 640M |

## Logins

| User | Who | Can |
|---|---|---|
| `admin` | Lubo, the UI | everything |
| `trainer` | `build-artifacts` (gg-trainer; file handed in by systemd) | EDIT `graphguard` |
| `research` | Phase 2-4 scripts, tracking tests (root) | EDIT `graphguard`, MANAGE `graphguard-tests` |

Anonymous requests: 401. New users see nothing until granted. Only admin can delete runs
or change permissions. Grants are data in `src/graphguard/ops/mlflow_auth.py`; apply with
`just mlflow-auth-setup` (idempotent). Searches are *filtered* to what the caller may
read; direct reads outside that are 403. Proof: `tests/ops/test_mlflow_auth_live.py`.

Code logs in through `graphguard.tracking.use_login()`: the login named by
`GRAPHGUARD_MLFLOW_USER` (default `research`), from `mlflow-<user>.env`.

**Lubo's password:** `just mlflow-admin-password` — in your own terminal, then into your
password manager. Change it in the UI, or with the update-password API.

## Rotating

`just rotate-mlflow-users` (trainer, research, and the CSRF key — logs out open UI
sessions); `just rotate-pg mlflow_auth` / `mlflow_app` (database roles).

## Upgrading MLflow (how S5b.7 did it)

1. Pick a release ≥ 14 days old; OSV-check it; `just mlflow-requirements <version>`;
   build `graphguard/mlflow:<version>`; bump `mlflow-skinny` in `pyproject.toml` to the
   same version; `uv lock` (then `./scripts/bootstrap.sh` or `uv sync` **with the extras**
   — a bare `uv sync` strips them from the venv).
2. `just mlflow-rehearse <new image> <current image>`: fresh backup → restored copy in a
   throwaway Postgres → `mlflow db upgrade` → every run compared with the live server →
   an artifact downloaded → the rollback (old image on the pre-migration dump) compared
   too. Must print 0 differences twice.
3. Live: `just backup`, a local `pg_dump -Fc mlflow` → stop MLflow →
   `docker compose run --rm --no-deps mlflow mlflow db upgrade postgresql+psycopg2://mlflow_app@mlflow-db:5432/mlflow`
   → up → compare with the snapshot taken before.

S5b.7's numbers: migration 4-5 s on the copy, 20 s of downtime live, 196 runs with 0
differences, the rollback proven on the copy.

## Rolling back to 2.19

Stop MLflow; restore the pre-migration dump into a fresh `mlflow` database
(`private/backups/pre-mlflow3-*.dump`, or the restic snapshot from before); set the
compose image back to `graphguard/mlflow:2.19.0` (kept), its backend URI and flags as in
git history; start. The rehearsal proved this path on a copy.
