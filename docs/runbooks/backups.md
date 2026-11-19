# Runbook — GraphGuard's backups (S5b.3)

Nightly (03:20 UTC) GraphGuard's irreplaceable state goes, encrypted by restic, to its own
S3 bucket with **Object Lock** (Governance, 30 days). Weekly (Sunday 05:10 UTC) a drill
restores the latest snapshot into a throwaway Postgres and proves it.

| | |
|---|---|
| Tool | restic 0.19.1, pinned + checksum-verified in `scripts/bootstrap.sh` (`.tools/bin/restic`) |
| Code | `src/graphguard/ops/backup.py`; timers in `systemd/` (`just backup-install`) |
| Bucket | `graphguard-backups-0dcd18` (us-east-1), Object Lock Governance 30 d, versioned, noncurrent versions expire after 31 d |
| Key | IAM user `graphguard-backup`, policy `graphguard-backup-s3` (below): write and read current objects, see the lock settings; **denied** deleting or even reading old versions, changing retention, or changing the bucket — `.secrets/backup-aws.env`. Proven live: `tests/ops/test_backup_live.py` (11 tests) |
| Password | `.secrets/backup-restic-password` (600) **and Lubo's password manager** — without it, nothing can be restored |
| Kept | every DB in `pg_access.SERVICES` (`pg_dump -Fc`) + roles, MLflow artifacts, row counts, `.secrets/`, `models/production/`, `private/` |
| Not kept | lakehouse data (S3, versioned), Redis (`just store-load`), raw CSV (Kaggle) |

## Everyday

```
just backup-status   # last backup / drill; exit 1 if stale (2 d / 8 d) or failed
just backup          # a backup now
just restore-check   # the drill now
systemctl list-timers 'graphguard-*'
journalctl -u graphguard-backup -u graphguard-restore-check --since -2d
```

## When `backup-status` says FAIL

Read the error it prints, then the journal. Common: the bucket key changed (update
`.secrets/backup-aws.env`), Docker or Postgres down at 03:20 (the next night retries;
`Persistent=true` catches up after downtime), a stale restic lock after a crash
(`restic unlock` — only if no backup is running).

## Proving it

```
uv run pytest -m integration tests/ops/test_backup_live.py   # the key cannot destroy history; lock = Governance 30 d
```

restic 0.19.1 writes to an Object Lock bucket without extra settings (it sends the
checksum header AWS requires) — checked in S5b.3 before anything else.

## Setup (done once, 2026-11-19)

The AWS steps are on the copy-paste page used in S5b.3 (bucket with Object Lock at creation,
30-day Governance default retention, lifecycle, policy `graphguard-backup-s3`, user
`graphguard-backup`). Then: key into `.secrets/backup-aws.env` with
`RESTIC_REPOSITORY=s3:s3.us-east-1.amazonaws.com/graphguard-backups-0dcd18/restic`,
password generated into `.secrets/backup-restic-password` and given to Lubo,
`uv run python -m graphguard.ops.backup init`, `just backup-install`.

## Rebuild on a new box (disaster recovery)

You need: the repository password (Lubo's password manager), the backup key
(`graphguard-backup`, or create a new key for it in IAM), and this repo.

1. Box ready: Docker, Tailscale; `git clone` the repo to `/srv/graphguard`; `./scripts/bootstrap.sh`
2. Restore the files:
   ```
   export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=us-east-1
   export RESTIC_REPOSITORY=s3:s3.us-east-1.amazonaws.com/graphguard-backups-0dcd18/restic
   .tools/bin/restic snapshots                         # asks for the password
   .tools/bin/restic restore latest --tag nightly --target /tmp/gg-restore
   cp -a /tmp/gg-restore/.secrets /tmp/gg-restore/private /srv/graphguard/
   cp -a /tmp/gg-restore/models /srv/graphguard/
   ```
3. Postgres: `docker compose --env-file .secrets/mlflow.env up -d mlflow-db`, then load the
   roles and each database from `/tmp/gg-restore/private/backups/<run>/dumps/`:
   `globals.sql` with `psql`, each `<db>.dump` with `pg_restore -d <db>` (as the superuser,
   `PGPASSWORD=$POSTGRES_PASSWORD`).
4. Services: `just mlflow-up`, `just lakekeeper-up` (Lakekeeper decrypts its storage
   credential with the key in the restored `.secrets/lakekeeper.env`).
   **If the catalog is older than 7 days**, Iceberg files it points to may have expired
   on S3: rebuild instead with `just lakehouse-build` (~35 s, from the CSV).
5. Online store and scorer: `redis` up, `just store-load`, `just image-build` (or import),
   `just k8s-redis-secret`, `just k8s-deploy`. Check with `just k8s-check` and a score.
6. `just backup-install` on the new box; `just backup-status` after the first night.

## Policy `graphguard-backup-s3`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "SeeTheBucket", "Effect": "Allow",
     "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
     "Resource": "arn:aws:s3:::graphguard-backups-0dcd18"},
    {"Sid": "SeeTheLockIsOn", "Effect": "Allow",
     "Action": ["s3:GetBucketObjectLockConfiguration", "s3:GetBucketVersioning",
                "s3:GetLifecycleConfiguration"],
     "Resource": "arn:aws:s3:::graphguard-backups-0dcd18"},
    {"Sid": "SeeEachBackupIsLocked", "Effect": "Allow",
     "Action": "s3:GetObjectRetention",
     "Resource": "arn:aws:s3:::graphguard-backups-0dcd18/*"},
    {"Sid": "WriteAndReadBackups", "Effect": "Allow",
     "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
     "Resource": "arn:aws:s3:::graphguard-backups-0dcd18/*"},
    {"Sid": "NeverDestroyHistory", "Effect": "Deny",
     "Action": ["s3:DeleteObjectVersion", "s3:BypassGovernanceRetention",
                "s3:PutObjectRetention", "s3:PutObjectLegalHold",
                "s3:PutBucketObjectLockConfiguration", "s3:PutBucketVersioning",
                "s3:PutLifecycleConfiguration", "s3:PutBucketPolicy",
                "s3:DeleteBucketPolicy", "s3:DeleteBucket"],
     "Resource": ["arn:aws:s3:::graphguard-backups-0dcd18",
                  "arn:aws:s3:::graphguard-backups-0dcd18/*"]}
  ]
}
```

Bucket: created **with Object Lock** (cannot be added later), default retention
**Governance, Fixed, 30 days** (not "event hold": that never expires), versioning on, all
public access blocked, SSE-S3. Lifecycle `graphguard-backups-cleanup`: noncurrent versions
deleted after 31 days, expired delete markers and incomplete uploads after 1 day, **no
action on current versions**.
