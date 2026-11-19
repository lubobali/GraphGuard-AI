# Runbook — secrets (S5b.6)

Every file in `.secrets/` is registered in `src/graphguard/ops/secrets_registry.py`:
who holds it, how it rotates, its maximum age. Rotation dates live in
`private/secrets/ledger.json`.

```
just secrets-status     # exit 1: overdue, untracked, missing, wrong mode or owner
```

## Rules

- **Keys are typed into the box, never pasted into chat.** In your own terminal (ssh /
  Termius): `just secret-set backup-aws.env` (or `lakekeeper-aws.env`, `aws.env`,
  `hetzner-readonly.env`). Hidden input, validated, written 600 in place, date recorded.
- A key that went through chat, email or a screenshot is rotated.
- A new secret file gets a registry entry in the same commit, or `secrets-status` fails.

## Rotating (generated on the box — no console needed)

| Command | What | Downtime (measured 2026-11-19) |
|---|---|---|
| `just rotate-pg superuser` | Postgres superuser (admin, backups) | none |
| `just rotate-pg mlflow_app` | MLflow's role | MLflow restart, seconds |
| `just rotate-pg lakekeeper` | Lakekeeper's role | Lakekeeper recreate, seconds |
| `just rotate-pg dex` / `openfga` | their roles | that container, seconds |
| `just rotate-pg lakehouse` | stale SQL catalog's role | none |
| `just rotate-identities` | the four Dex client secrets; old ones proven refused | Dex recreate, seconds |
| `just rotate-openfga` | OpenFGA ↔ Lakekeeper key | both recreated, seconds |
| `just rotate-redis` | the three Redis users | two Redis restarts: 0.2 s + 0.4 s of errors, ~11 s of cold answers while refilling; the scorer itself rolls with zero errors |

Each one changes the secret where it is checked, updates the files its holder reads (in
place — bind mounts keep seeing them), restarts only that GraphGuard container, and
**proves** the holder works; on failure it puts the old secret back. New Postgres
passwords are sent as SCRAM verifiers: the plain password never reaches a command line
or a log. Run `just backup` afterwards so the off-box copy has the new secrets.

## Rotating (cloud consoles — Lubo)

AWS keys (`graphguard-lakekeeper`, `graphguard-backup`, `graphguard-lakehouse`): create a
second key in IAM → `just secret-set <file>` → restart the holder (Lakekeeper:
`just lakekeeper-up`; backups: next run) → check it works → deactivate the old key → delete
it. Hetzner token: new Read token → `just secret-set hetzner-readonly.env` →
`just edge-check` → delete the old token. The backup repository's password is changed with `restic key add`,
check a backup and the drill, `restic key remove <old id>`, update the password manager.

## Not rotatable in place

Lakekeeper's encryption key (`LAKEKEEPER__PG_ENCRYPTION_KEY`) encrypts the storage
credentials it stores; changing it needs re-encryption. It is backed up (S5b.3).
