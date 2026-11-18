# Object storage for a single-node open-source lakehouse (as of 2026-11-18)

Scope: where the Parquet/Iceberg files for GraphGuard's lakehouse should live. Options are self-hosted S3-compatible storage on the shared 8-core Hetzner box (Ashburn), or a real cloud bucket. Project limits: about 4GB RAM in total with about 1GB spare, and about 25GB disk. An AWS S3 bucket and IAM user are already planned for model artifacts, and Backblaze B2 is already used for restic backups.

Method note: release versions and dates for GitHub-hosted projects were pulled live from the GitHub REST API on 2026-11-18. Garage releases came from the Deuxfleurs Forgejo API and release page. Docker image tags came from the Docker Hub API. These are primary data. Anything marked "(secondhand)" comes from blogs or aggregators. Anything marked "(training knowledge, not re-verified)" is from my prior knowledge and was not re-fetched.

## MinIO: licence, the 2025-2026 community edition changes, and its state in Nov 2026

### Takeaway
Upstream MinIO community edition is dead. The GitHub repo `minio/minio` is **archived** (AGPL-3.0). Its last release is `RELEASE.2025-10-15T17-29-55Z`. Official community binaries and Docker images stopped in Oct 2025, and unpatched CVEs affect that last release. The only maintained MinIO-derived image is a third-party AGPL fork, `pgsty/minio`, which is now renamed **`pgsty/silo`**. That fork is active as of Nov 2026, but it is a one-vendor community fork. Do not use MinIO for a new portfolio project.

