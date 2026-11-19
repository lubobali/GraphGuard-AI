# Runbook — one user per job (S5b.5)

Every lakehouse job runs as its own unprivileged user, in a transient systemd unit that
is capped, read-only except for what it writes, has no capabilities and cannot see other
processes — and is handed **only its own credentials** (systemd `LoadCredential`, read
from `$CREDENTIALS_DIRECTORY` by `graphguard.config.secrets_dir()`).

| `just` | User | Credentials handed in | Writes | Cap |
|---|---|---|---|---|
| `lakehouse-build` | gg-builder | identity-builder | lineage log, `lakehouse/tmp` | 1800M (peak 1.1 GB) |
| `build-artifacts` | gg-trainer | identity-trainer | lineage log, `models/production` | 2560M (peak 2.0 GB) |
| `store-load` | gg-reader | identity-reader, Redis loader password | lineage log | 1G (peak 0.5 GB) |
| `sql` | gg-reader | identity-reader | — | 512M |
| `notebook` | gg-reader | identity-reader | `notebooks/` | 1G |

**No job can see:** `.secrets/`, `private/`, `runner/`, the Docker socket, k3s's
kubeconfig and state. **Trainer and reader also cannot see** the raw CSVs (they hold the
test window); the trainer gets only the ring list. Profiles: `src/graphguard/ops/jobs.py`
— change access there, nowhere else. `lakekeeper-init` (admin) and the tests stay root.

## Proving it

```
uv run pytest -m integration tests/ops/test_jobs_live.py   # from inside each job
```

## Setup (done once)

`just job-users-install`: declares the users in `/etc/sysusers.d/graphguard.conf` (no
shell, no home, no other groups) and gives the job groups write access to the folders
above. Per-user Redis files (`redis-<user>.env`) come from `just redis-secrets`.

## When a job fails with "Read-only file system" or "Permission denied"

The sandbox hid a path the job needs. Add **that path** to the job's `writes` (or its
credential to `credentials`) in `jobs.py`, with a comment saying why — never widen to the
whole repo. Two such paths were found this way when S5b.5 was built: the builder's
scratch folder and DuckDB's spill folder (now the job's private `/tmp`).

## Removing

Point the five recipes back at `{{UV}} run python -m <module>`, then
`userdel gg-builder; userdel gg-trainer; userdel gg-reader; groupdel gg-jobs` and delete
`/etc/sysusers.d/graphguard.conf`.
