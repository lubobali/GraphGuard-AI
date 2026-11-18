# AWS setup for GraphGuard's lakehouse (S5.6b)

**Who:** Lubo, in the AWS console. About 10 minutes.
**Account:** the existing AWS account — but a **new** bucket and a **new** IAM user used
only by GraphGuard. Nothing belonging to `aws-job-streamer` is opened, reused or edited.
**Cost target:** about $1/month once the free credits end (~1 GB stored, a few thousand
requests a month). The lifecycle rules in step 2 are what keep it there.

Region for everything: **us-east-1** (N. Virginia) — the box is in Ashburn, 3.7 ms away.

---

## 1. Create the bucket

S3 → **Create bucket**

| Setting | Value |
|---|---|
| Bucket name | `graphguard-lakehouse-0dcd18` (must be globally unique; if taken, add any suffix and tell Claude the final name) |
| Region | us-east-1 |
| Object Ownership | ACLs disabled (bucket owner enforced) |
| Block **all** public access | **On** (all four boxes ticked) |
| Bucket Versioning | **Enable** — the safety net if a cleanup ever deletes the wrong file |
| Default encryption | SSE-S3 (the default) |
| Tags (optional) | `project = graphguard` |

## 2. Lifecycle rules (this is what keeps it at ~$1/month)

Bucket → **Management** → **Create lifecycle rule** → name `graphguard-cleanup`, apply to
**all objects**, and tick:

- **Permanently delete noncurrent versions of objects** → after **7** days
  (versioning keeps old copies of every rewritten file; without this they pile up and
  cost money forever)
- **Delete expired object delete markers or incomplete multipart uploads** → tick
  **Delete incomplete multipart uploads**, after **1** day

## 3. Create the IAM user

IAM → **Users** → **Create user**

- Name: `graphguard-lakehouse`
- **No** console access
- Permissions: **Attach policies directly** → **Create policy** → JSON tab → paste the
  policy below (replace the bucket name if yours differs) → name it
  `graphguard-lakehouse-s3` → attach it to the user. Attach **nothing else**.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SeeTheBucket",
      "Effect": "Allow",
      "Action": ["s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::graphguard-lakehouse-0dcd18"
    },
    {
      "Sid": "ListOnlyTheLakehousePrefix",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::graphguard-lakehouse-0dcd18",
      "Condition": { "StringLike": { "s3:prefix": ["lakehouse/", "lakehouse/*"] } }
    },
    {
      "Sid": "ReadWriteOnlyTheLakehousePrefix",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
        "s3:ListMultipartUploadParts"
      ],
      "Resource": "arn:aws:s3:::graphguard-lakehouse-0dcd18/lakehouse/*"
    }
  ]
}
```

What this allows: read, write and delete **only** under `lakehouse/` in this one bucket.
What it denies (everything else, by default): other buckets, other prefixes, IAM,
billing, every other AWS service. S5.6b has a test that **expects** those denials.

## 4. Create the access key

User `graphguard-lakehouse` → **Security credentials** → **Create access key** →
use case **"Application running outside AWS"** → create. Keep the page open.

## 5. Put the key on the box — yourself, never in chat

In the Claude Code prompt on the box, type:

```
! nano /srv/graphguard/.secrets/aws.env
```

The file already exists (permissions 600, gitignored) with empty values. Fill in:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
GRAPHGUARD_S3_BUCKET=graphguard-lakehouse-0dcd18
```

Save (Ctrl+O, Enter) and exit (Ctrl+X). Then tell Claude "AWS is ready". Claude checks
the file's permissions and that the key works — without ever printing it.

---

**If a key ever leaks:** IAM → the user → Security credentials → **Deactivate** the key,
create a new one, update `.secrets/aws.env`. The damage is limited to the `lakehouse/`
prefix, and versioning keeps 7 days of old copies.

---

**Status 2026-11-18:** done. Bucket, lifecycle rule, policy and user created by Lubo; the
5 live least-privilege tests pass. One deviation: the `!` prompt cannot run an
interactive editor, so the key was pasted into the Claude chat and written to
`.secrets/aws.env` from there (Lubo's decision — a portfolio project, key limited to one
prefix). It is in no code, git history or image. **Recommended:** rotate it once —
create a second access key, put it in `.secrets/aws.env` from your own terminal
(`nano`), run `just test` (the live tests must pass), then delete the first key in IAM.

**Status 2026-11-18, S5.6d:** this key is **retired**. Jobs now get short-lived keys
vended by Lakekeeper (`docs/runbooks/aws-vending.md`); the bucket, lifecycle rule and
the `graphguard-lakehouse-s3` policy stay (the vending role uses that policy). The
access key of `graphguard-lakehouse` is deleted once S5.6d is verified — which also
retires the key that was pasted in chat.
