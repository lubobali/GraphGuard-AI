# AWS setup for vended credentials (S5.6d part 2)

**Who:** Lubo, in the AWS console, about 10 minutes. Done 2026-11-18.
**Account:** the same one as S5.6b. One new IAM user and one new role, used only by
GraphGuard; nothing belonging to `aws-job-streamer` is opened or edited. STS is free.

## What it builds

```
graphguard-lakekeeper (IAM user)          the only long-lived key; held by Lakekeeper alone
   └─ may only: sts:AssumeRole on ─┐
                                   ▼
graphguard-lakekeeper-vending (role)      policy graphguard-lakehouse-s3 → lakehouse/ only
   ▲
   └─ Lakekeeper assumes it for its own work, and again per table for every key it
      vends, with a session policy narrowed to that table: read-only unless the job
      may write, none at all if it may not read. Keys expire after 1 hour.
```

## Steps (as done)

1. **User** `graphguard-lakekeeper`: no console access, **no permissions** at creation.
2. **Role** `graphguard-lakekeeper-vending`: *Custom trust policy* below; attach the
   existing managed policy `graphguard-lakehouse-s3` (S5.6b); no description.

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "OnlyTheLakekeeperUser",
         "Effect": "Allow",
         "Principal": { "AWS": "arn:aws:iam::053849128997:user/graphguard-lakekeeper" },
         "Action": "sts:AssumeRole"
       }
     ]
   }
   ```

3. **Policy** `graphguard-lakekeeper-assume` (IAM → Policies → Create policy → JSON),
   attached to the user with *Attach policies directly*. It is the user's only
   permission. (The user page's *Create inline policy* menu works too; a hand-typed
   console URL for it does not.)

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "AssumeOnlyTheVendingRole",
         "Effect": "Allow",
         "Action": "sts:AssumeRole",
         "Resource": "arn:aws:iam::053849128997:role/graphguard-lakekeeper-vending"
       }
     ]
   }
   ```

4. **Access key** for the user, use case *Application running outside AWS*, written
   to `.secrets/lakekeeper-aws.env` (600, gitignored) with the role ARN:

   ```
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   GRAPHGUARD_VENDING_ROLE_ARN=arn:aws:iam::053849128997:role/graphguard-lakekeeper-vending
   ```

5. `just lakekeeper-init` switches the warehouse to vending (Lakekeeper validates the
   role before saving).
6. **Delete the S5.6b key** of user `graphguard-lakehouse` — *not done: Lubo kept it
   active (2026-11-18), an accepted risk; it is the one key that still reaches `sealed`
   directly on S3.* No job reads it: every job runs without `.secrets/aws.env`
   (verified 2026-11-18 by moving the file away and running the build, reload, SQL,
   training's read and the full test suite).

## Proven by tests

`tests/lakehouse/test_s3_live.py`: the key alone cannot read S3, list buckets or touch
IAM; the role reads/writes/deletes under `lakehouse/` only.
`tests/lakehouse/test_governance_live.py`: trainer's silver key cannot read a `sealed`
or bronze file by path, nor list them; trainer's and reader's keys are read-only; even
builder's key opens only the table it was vended for; bronze comes with no key for
trainer and reader.

## If the key leaks

IAM → user `graphguard-lakekeeper` → Security credentials → **Deactivate**. The key by
itself reads nothing; with the role it reaches `lakehouse/` only, and keys it obtained
expire within the hour. Create a new key, update `.secrets/lakekeeper-aws.env`, run
`just lakekeeper-init` (it re-sends the credential), then `just test`.
