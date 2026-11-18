# Open table formats and open lakehouse catalogs (as of 2026-11-18)

Research notes for choosing a table format + catalog for a single-node lakehouse on a shared 8-core box
(~1GB RAM to spare, ~25GB disk, Docker + k3s; engines Polars now, DuckDB maybe, Spark later; 5M rows now, 180M later).

Method note: release versions/dates below were pulled live from the GitHub Releases API on 2026-11-18 (primary
source). Many feature claims come from vendor blogs; these are labelled. Alex Merced (datalakehousehub.com /
amdatalakehouse.substack.com) states he works at Dremio (Polaris-aligned vendor) — treat his posts as vendor-adjacent.

## Q1. Iceberg vs Delta Lake (vs Hudi) in 2026 — is "Iceberg + REST catalog" the interoperable standard?

### Takeaway
Yes. In 2026 every major platform (Snowflake, Databricks, AWS S3 Tables/Glue, Google, Microsoft OneLake) exposes or
consumes Iceberg through the Iceberg REST Catalog protocol, and Iceberg v3 went GA on both Snowflake and Databricks in
May 2026. Delta is still very active (4.4.1, Oct 2026) but its cross-engine story is "Delta that also emits Iceberg
metadata" (UniForm); Hudi is alive but not where the platform interop is.