### Cited Findings
- GitHub API (live 2026-11-18): `minio/minio` has `archived: true`, licence `AGPL-3.0`, last push 2026-04-24. The last three releases are `RELEASE.2025-10-15T17-29-55Z` (published 2025-10-16), `RELEASE.2025-09-07T16-13-09Z` and `RELEASE.2025-07-23T15-54-02Z`. — [GitHub API minio/minio](https://api.github.com/repos/minio/minio/releases)
- Timeline from the fork author: licence changed Apache 2.0 to AGPLv3 in 2021-05; **admin console removed from community edition in 2025-05**; **pre-built binary and Docker distribution stopped 2025-10, source only**; "maintenance mode" announced on GitHub 2025-12-03; repo marked "no longer maintained" then archived on 2026-02-12. — [Vonng, "MinIO Is Dead, Long Live MinIO"](https://blog.vonng.com/en/db/minio-resurrect/) (secondhand, written by the fork's maintainer)
- TuxCare dates the archival to **13 February 2026** and says MinIO Inc. ships "no further security fixes" for the community code. It lists CVE-2026-39414, CVE-2026-34204, GHSA-9c4q-hq6p-c237 and GHSA-hv4r-mvr4-25vw as affecting the last community release. MinIO fixed some of these in the commercial **AIStor** product, but the fixes are not backported. TuxCare sells paid "Endless Lifecycle Support" backports. — [TuxCare, MinIO ELS](https://tuxcare.com/blog/minio-els/) (vendor source with a commercial interest)
- Another timeline adds that the repo was "archived again" in Apr 2026 and has stayed locked. This matches the 2026-04-24 last push in the GitHub API. It recommends building from source if you must run community MinIO. — [Glukhov, "MinIO CE in 2026"](https://glukhov.org/data-infrastructure/object-storage/minio-dead/) (secondhand)
- Dates conflict. Most sources give Feb 12/13 2026 for the archival, but one blog gives April 25, 2026 for the read-only state. The GitHub push date of 2026-04-24 suggests there was a second archive or unarchive cycle. — [itsfoss](https://itsfoss.com/news/minio-moves-away-from-open-source/); [Glukhov](https://glukhov.org/data-infrastructure/object-storage/minio-dead/)
- The community fork is published as Docker image `pgsty/minio` and as RPM/DEB packages. It restores the admin console by reverting the `minio/console` submodule, stays under AGPL with a trademark disclaimer, and patches CVE-2025-62506. — [Vonng blog](https://blog.vonng.com/en/db/minio-resurrect/)
- GitHub API (live): `pgsty/minio` now redirects to **`pgsty/silo`** (AGPL-3.0, not archived, pushed 2026-11-17). Its releases are `RELEASE.2026-11-12T00-00-00Z`, `RELEASE.2026-11-09T00-00-00Z` and `RELEASE.2026-10-26T00-00-00Z`. Docker Hub `pgsty/silo` has 54 tags, with the latest amd64 image (~60MB) pushed 2026-11-12. The old `pgsty/minio` Docker repo's newest tag is `RELEASE.2026-08-04T00-00-00Z`. — [GitHub API pgsty/minio→silo](https://api.github.com/repos/pgsty/minio/releases); [Docker Hub pgsty/silo](https://hub.docker.com/r/pgsty/silo)
- Idle RAM: MinIO "typically consumes 500 MB or more" against 50-100MB for Garage (secondhand comparison). — [selfhosting.sh MinIO vs Garage](https://selfhosting.sh/compare/minio-vs-garage/)

### Inferences
- "Can you still pull a maintained image?" Not from MinIO Inc. The old `minio/minio` images are frozen with known CVEs. A maintained image exists only from the pgsty/Pigsty fork, now named Silo. It is credible and active, but it depends on one small maintainer team, and the rename shows it is drifting away from the MinIO name for trademark reasons.
- The licence is not a trap for running the software internally. AGPLv3 matters only if you modify it and serve it to others. The real risk is the governance and maintenance story. A senior reviewer who sees `minio/minio:latest` in a 2026 repo will read it as unpatched software.

### Gaps
- I did not verify the severity or the exact affected versions of CVE-2026-39414 and CVE-2026-34204 against NVD.
- I did not confirm whether Silo fixes those 2026 CVEs. The fork blog only explicitly names CVE-2025-62506.

## Alternatives: Garage, SeaweedFS, Ceph RGW, RustFS, Versity Gateway, Zenko CloudServer

### Takeaway
All the alternatives except Ceph are actively released in Nov 2026 under permissive or copyleft OSS licences. **Garage** (AGPLv3) has the lowest RAM use and offers a one-flag single-node mode. However, it has **no conditional writes, no bucket policies, no versioning and no object lock**. **SeaweedFS** and **RustFS** (Apache-2.0) cover more of the S3 API surface. **Versity Gateway** (Apache-2.0) is a thin S3 front end over a POSIX directory. Ceph RGW is too heavy for a 1GB slice.

### Cited Findings
**Garage (Deuxfleurs, AGPLv3, Rust)**
- Releases: **v2.5.0 (2026-10-24)**, v2.4.1 (2026-09-08), v2.4.0 (2026-09-06), v2.3.0 (2026-04-16), v2.2.0 (2026-01-24). A v1.3.x line is still patched, with v1.3.1 released 2026-01-24. — [Garage releases page](https://garagehq.deuxfleurs.fr/_releases.html); [Forgejo releases API](https://git.deuxfleurs.fr/api/v1/repos/Deuxfleurs/garage/releases)
- v2.3.0 added `garage server --single-node`, which auto-creates a layout so one node works immediately. It also added `--default-access-key` and `--default-bucket`, which create a key and bucket from environment variables. — [Garage v2.3.0 release notes](https://git.deuxfleurs.fr/Deuxfleurs/garage/releases/tag/v2.3.0)
- v2.5.0 is **not downgrade-compatible**. It restricts the lifecycle endpoints to owner keys as a breaking security change, fixes a panic on invalid UTF-8 in URLs, and adds `public_endpoint` and JSON logs. v2.4.0 fixed a reflected XSS on the web endpoint. — [Garage v2.5.0 / v2.4.0 notes](https://git.deuxfleurs.fr/api/v1/repos/Deuxfleurs/garage/releases)
- S3 compatibility page: multipart upload is fully implemented and presigned URLs are implemented. **Bucket policies are missing** (Put/Get/DeleteBucketPolicy). **ACLs are missing**, because Garage has its own per-key-per-bucket permission system. **Versioning is missing**, with GetBucketVersioning stubbed. **Object lock is missing.** — [Garage S3 compatibility](https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/)
- **Conditional PUT (If-None-Match / If-Match) is not supported.** Issue #1326 (2026-02-07) reports that `If-None-Match: *` silently **overwrites** existing objects. It was closed as a duplicate of #1052, "Support conditional writes", which has been open since 2025-05-28. A maintainer wrote (2025-05-29) that this is "not possible with our weak-consistency replication model, it would require a full rearchitecturing". As of 2026-06, there are community proposals for a lock-based design. — [Garage #1326](https://git.deuxfleurs.fr/Deuxfleurs/garage/issues/1326); [Garage #1052](https://git.deuxfleurs.fr/Deuxfleurs/garage/issues/1052)
- Garage-specific workaround in the wild: Proxmox Backup Server needs a `skip-if-none-match-header` quirk flag to run against Garage. — [Proxmox forum](https://forum.proxmox.com/posts/850117/) (secondhand)
- Idle RAM: under 20MB idle and under 200MB in a stress test according to the VSHN ADR. Other reports give 50-100MB or 100-200MB idle (all secondhand or informal). — [VSHN ADR 0050](https://kb.vshn.ch/app-catalog/adr/0050-alternatives-to-minio-for-s3-compatible-object-storage.html); [selfhosting.sh](https://selfhosting.sh/apps/garage/); [PiStack](https://www.pistack.xyz/posts/seaweedfs-vs-minio-vs-garage/)
- The Docker image `dxflrs/garage` is about 28MB for amd64, with builds pushed daily as of 2026-11-18. — [Docker Hub API dxflrs/garage](https://hub.docker.com/r/dxflrs/garage)

**SeaweedFS (Apache-2.0, Go)**
- GitHub API (live): **4.54 released 2026-11-16**, 4.53 on 2026-11-08 and 4.52 on 2026-11-02. It ships roughly weekly and is not archived. — [GitHub API seaweedfs](https://api.github.com/repos/seaweedfs/seaweedfs/releases)
- 4.04 added `weed mini -dir=xxx`, a single-command all-in-one mode for test environments. In 4.24-4.25 and later, IAM users without policies are denied by default and admin endpoint auth was tightened. — [newreleases 4.04](https://newreleases.io/project/github/seaweedfs/seaweedfs/release/4.04); [Cloudron forum](https://forum.cloudron.io/topic/15371/seaweedfs-package-updates) (secondhand summaries)
- RAM is about 256MB minimum according to one comparison table (secondhand). — [PiStack](https://www.pistack.xyz/posts/seaweedfs-vs-minio-vs-garage/)
- Its own S3 gateway supports IAM-style identities and policies (training knowledge, not re-verified). SeaweedFS is a multi-process design (master, volume, filer, s3), which `weed mini` / `weed server -s3` collapses into one process.

**RustFS (Apache-2.0, Rust)**
- **1.0 GA on 2026-09-16** (beta Apr 2026, RC Aug 2026). — [Linuxiac](https://linuxiac.com/rustfs-1-0-s3-compatible-object-storage-reaches-ga/); [RustFS docs](https://docs.rustfs.com/concepts/introduction.html)
- GitHub API (live): **1.0.6 released 2026-11-15**, 1.0.5 on 2026-11-10 and 1.0.4 on 2026-10-25. Licence Apache-2.0. — [GitHub API rustfs](https://api.github.com/repos/rustfs/rustfs/releases)
- It claims versioning, WORM, SSE and replication. Some interop features, such as MinIO on-disk compatibility, are still preview-scoped. One report cites a "serious vulnerability" during its alpha phase. — [Elest.io comparison](https://blog.elest.io/rustfs-vs-seaweedfs-vs-garage-which-minio-alternative-should-you-pick/); [zeli.app](https://zeli.app/ru/story/49709381) (secondhand)
- Earlier 2026 articles still called it "alpha, pilot only". That was true before GA. — [Glukhov](https://glukhov.org/data-infrastructure/object-storage/minio-dead/)

**Versity Gateway (Apache-2.0, Go)**
- GitHub API (live): **v1.11.0 released 2026-11-06**, v1.10.0 on 2026-10-22 and v1.9.0 on 2026-10-13. — [GitHub API versitygw](https://api.github.com/repos/versity/versitygw/releases)
- It is listed among "filesystem-backed options" alongside S3Proxy and rclone. — [Glukhov](https://glukhov.org/data-infrastructure/object-storage/minio-dead/) (secondhand)
- Architecture: a stateless S3 front end that maps buckets and objects to a POSIX directory, with optional IAM accounts. It is a small single binary (training knowledge, not re-verified).

**Zenko CloudServer (Scality, Apache-2.0, Node.js)**
- GitHub API (live): 9.5.6, 9.4.16 and 9.3.31, all released 2026-11-16. Three maintained branches. — [GitHub API scality/cloudserver](https://api.github.com/repos/scality/cloudserver/releases)
- Node.js server backed by a file or in-memory store. It is mostly used as an S3 test target (training knowledge, not re-verified).

**Ceph RGW**
- Framed as the "enterprise option... higher operational complexity". — [Glukhov](https://glukhov.org/data-infrastructure/object-storage/minio-dead/); [Hostzero](https://hostzero.com/articles/minio-maintenance-mode-ceph-rgw-open-object-storage) (secondhand)
- `ceph/ceph` is actively developed (GitHub push on 2026-11-18). — [GitHub API ceph](https://api.github.com/repos/ceph/ceph)

### Inferences
- RAM ranking for a 1GB spare budget: Garage (tens of MB) < Versity (small) < SeaweedFS all-in-one (~256MB) < RustFS (unmeasured, assume hundreds of MB) < MinIO/Silo (~500MB) << Ceph (a MON+MGR+OSD+RGW stack needs multiple GB). Ceph is out.
- Garage's gaps are exactly the "real cloud" features: bucket policies, versioning and conditional writes. It is the lowest-RAM choice but the least AWS-like. Its permissions are per-key-per-bucket read/write/owner, not IAM JSON policies.
- RustFS is the closest thing to a "MinIO replacement" in feature surface, and it is permissively licensed. But it is only 2 months past 1.0 and puts out frequent patch releases (6 in 2 months), so treat it as young.
- SeaweedFS is the mature, permissive, actively released middle ground with IAM-style policies.

### Gaps
- No measured idle RAM figure for RustFS, Versity or CloudServer was found. Measure with `docker stats` under a cap before deciding.
- I did not verify whether SeaweedFS, RustFS or Versity honour `If-None-Match: *` and `If-Match` on PutObject. Test with `aws s3api put-object --if-none-match '*'` twice. The second call must return 412.
- No Garage RAM figure from Deuxfleurs itself was found. All figures are third-party.

## Cloud buckets: AWS S3 (and S3 Tables), Cloudflare R2, Backblaze B2

### Takeaway
At 5-50GB, every cloud option costs well under $2/month. Cloudflare R2 and Backblaze B2 have 10GB free tiers, so the low end costs about $0. AWS S3 is the most "real" option: actual IAM, bucket policies, conditional writes, and S3 Tables as a managed Iceberg catalog. The project already plans an AWS account, bucket and IAM user, so adding a lakehouse prefix or bucket there adds nothing new to manage.

### Cited Findings
- **Cloudflare R2:** Standard storage $0.015/GB-month. Class A $4.50 per million operations, Class B $0.36 per million. **Free tier: 10GB-month, 1M Class A, 10M Class B.** **Egress is free** via the S3 API. — [R2 pricing](https://developers.cloudflare.com/r2/pricing/)
- **R2 Data Catalog**, now renamed **Basin Catalog**: a managed Iceberg REST catalog that supports PyIceberg, DuckDB and Spark, with read-only API tokens for engines. Pricing announced 2026-05-11: catalog operations plus compaction, with a monthly free tier of 1M catalog ops, 10GB of compaction data and 1M compaction objects. As of that changelog, billing was not yet enabled, with 30 days' notice promised. GA status is unconfirmed. — [CF changelog 2026-05-11](https://developers.cloudflare.com/changelog/post/2026-05-11-r2-data-catalog-pricing-announced/); [Basin Catalog changelog](https://developers.cloudflare.com/changelog/product/basin-catalog/); [R2 Data Catalog beta blog](https://blog.cloudflare.com/r2-data-catalog-public-beta/)
- **Backblaze B2:** $6.95/TB-month (~$0.007/GB). First 10GB free. Free egress up to 3x average stored, then $0.01/GB. Class A/B/C calls are free, and Class D calls cost $0.004 per 10k with 2,500 free per day. No minimum file size or minimum duration. — [B2 pricing](https://www.backblaze.com/cloud-storage/pricing)
- **AWS S3 (us-east-1):** GET $0.0004 per 1,000. The first **100GB/month of internet egress is free**, aggregated across services. — [AWS S3 pricing](https://aws.amazon.com/s3/pricing/). The S3 Standard storage rate of ~$0.023/GB-month, PUT at ~$0.005 per 1,000 and egress at ~$0.09/GB beyond the free 100GB did not render on the fetched page (training knowledge, not re-verified).
- **AWS S3 Tables:** storage $0.0265/GB for the first 50TB. PUT $0.005 per 1k, GET $0.0004 per 1k. Monitoring $0.025 per 1,000 objects. Compaction $0.002 per 1,000 objects plus $0.005/GB. — [AWS S3 pricing](https://aws.amazon.com/s3/pricing/)
- AWS S3 has supported conditional writes (`If-None-Match`) since Aug 2024. — [AWS what's new](https://aws.amazon.com/about-aws/whats-new/2024/08/amazon-s3-conditional-writes); [AWS docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.md)

### Inferences
- Cost at 50GB/month: R2 ≈ (50−10)×0.015 = **$0.60**. B2 ≈ (50−10)×0.00695 = **$0.28**. S3 Standard ≈ 50×0.023 = **$1.15** plus small request costs. S3 Tables ≈ 50×0.0265 = $1.33 plus monitoring and compaction. Egress is effectively free for this workload in all four, because S3 keeps it under 100GB/month. At 5GB, R2 and B2 cost $0.
- **Latency (inference, no measured source found):** Hetzner Ashburn and AWS us-east-1 are both in the Northern Virginia data-centre cluster. A bucket in us-east-1 should therefore be only a few milliseconds away. R2 is served from Cloudflare's anycast edge with storage in a chosen region, and should also be low latency from Ashburn. B2's US-East region is in Reston, VA (training knowledge, not re-verified). Iceberg scans are dominated by metadata round trips plus a small number of large Parquet GETs, so a few ms per request is fine at this scale. Local storage will still beat all of them.
- Engine compatibility: PyIceberg (`s3.endpoint` plus fsspec/pyarrow FileIO), DuckDB (`httpfs`/`iceberg` extensions with a `CREATE SECRET` endpoint), Polars (via `object_store`/PyIceberg) and Spark (`S3FileIO`/`s3a`) all accept a custom S3 endpoint plus path-style addressing, so R2, B2, Garage, SeaweedFS and RustFS are all reachable (training knowledge, not re-verified per version). AWS S3 needs no endpoint override at all.
- B2 shares an account with the restic backups. Keeping lakehouse data in a different bucket with a separate application key keeps the blast radius apart. Its S3 API does not support bucket policies in the AWS sense (training knowledge, not re-verified).

### Gaps
- No measured RTT from a Hetzner Ashburn host to us-east-1, R2 or B2 was found. Run `curl -w '%{time_connect} %{time_starttransfer}'` against each endpoint from the box.
- Basin/R2 Data Catalog GA status and whether billing has started as of Nov 2026 are not confirmed.
- I did not re-verify whether B2's S3 API supports conditional writes.

## Does Iceberg need atomic conditional writes from the object store, or does the catalog handle commits? Which stores break which engines?

### Takeaway
With a real catalog (SQL, REST, Hive, Glue, Nessie or Polaris), **the catalog does the atomic commit**: a compare-and-swap of the metadata pointer. The object store only needs to hold immutable files. No rename, no listing consistency and no conditional writes are required. So Garage's missing conditional writes do **not** break Iceberg when you use a SQL or REST catalog. The breakage happens with catalog-less, file-system-style designs, for example Iceberg's Hadoop catalog, or anything that uses `If-None-Match` on the store as its commit primitive.

### Cited Findings
- Iceberg docs: "Commits replace the path of the current table metadata file using an atomic operation." And: "By avoiding file listing and rename operations, Iceberg tables are compatible with any object store." "No consistent listing is required." — [Iceberg Reliability](https://iceberg.apache.org/docs/latest/reliability/)
- A catalog commit is a CAS. It is rejected if the writer's base metadata location does not match the catalog's, and the writer then retries. Hadoop/file-system catalogs instead depend on atomic rename, which object stores lack. — [mintlify mirror of Iceberg reliability concepts](https://www.mintlify.com/apache/iceberg/concepts/reliability); [Datalakehouse Hub, Iceberg commits](https://datalakehousehub.com/blog/2026-04-29-apache-iceberg-masterclass-06-writing-to-iceberg) (secondhand)
- S3 conditional writes (2024) make catalog-less commits possible, for example a small pointer object such as `current.json` updated only when its ETag still matches. Several 2026 posts explore "catalog on object storage". These are proposals and experiments, not the standard Iceberg path. — [Apache Ozone blog 2026-07-08](https://ozone.apache.org/blog/2026/07/08/ozone-s3-conditional-request); [C. Douglas, "Conditional Operations in Object Stores"](https://cdouglas.github.io/posts/2026/01/conditional); [Iceberg dev list](https://go.mail-archive.com/dev@iceberg.apache.org/msg08604.html)
- Garage silently ignores `If-None-Match: *` on PUT and overwrites the object. — [Garage #1326](https://git.deuxfleurs.fr/Deuxfleurs/garage/issues/1326)

### Inferences
- **Safe on any of these stores:** Iceberg plus PyIceberg `SqlCatalog` (SQLite/Postgres), a REST catalog (Lakekeeper, Polaris, Nessie, Gravitino, R2/Basin), Hive or Glue. The store never sees a conditional write.
- **Risky or broken on stores without conditional PUT (Garage, possibly others):** Iceberg `HadoopCatalog` / "file-system tables" on object storage, which is already unsafe on any S3. **Delta Lake** multi-writer on S3: delta-rs/Spark rely either on S3 conditional PUT or on an external DynamoDB lock (training knowledge, not re-verified). Catalog-less "pointer file" designs. Tools like Proxmox Backup Server.
- Silent overwrite is worse than a 501 error. A client that thinks it got create-if-absent semantics from Garage will corrupt state without any error. That is a concrete reason to avoid relying on store-level CAS with Garage at all.
- The project already runs its own Postgres (MLflow, port 5434), so a SQL catalog on Postgres needs no extra RAM.

### Gaps
- I did not find authoritative per-engine documentation, for DuckDB's Iceberg writer or Polars' `write_iceberg`, stating whether they ever issue conditional PUTs when a catalog is configured. My understanding is that they delegate commits to the catalog. Verify per version.
- I did not confirm whether Garage's multipart upload ETags and checksums match what PyIceberg/pyarrow expect. The v2.5.0 notes fix composite checksum suffixes (#1555) and `x-amz-checksum-type` (#1511), which suggests recent SDK checksum changes did cause friction.

## Recommendation: most "real Databricks/Snowflake-like" at the lowest RAM, and safest for a portfolio (no licence traps)

### Takeaway
**Primary recommendation: AWS S3 in us-east-1**, a dedicated lakehouse bucket (or prefix) with its own scoped IAM user, plus an Iceberg SQL or REST catalog on the box. It costs zero RAM on the box, gives the real S3 API (IAM JSON policies, conditional writes, versioning), costs about $1/month at 50GB, adds no new vendor, and has no licence question. **If self-hosting is a goal in itself**, use Garage v2.5 with `--single-node` (AGPLv3, which is fine when run unmodified as an internal service) for the lowest RAM, and accept its missing policies, versioning and conditional writes. Alternatively, use SeaweedFS (Apache-2.0) for a more complete S3/IAM surface at about 256MB. **Avoid MinIO/Silo.**

### Cited Findings
- Upstream MinIO is archived with unpatched CVEs, and the fork has been renamed Silo. — [GitHub API](https://api.github.com/repos/minio/minio); [TuxCare](https://tuxcare.com/blog/minio-els/); [GitHub API pgsty/silo](https://api.github.com/repos/pgsty/minio/releases)
- Garage lacks bucket policies, versioning and object lock. — [Garage S3 compat](https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/). It also lacks conditional writes. — [Garage #1052](https://git.deuxfleurs.fr/Deuxfleurs/garage/issues/1052)
- SeaweedFS, RustFS and Versity are Apache-2.0 and released in Nov 2026. — GitHub API ([seaweedfs](https://api.github.com/repos/seaweedfs/seaweedfs/releases), [rustfs](https://api.github.com/repos/rustfs/rustfs/releases), [versitygw](https://api.github.com/repos/versity/versitygw/releases))
- Cloud costs as cited in the section above. — [R2](https://developers.cloudflare.com/r2/pricing/); [B2](https://www.backblaze.com/cloud-storage/pricing); [AWS S3](https://aws.amazon.com/s3/pricing/)

### Inferences
- "Databricks/Snowflake-like" means: data in a real cloud bucket, access through scoped credentials and policies, and a catalog that owns commits. Only AWS S3 gives all three natively. That includes S3 Tables if a managed catalog is wanted, though that may hide the catalog work a portfolio wants to show. R2 plus Basin Catalog is a close second, with zero egress and a free tier, but its catalog may still be beta.
- **Disk:** a cloud bucket also removes the data from the 25GB disk budget. A self-hosted store's data plus metadata counts against it, and so do Iceberg snapshots and orphan files until compaction or expiry runs.
- **Box safety:** the box's swap is about 99% full, which argues for zero extra resident services. Any self-hosted store must carry a hard `mem_limit` (Garage at 128-256M, SeaweedFS at 384-512M), its own network, and a bind on 127.0.0.1 only, consistent with the GraphGuard CLAUDE.md rules.
- **Portfolio story:** "Iceberg tables on S3 with a Postgres-backed SQL/REST catalog; storage is pluggable (also tested against Garage locally)" shows understanding without depending on a fragile store. Pointing PyIceberg at both S3 and a local Garage container in CI would demonstrate that storage is an abstraction.
- **Leakage-contract note:** Iceberg snapshots and time travel on any of these stores help prove "the graph at time T only used data before T". This works regardless of the backend, because snapshots are catalog metadata.

### Gaps
- No head-to-head benchmark of PyIceberg/DuckDB scan latency on Garage vs SeaweedFS vs AWS S3 from this box exists. It would need to be measured.
- I did not check whether the planned AWS IAM user should be split. A separate lakehouse user is the least-privilege choice and matches the existing "own IAM user scoped to that bucket only" rule.