### Cited Findings
**Latest releases (GitHub Releases API, fetched 2026-11-18)**
- Apache Iceberg (Java): 1.12.0 on 2026-09-30; 1.11.0 on 2026-05-20; 1.10.1 on 2025-12-22 — [GitHub apache/iceberg releases](https://github.com/apache/iceberg/releases). (Apache releases page gives 1.11.0 as 2026-05-19; tag published 05-20 — [iceberg.apache.org/releases](https://iceberg.apache.org/releases/).)
- PyIceberg: 0.12.0 on 2026-09-01; 0.11.0 on 2026-02-10 — [GitHub apache/iceberg-python](https://github.com/apache/iceberg-python/releases).
- Delta Lake: 4.4.1 on 2026-10-05, 4.4.0 on 2026-08-20, 4.3.1 on 2026-07-08 (3.3.3 maintenance line 2026-08-12) — [GitHub delta-io/delta](https://github.com/delta-io/delta/releases). ~9.1k GitHub stars vs Iceberg ~9.4k (same API call).
- Apache Hudi: 1.2.1 on 2026-09-24, 1.1.2 on 2026-10-17, 1.2.0 on 2026-05-23 — [GitHub apache/hudi](https://github.com/apache/hudi/releases).

**Iceberg spec v3 status**
- Iceberg 1.11.0 (May 2026) added a SQL UDF spec, clarified V3 geometry restrictions; blogs describe v3 as production-ready from 1.11 — [Dremio blog (vendor)](https://www.dremio.com/blog/whats-new-in-apache-iceberg-1-11-0/), [Google Open Source Blog](https://opensource.googleblog.com/2026/05/announcing-apache-iceberg-1110.html), [Snowflake engineering blog (vendor)](https://www.snowflake.com/en/blog/engineering/apache-iceberg-1-11-new-features-fixes/).
- Iceberg 1.12.0 (2026-09-30): >800 changes, deeper v3 support (variant, geometry/geography, row lineage, deletion vectors, encryption), dropped Spark 3.4 module — [Dremio blog (vendor)](https://www.dremio.com/blog/apache-iceberg-1-12-0-whats-new-breaking-changes-and-upgrade-guide); [datalakehousehub (vendor-adjacent)](https://datalakehousehub.com/blog/upgrading-apache-iceberg-1-12-0/).
- Spec v4 is still being defined; 1.11 introduced foundational types for it — [Snowflake engineering blog](https://www.snowflake.com/en/blog/engineering/apache-iceberg-1-11-new-features-fixes/).
- Snowflake: Iceberg v3 preview 2026-03-04 — [Snowflake release note](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-04-iceberg-v3-support-preview); reported GA May/June 2026 — [Atlan](https://atlan.com/know/snowflake/apache-iceberg-v3/) (secondary). Atlan also reports Trino was not yet v3-ready as of June 2026 (unverified against Trino docs).
- Databricks: Iceberg v3 GA for Unity Catalog managed Iceberg tables, foreign Iceberg tables and v3 features, release notes dated 2026-05-21 — [Azure Databricks release notes May 2026](https://learn.microsoft.com/en-za/azure/databricks/release-notes/product/2026/may). v3 covers deletion vectors, VARIANT, row lineage; applies to managed Delta+UniForm, managed Iceberg and foreign Iceberg; requires DBR 18.0+; upgrade of managed Iceberg to v3 is one-way — [Databricks docs: Iceberg v3](https://docs.databricks.com/aws/en/iceberg/iceberg-v3).

**Delta 4.x / UniForm**
- Delta 4.3 made UniForm's Iceberg conversion atomic and incremental — [delta.io 4.3 blog](https://delta.io/blog/2026-06-22-delta-4-3-release).
- Delta 4.4.0: delta-iceberg_2.13 supports Spark 4.1, NOT Spark 4.2; atomic UniForm metadata init at table creation; release theme is catalog-managed tables + Delta Kernel + UC Delta APIs — [newreleases.io mirror of 4.4.0 notes](https://newreleases.io/project/github/delta-io/delta/release/v4.4.0), [delta.io 4.4 blog](https://delta.io/blog/2026-08-20-simplifying-your-open-lakehouse-with-the-delta-kernel-and-the-uc-delta-apis).
- On Databricks, v3 on UniForm tables is a per-table setting (`delta.enableIcebergCompatV3`) — [Databricks docs](https://docs.databricks.com/aws/en/iceberg/iceberg-v3).

**What Snowflake and Databricks natively use / interoperate with**
- Snowflake Horizon Catalog is "built on the foundation of Apache Polaris"; Snowflake claims Unity Catalog is fully interoperable only inbound, and that Databricks does not use Iceberg REST to read external catalogs like Horizon (competitor claim, July 2026) — [Snowflake blog (vendor)](https://www.snowflake.com/en/blog/bidirectional-interoperability-snowflake-horizon-databricks/).
- Snowflake: external engines can write to Snowflake-managed Iceberg tables via Horizon's Iceberg REST (Preview 2026-03-16) — [Snowflake release note](https://docs.snowflake.com/en/release-notes/2026/other/2026-03-16-tables-iceberg-query-using-external-query-engine-snowflake-horizon-writes-feature).
- Databricks community answer: Snowflake can read (GA) and write (Public Preview) UC-managed Iceberg tables via UC's Iceberg REST endpoint; Databricks reads Horizon-managed tables via UC Iceberg catalog federation (Public Preview, DBR 16.4 LTS+) — [Databricks community (not official docs)](https://community.databricks.com/t5/technical-blog/iceberg-interoperability-databricks-lt-gt-snowflake/ba-p/128406). Conflicts with Snowflake's claim above.
- AWS: S3 Tables expose an Iceberg REST endpoint `https://s3tables.<REGION>.amazonaws.com/iceberg`, authorized with `s3tables` IAM actions (SigV4) — [AWS S3 docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-open-source.html); Snowflake's S3 Tables Iceberg REST integration GA 2026-08-10 — [Snowflake release note](https://docs.snowflake.com/release-notes/2026/other/2026-08-10-amazon-s3-tables-iceberg-rest-catalog-integration-ga); Glue federates remote Iceberg REST catalogs — [AWS What's New 2026-08](https://aws.amazon.com/about-aws/whats-new/2026/08/aws-glue-catalog-federation-iceberg-govcloud/).
- Google: BigLake reportedly renamed "Lakehouse for Apache Iceberg" (2026-04-20), with its runtime catalog serving an Iceberg REST endpoint — [datalakehousehub (secondary, vendor-adjacent)](https://datalakehousehub.com/blog/iceberg-across-the-hyperscalers); PyIceberg docs ship a "GCP BigLake Metastore Catalog REST" example, plus Unity Catalog, R2 Data Catalog, Lakekeeper, Polaris, Gravitino, OneLake — all as `type: rest` — [PyIceberg configuration docs](https://github.com/apache/iceberg-python/blob/main/mkdocs/docs/configuration.md).
- Seven REST catalogs (Polaris, Lakekeeper, Gravitino, Nessie, Glue, Databricks UC, Snowflake Open Catalog) can be driven by one DuckDB script via OAuth2 + `ACCESS_DELEGATION_MODE 'vended_credentials'`, "substantially yes" for the data plane; caveat: DuckDB lacks REST scan planning, so policy-protected tables (some UC setups) fall outside — [datalakehousehub, 2026-08-24, author works at Dremio](https://datalakehousehub.com/blog/seven-rest-catalogs-one-duckdb-script). No per-catalog test results were published.

### Inferences
- Iceberg + Iceberg REST catalog is the de-facto interop standard in late 2026: it is the one protocol Snowflake, Databricks, AWS, Google and every OSS catalog all speak. Choosing Iceberg is the choice that maps most directly onto "how Snowflake/Databricks work" for interview/portfolio purposes; Databricks' own answer is "Delta inside, Iceberg REST outside".
- Delta's single-node Python story (delta-rs, `pl.write_delta`) is mature, but it buys you a Unity-Catalog-shaped world rather than the cross-vendor one. Hudi is not worth it for this project.
- Write v2 tables by default; v3 features (deletion vectors, variant, row lineage) are not uniformly supported by Polars/PyIceberg/Trino yet (inferred from the per-engine gaps below).

### Gaps
- No official Apache "v3 spec ratified on date X" announcement found; v3 status is inferred from 1.11/1.12 releases and vendor GA dates.
- Did not check Databricks official docs for Tabular-acquisition outcomes (Databricks bought Tabular in June 2024 — training knowledge, not re-verified this session).
- Did not verify Google's official endpoint URL or rename against Google Cloud docs.
- Snowflake Open Catalog (managed Polaris) current status not re-checked.

## Q2. Open catalogs compared (Polaris, Lakekeeper, Nessie, Unity Catalog OSS, Gravitino, PyIceberg SQL catalog)

### Takeaway
All six are actively released and Apache-2.0. Lakekeeper (Rust) is the clear footprint outlier: a ~67MB container
image vs ~414MB for Polaris, ~535MB for Gravitino and ~2.76GB for Unity Catalog OSS. Polaris graduated to an Apache
top-level project (Feb 2026) and is what Snowflake's Horizon builds on. No source publishes measured idle RAM for any
of them — that must be measured on the box.

### Cited Findings
**Release cadence / latest versions (GitHub Releases API, 2026-11-18)**

| Catalog | Lang | Latest | Previous | Licence | Stars |
|---|---|---|---|---|---|
| Apache Polaris | Java (Quarkus) | 1.9.0 (2026-11-14) | 1.8.0 (09-28), 1.7.0 (08-02), 1.6.0 (07-09) | Apache-2.0 | ~2.1k |
| Lakekeeper | Rust | 0.15.1 (2026-11-15) | 0.15.0 (11-06), 0.14.x (Oct), 0.13.x maintained | Apache-2.0 | ~1.5k |
| Project Nessie | Java | 0.110.0 (2026-11-06) | 0.109.0 (10-08), 0.108.8 (09-09) | Apache-2.0 | ~1.5k |
| Unity Catalog OSS | Java | 0.7.0 (2026-10-13) | 0.6.0 (08-20), 0.5.1 (07-18), 0.5.0 (06-18) | Apache-2.0 | ~3.6k |
| Apache Gravitino | Java | 1.3.1 (2026-09-30) | 1.3.0 (06-29), 1.2.1 (05-12) | Apache-2.0 | ~3.4k |
| PyIceberg SQL catalog | Python lib | pyiceberg 0.12.0 (2026-09-01) | 0.11.1 (03-03) | Apache-2.0 | ~1.2k |

Sources: [apache/polaris](https://github.com/apache/polaris/releases), [lakekeeper/lakekeeper](https://github.com/lakekeeper/lakekeeper/releases), [projectnessie/nessie](https://github.com/projectnessie/nessie/releases), [unitycatalog/unitycatalog](https://github.com/unitycatalog/unitycatalog/releases), [apache/gravitino](https://github.com/apache/gravitino/releases), [apache/iceberg-python](https://github.com/apache/iceberg-python/releases). All repos pushed to within the last 24h; none archived.

**Container image size (Docker Hub API, compressed, amd64) — measured by registry, NOT RAM**
- `vakamo/lakekeeper:latest` ~67MB; `apache/polaris:1.9.0` ~417MB; `apache/gravitino-iceberg-rest:1.3.1` ~535MB; `projectnessie/nessie` (Docker Hub tag, stale 0.76.6) ~364MB; `unitycatalog/unitycatalog:v0.7.0` ~2,760MB — [Docker Hub](https://hub.docker.com/r/vakamo/lakekeeper), [Docker Hub apache/polaris](https://hub.docker.com/r/apache/polaris). Relevant to the ~25GB disk budget.

**Apache Polaris**
- Graduated from the Incubator to an Apache TLP in Feb 2026 — [datalakehousehub (vendor-adjacent)](https://datalakehousehub.com/blog/seven-rest-catalogs-one-duckdb-script); 1.3.0 was the last "-incubating" release (2026-01-16) — [polaris.apache.org downloads 1.3.0](https://polaris.apache.org/downloads/1.3.0).
- Releases ship server + admin Docker images (`apache/polaris:1.9.0`, `apache/polaris-admin:1.9.0`) and a Helm chart — [1.9.0 release notes](https://github.com/apache/polaris/releases/tag/apache-polaris-1.9.0).
- Persistence: `in-memory` (Helm default), `relational-jdbc` (PostgreSQL, CockroachDB), `nosql` (MongoDB or InMemory) — [Polaris Helm values.yaml](https://github.com/apache/polaris/blob/main/helm/polaris/values.yaml); CockroachDB added in 1.4 — [Snowflake blog (vendor)](https://www.snowflake.com/en/blog/engineering/apache-polaris-1-4-release/).
- 1.4: persist Iceberg ScanReports/CommitReports to DB; multi-tenancy — [Snowflake blog](https://www.snowflake.com/en/blog/engineering/apache-polaris-1-4-release/). 1.6: Spark 4.0 client — [polaris.apache.org 1.6.0](https://polaris.apache.org/downloads/1.6.0/). 1.7: correctness focus — [datalakehousehub](https://datalakehousehub.com/blog/apache-polaris-1-7-0). 1.8: bootstrap no longer creates DB schema (breaking) — [Dremio blog (vendor)](https://www.dremio.com/blog/apache-polaris-1-8-0-whats-new-breaking-changes-and-upgrade-guide/).
- RBAC model: principals -> principal roles -> catalog roles -> privileges (training knowledge; consistent with the "catalog, principal, and role bootstrap" described in [datalakehousehub](https://datalakehousehub.com/blog/seven-rest-catalogs-one-duckdb-script)). Credential vending for S3/GCS/Azure confirmed indirectly by the 2026 CVEs below.
- Memory: JVM; container heap defaults to a share of the container limit (JAVA_MAX_MEM_RATIO, default ceiling 80%), no effect without a limit; ParallelGC default; heap can be fixed via `JAVA_OPTS_APPEND="-Xmx..."` — [Polaris configuration docs](https://polaris.apache.org/releases/1.7.0/configuration/configuring-polaris/). No published idle RSS figure found. Helm `resources: {}` default (only a commented 128Mi template example — not a recommendation).

**Lakekeeper**
- Rust Iceberg REST catalog; Postgres backend; OpenFGA authz in OSS; Lakekeeper+ enterprise adds predefined Cedar policies (on by default in Lakekeeper+ 0.14.0) — [Lakekeeper enterprise release notes](https://docs.lakekeeper.io/about/enterprise-release-notes/), [Lakekeeper release notes](https://docs.lakekeeper.io/about/release-notes/).
- 0.15.0 (2026-11-06): new OpenFGA `write` privilege (data/schema changes without drop/rename); cross-instance cache invalidation via shared Postgres; `serve` requires migrated DB; S3-compatible STS that needs a principal; Google official Rust SDK for GCS — [release notes](https://docs.lakekeeper.io/about/release-notes/).
- 0.14.x: Grants API with OpenFGA; `LAKEKEEPER__PG_SCHEMA` to keep tables in a non-public schema; remote signing aligned with latest Iceberg REST spec and fixed for Iceberg 1.12; table registration honours vended-credentials vs remote-signing access mode; accepts v3 `unknown` type — [release notes](https://docs.lakekeeper.io/about/release-notes/).
- Credential vending: S3 STS vended credentials and S3 remote signing, GCS token vending — [release notes](https://docs.lakekeeper.io/about/release-notes/).
- Very frequent patch cadence with RustSec dependency bumps in 0.14.1–0.15.1 (e.g. RUSTSEC-2026-0538, -0441, -0381..0387, -0338..0349) — [release notes](https://docs.lakekeeper.io/about/release-notes/).
- Footprint: "small footprint" is an author claim, not a measurement — [andreabozzo blog](https://andreabozzo.pages.dev/en/posts/lakekeeper-blog). No published MB figure found. Helm `resources: {}` default — [lakekeeper-charts values.yaml](https://github.com/lakekeeper/lakekeeper-charts/blob/main/charts/lakekeeper/values.yaml).

**Project Nessie**
- Still releasing roughly monthly (0.110.0 on 2026-11-06) — [GitHub](https://github.com/projectnessie/nessie/releases).
- Maintained by a small group with Dremio roots; Dremio's Sept 2026 post hints small-contributor projects may be in maintenance mode — [Dremio blog (vendor)](https://www.dremio.com/blog/choosing-an-apache-iceberg-catalog-polaris-gravitino-unity-lakekeeper-and-more). Dremio said in 2024 it intended to fold Nessie capabilities into Polaris — [BigDATAwire 2024](https://www.bigdatawire.com/2024/10/29/dremio-goes-hybrid-with-nessie-based-metadata-catalog); no later confirmation found.
- Nessie is in the seven-catalog Iceberg REST list — [datalakehousehub](https://datalakehousehub.com/blog/seven-rest-catalogs-one-duckdb-script).

**Unity Catalog OSS**
- LF AI & Data sandbox project; supports Iceberg REST and HMS interfaces; README warns APIs are evolving and not stable — [GitHub unitycatalog](https://github.com/unitycatalog/unitycatalog).
- 0.7.0 (2026-10-13): "Full Apache Iceberg table support" — any Iceberg REST engine can create/write/read/rename/drop Iceberg tables (endpoint `/api/2.1/unity-catalog/iceberg`); managed storage cleanup; Spark 4.0/4.1/4.2 connectors; Docker image `unitycatalog/unitycatalog:v0.7.0` — [UC 0.7.0 release notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.7.0). (Before 0.7, Iceberg REST was read-oriented — inferred from the release wording "extends".)

**Apache Gravitino**
- Metadata "metalake" federation layer with an Iceberg REST service image (`apache/gravitino-iceberg-rest`); latest 1.3.1 (2026-09-30) — [GitHub](https://github.com/apache/gravitino/releases). A guide says Polaris has a lighter JVM footprint than Gravitino (qualitative only) — [pistack.xyz guide 2026-10-21](https://www.pistack.xyz/posts/2026-10-21-iceberg-rest-catalogs-polaris-lakekeeper-gravitino-guide/).

**PyIceberg SQL catalog (no server)**
- `type: sql`, backed by PostgreSQL or SQLite via SQLAlchemy; docs warn "SQLite is not built for concurrency, you should use this catalog for exploratory or development purposes"; also an in-memory catalog — [PyIceberg configuration docs](https://github.com/apache/iceberg-python/blob/main/mkdocs/docs/configuration.md). No REST, no RBAC, no credential vending (inherent to the design: it is a library, not a service).

### Inferences
- Rough RAM expectation (ESTIMATED, not measured): a Rust Lakekeeper process is likely tens of MB RSS idle; Polaris/Nessie/Gravitino/UC are JVM services and realistically need a few hundred MB each once heap + metaspace + threads are counted, unless heap is capped hard (`-Xmx256m`-class). This must be verified with `docker stats` / RSS on the box before committing.
- Lakekeeper's full "platform" setup adds containers: Postgres (GraphGuard already runs its own MLflow Postgres on 5434 — a separate database there would avoid a new Postgres), OpenFGA (only if you want RBAC), and S3-compatible object storage with STS (only if you want credential vending).
- Unity Catalog OSS's 2.76GB image alone is >10% of the 25GB disk budget; poor fit.
- Nessie's git-like branching is unique but the project's future looks less certain than Polaris/Lakekeeper; Iceberg's own branches/tags cover much of the "branch" use case.

### Gaps
- No measured idle or under-load RAM figures exist publicly for any of these catalogs (searched explicitly). Measuring was not done here because GraphGuard rules require asking before starting any container.
- OpenFGA's own RAM footprint not researched.
- Lakekeeper: did not confirm whether any non-Postgres backend exists in 0.15 (release notes only reference Postgres).
- Nessie's current container image location (Docker Hub tags appear stale at 0.76.6; newer images are likely on GHCR/Quay) not verified.
- Gravitino and Nessie RBAC/credential-vending specifics not verified this session.

## Q3. Engine compatibility (Polars, DuckDB, PyIceberg, Spark 4, Trino)

### Takeaway
Any Iceberg REST catalog works with all of these, because they all speak the same REST protocol. Polars reads natively
and writes through PyIceberg (marked unstable); DuckDB has real REST read/write including MERGE since 1.5.3;
Spark 4.0/4.1 is supported by Iceberg runtime 1.11/1.12 and by Unity Catalog / Polaris clients.

### Cited Findings
- Polars (latest py-2.1.0, 2026-10-25; 2.0.0 on 2026-10-06 — [GitHub pola-rs/polars](https://github.com/pola-rs/polars/releases)): `scan_iceberg` takes a path or PyIceberg Table, has `reader_override` native vs pyiceberg, and a `catalog` parameter accepting a PyIceberg catalog or `IcebergCatalogConfig` — [Polars API docs](https://docs.pola.rs/api/python/dev/reference/api/polars.scan_iceberg.html).
- Polars write: `LazyFrame.sink_iceberg(target, mode=append|overwrite, schema_mode=merge|overwrite, overwrite_filter, partition_overwrite='dynamic', create_if_not_exists, catalog=..., ...)` and `DataFrame.write_iceberg(target, mode)` (which calls PyIceberg `table.append/overwrite`); both documented as **unstable** — [polars lazyframe/frame.py source](https://github.com/pola-rs/polars/blob/main/py-polars/src/polars/lazyframe/frame.py), [dataframe/frame.py](https://github.com/pola-rs/polars/blob/main/py-polars/src/polars/dataframe/frame.py).
- DuckDB iceberg extension: writes require an attached REST catalog (`iceberg_scan` path-based is read-only); supports CREATE/DROP SCHEMA/TABLE, INSERT, UPDATE, DELETE, MERGE INTO, ALTER TABLE; merge-on-read positional deletes only (no copy-on-write); storage backends S3, S3 Tables, GCS only; GEOGRAPHY/UNKNOWN planned for v2.0 — [DuckDB docs: writing](https://duckdb.org/docs/current/core_extensions/iceberg/writing). Write support started in 1.4 LTS (Sept 2025); 1.5.3 (May 2026) added MERGE INTO, ALTER TABLE, partition transforms, v3 incl. deletion vectors — [DuckDB blog 2026-05-29](https://duckdb.org/2026/05/29/new-iceberg-features). Extension still labelled experimental; no REST scan planning — [datalakehousehub](https://datalakehousehub.com/blog/seven-rest-catalogs-one-duckdb-script).
- PyIceberg 0.12.0 REST client supports OAuth2, SigV4 and pluggable AuthManager, with documented examples for Glue, UC, R2, Lakekeeper, Polaris, Gravitino, BigLake, OneLake — [PyIceberg configuration docs](https://github.com/apache/iceberg-python/blob/main/mkdocs/docs/configuration.md).
- Spark 4: UC 0.7.0 example uses `iceberg-spark-runtime-4.0_2.13:1.11.0` / `4.1_2.13:1.11.0` against UC's Iceberg REST — [UC 0.7.0 notes](https://github.com/unitycatalog/unitycatalog/releases/tag/v0.7.0); Polaris 1.6 added a Spark 4.0 client — [polaris.apache.org 1.6.0](https://polaris.apache.org/downloads/1.6.0/); Iceberg 1.11 added Spark 4.1 support — [machineherald summary (secondary)](https://machineherald-io.pages.dev/article/2026-05/21-apache-iceberg-1110-ships-with-full-encryption-spark-41-support-and-deletion-vectors-for-flink). Delta-iceberg 4.4 not compatible with Spark 4.2 — [Delta 4.4.0 notes](https://newreleases.io/project/github/delta-io/delta/release/v4.4.0).
- Trino: S3 Tables can be queried from OSS Trino via Iceberg REST — [AWS Storage blog](https://aws.amazon.com/blogs/storage/query-amazon-s3-tables-from-open-source-trino-using-apache-iceberg-rest-endpoint); reported not v3-ready as of June 2026 — [Atlan (secondary)](https://atlan.com/know/snowflake/apache-iceberg-v3/).

### Inferences
- DuckDB's storage list (S3/S3 Tables/GCS) means a local-filesystem warehouse won't work with DuckDB's REST write path; a single-box setup needs an S3-compatible store (MinIO/Garage/RustFS-class) for the DuckDB path and for credential vending.
- Polars + PyIceberg alone can work against a local `file://` warehouse with the SQL catalog, which is the zero-extra-RAM fallback.
- At 5M→180M rows, the catalog is not the bottleneck (it only serves metadata); the engine and object store are.

### Gaps
- Did not verify per-catalog Polars write results end-to-end; Polars' sink path goes through PyIceberg commits, so any catalog PyIceberg supports should work (inference).
- Trino version/v3 status not checked against Trino release notes.

## Q4. Security: CVEs / auth issues 2025–2026

### Takeaway
Polaris had four critical-rated CVEs (May 2026, fixed in 1.4.1) all around credential vending/location validation;
Unity Catalog OSS had a critical JWT-issuer bypass (Mar 2026); Nessie had a high-severity S3 remote-signing bypass
(Nov 2026). Lakekeeper shows only dependency RustSec bumps, no project-level GHSA. Credential vending is the
recurring attack surface across catalogs.

### Cited Findings
- Apache Polaris, all published 2026-05-04, fixed in 1.4.1, CVSS ~9.4–9.9, require an authenticated user:
  - CVE-2026-42809: staged table creation can mint broad temporary storage credentials for unvalidated locations — [vulert](https://vulert.com/vuln-db/CVE-2026-42809), [ZeroPath analysis](https://researcher.branch.zeropath.com/blog/cve-2026-42809-apache-polaris-credential-vending-bypass).
  - CVE-2026-42810: literal `*` in namespace/table names enables cross-table metadata access/modify — [vulert](https://vulert.com/vuln-db/CVE-2026-42810).
  - CVE-2026-42811: CEL injection widens GCS credential scope to whole bucket — [ZeroPath](https://researcher.branch.zeropath.com/blog/cve-2026-42811-apache-polaris-gcs-cel-injection).
  - CVE-2026-42812: `write.metadata.path` bypasses location validation when `allow.unstructured.table.location=true` — [vulert](https://vulert.com/vuln-db/CVE-2026-42812).
  - Dremio shipped a downstream bulletin — [Dremio Security Bulletin 2026-05-03-01](https://docs.dremio.com/current/reference/bulletins/2026-05-03-01).
  - (Aggregator sources; not cross-checked against NVD/Apache announce list.)
- Unity Catalog OSS: CVE-2026-27478 / GHSA-qqcj-rghw-829x, critical, 2026-03-11, "JWT Issuer Validation Bypass Allows Complete User Impersonation" — [GitHub advisory](https://github.com/unitycatalog/unitycatalog/security/advisories/GHSA-qqcj-rghw-829x).
- Project Nessie: GHSA-5g6c-2r9x-gq46, high, 2026-11-06, "S3 remote-signing authorization bypass through sibling-prefix matching" (no CVE yet); CVE-2026-62372 / GHSA-64hg-f7v5-9gv3, medium, 2026-07-28, diff operation content checks applied to wrong side — [Nessie security advisories](https://github.com/projectnessie/nessie/security/advisories).
- Lakekeeper: no GitHub security advisories returned by the API; release notes list dependency advisories fixed (rustls, quinn-proto, webpki, tokio — RUSTSEC-2026-0338..0349, -0381..0387, -0441, -0538) and stricter remote signing in 0.14.1 — [Lakekeeper release notes](https://docs.lakekeeper.io/about/release-notes/).
- Gravitino, PyIceberg: GitHub security-advisories API returned none (Apache projects often publish via the Apache security list instead, so absence is weak evidence).

### Inferences
- Whatever catalog is chosen: pin to the latest patch, bind it to localhost / the internal Docker network only (never public), and keep it off the shared host network — consistent with the box's S5.8 lockdown work.
- Polaris's absence of GHSAs reflects Apache's CVE process, not absence of bugs; Polaris ≥1.4.1 required (1.9.0 current).

### Gaps
- Did not check the Apache security mailing list for Gravitino or Iceberg CVEs in 2025–2026.
- Lakekeeper's OpenFGA dependency CVEs not researched.

## Q5. Recommendation for one node with ~1GB to spare

### Takeaway
Iceberg tables + Lakekeeper as the REST catalog, backed by a database on GraphGuard's existing Postgres, is the most
"real platform" (Iceberg REST, OpenFGA RBAC, STS credential vending / remote signing) per MB of RAM. Polaris is the
best-known name and the closest to Snowflake's actual stack, but it is a JVM service — choose it only if measured RSS
with a capped heap fits. Keep PyIceberg's SQL catalog as the zero-RAM fallback.

### Cited Findings
- Lakekeeper image ~67MB vs Polaris ~417MB / Gravitino ~535MB / UC ~2.76GB (Docker Hub API) — [Docker Hub](https://hub.docker.com/r/vakamo/lakekeeper).
- Lakekeeper OSS has OpenFGA authz, Grants API, S3 STS vending, remote signing, Postgres multi-instance cache sync, non-public PG schema support — [Lakekeeper release notes](https://docs.lakekeeper.io/about/release-notes/).
- Polaris is the base of Snowflake Horizon and Snowflake Open Catalog, Apache TLP since Feb 2026 — [Snowflake blog](https://www.snowflake.com/en/blog/bidirectional-interoperability-snowflake-horizon-databricks/), [datalakehousehub](https://datalakehousehub.com/blog/seven-rest-catalogs-one-duckdb-script).
- Polaris heap is controllable (JAVA_MAX_MEM_RATIO / `-Xmx`) — [Polaris configuration docs](https://polaris.apache.org/releases/1.7.0/configuration/configuring-polaris/).
- PyIceberg SQL catalog on Postgres needs no server — [PyIceberg docs](https://github.com/apache/iceberg-python/blob/main/mkdocs/docs/configuration.md).

### Inferences
- Suggested stack (ESTIMATE, to be measured): Iceberg v2 tables, Lakekeeper container with a hard memory cap (start ~128–256M), its DB in GraphGuard's existing MLflow Postgres (separate database/schema via `LAKEKEEPER__PG_SCHEMA`), an S3-compatible object store only when credential vending/DuckDB writes are needed, and OpenFGA added last only if RBAC is to be demonstrated. Engines connect via `type: rest` (PyIceberg/Polars) or `ATTACH ... (TYPE iceberg)` (DuckDB) or `iceberg-spark-runtime` `type=rest` (Spark), so swapping to Polaris later is a config change, not a rewrite.
- Interview story: "Iceberg + REST catalog is exactly the interface Snowflake Horizon (Polaris), Databricks UC, and AWS S3 Tables expose; I ran the OSS equivalent on one node with RBAC and vended credentials." That is accurate per the sources above.
- Before committing, measure: `docker stats --no-stream` idle RSS for Lakekeeper vs Polaris (heap-capped) under a 5M-row Polars append + DuckDB MERGE, per the box's "measure, don't assume" practice.

### Gaps
- No measured RAM evidence anywhere (all footprint conclusions are inferred from language runtime + image size).
- RAM/disk of the S3-compatible store (MinIO/Garage/RustFS) and of OpenFGA not researched — outside this assignment's scope but needed for the total budget.
