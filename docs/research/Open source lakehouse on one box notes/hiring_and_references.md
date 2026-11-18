# Lakehouse skills: hiring demand (2026) and single-node reference architectures

Research date: 2026-11-18. Method note up front: the posting sample was pulled straight from the public Greenhouse, Ashby and Lever job-board APIs (full posting text) for about 90 fintech/payments/AML-vendor and tech companies. Only roles whose title matched data engineer / analytics engineer / data platform / data infrastructure / ML platform / ML infra / ML engineer / feature were kept. Manager, intern, sales and security titles were dropped, and so was Databricks itself because it is a vendor. Duplicate company+title pairs were removed. Result: **N = 139 postings** (103 fintech/payments/crypto/AML, 36 tech). 129 of 139 were first published in 2026; median first-publish date 2026-09-21, range 2023-09-26 to 2026-11-17. This is a snapshot of postings open on 2026-11-18, not a random sample of the market. Keyword matching is regex over the full text. The full list with URLs is in the appendix at the end of this file.

## Q1. What do 2026 data-engineering / ML-platform / analytics-engineering postings actually ask for?

### Takeaway
The day-to-day stack hiring managers ask for is Spark (39%) + Airflow (37%) + Kafka (25%) + a warehouse (Snowflake 24%, Databricks 15%) + dbt (20%), with data quality, governance and lineage showing up as capabilities. Iceberg appears in only 7% of postings (10/139). All 10 are data-platform / data-infrastructure roles, mostly senior or staff. **Zero of the 79 ML-engineer and ML-platform postings mention Iceberg or "lakehouse".** Polaris, Hudi, SQLMesh, DuckDB and "medallion" appear in 0 postings.

### Cited Findings

**Keyword counts, N=139** (source: the postings in the appendix; each count is the number of postings that mention the term at least once).
"Req-zone" means the first mention comes before the first "preferred / nice to have / bonus / a plus / ideally" phrase in the posting. "Pref-zone" means it only comes after one. This is a rough heuristic: some postings list the stack in an "about the team" paragraph rather than under requirements.

| Term | Postings | % of 139 | Fintech (103) | Tech (36) | Req-zone | Pref-zone |
|---|---|---|---|---|---|---|
| Spark / PySpark | 54 | 38.8 | 41 | 13 | 44 | 10 |
| Airflow | 51 | 36.7 | 38 | 13 | 43 | 8 |
| Kafka | 34 | 24.5 | 28 | 6 | 27 | 7 |
| Snowflake | 33 | 23.7 | 30 | 3 | 29 | 4 |
| data quality | 30 | 21.6 | 24 | 6 | 28 | 2 |
| dbt | 28 | 20.1 | 25 | 3 | 22 | 6 |
| Kubernetes | 22 | 15.8 | 18 | 4 | 18 | 4 |
| Databricks | 21 | 15.1 | 20 | 1 | 18 | 3 |
| Flink | 17 | 12.2 | 13 | 4 | 15 | 2 |
| Trino / Presto / Starburst | 15 | 10.8 | 14 | 1 | 13 | 2 |
| lineage | 14 | 10.1 | 12 | 2 | 14 | 0 |
| BigQuery | 13 | 9.4 | 12 | 1 | 10 | 3 |
| Terraform | 13 | 9.4 | 11 | 2 | 10 | 3 |
| feature store / feature platform | 11 | 7.9 | 8 | 3 | 7 | 4 |
| **Iceberg** | **10** | **7.2** | 8 | 2 | 7 | 3 |
| lakehouse | 8 | 5.8 | 8 | 0 | 6 | 2 |
| Redshift | 8 | 5.8 | 7 | 1 | 7 | 1 |
| S3 | 6 | 4.3 | 4 | 2 | 6 | 0 |
| data lake | 6 | 4.3 | 5 | 1 | 6 | 0 |
| data contracts | 6 | 4.3 | 6 | 0 | 6 | 0 |
| Ray | 6 | 4.3 | 5 | 1 | 4 | 2 |
| Hive | 5 | 3.6 | 2 | 3 | 4 | 1 |
| Delta Lake | 4 | 2.9 | 4 | 0 | 4 | 0 |
| MLflow | 4 | 2.9 | 4 | 0 | 2 | 2 |
| Dagster | 4 | 2.9 | 1 | 3 | 4 | 0 |
| Polars | 1 | 0.7 | 0 | 1 | 0 | 1 |
| Feast / Tecton | 1 | 0.7 | 1 | 0 | 1 | 0 |
| Unity Catalog | 1 | 0.7 | 1 | 0 | 1 | 0 |
| Parquet | 1 | 0.7 | 0 | 1 | 0 | 1 |
| Hudi, Polaris, SQLMesh, DuckDB, medallion | 0 | 0 | 0 | 0 | 0 | 0 |

(A loose "catalog/governance" match hit 34 postings, but it mostly catches the generic word "governance", so it is not reported as a skill count.)

**By role type** (title-based classification):
- Data engineer / data platform (n=54): Airflow 38, Spark 32, Kafka 25, Snowflake 24, data quality 23, dbt 20, Databricks 16, Flink 15, lineage 11, **Iceberg 10, lakehouse 7**.
- ML engineer (n=58): Spark 20, Airflow 10, Kubernetes 8, Kafka 8, feature store 6, MLflow 4, Ray 4, **Iceberg 0, lakehouse 0**.
- ML platform (n=21): Trino/Presto 8, Kubernetes 6, feature store 3, Ray 2, Spark 2, **Iceberg 0, lakehouse 0**.
- Analytics engineer (n=6, small): dbt 6, Snowflake 5, lineage 2, lakehouse 1, data contracts 1.

**The 10 Iceberg postings, with exact wording:**
- Stripe, *Staff Software Engineer, Risk Data Engineering* (2026-08-06), a fraud/risk role. Iceberg is listed under "Preferred qualifications": "Our stack is made up of Iceberg, Kafka, Change Data Capture, Flink, Spark, Airflow, Hive Metastore, Pinot, Trino, and AWS Cloud" — [Stripe](https://stripe.com/jobs/search?gh_jid=8112043)
- Stripe, *Senior Staff Engineer, Big Data Infrastructure* (2026-11-04): "Data Orchestration (Airflow) Batch Compute (Spark, Celeborn) Data Lake (Iceberg, Hive, S3, Azure Blob Storage)… over 2,000 engineers and 600+ internal teams" — [Stripe](https://stripe.com/jobs/search?gh_jid=8317306)
- TRM Labs (blockchain AML), *Senior* and *Staff Software Engineer, Data Platform* (2026-09-23): "In-depth experience with data stores and engines such as Iceberg, Trino, BigQuery, and StarRocks, and Citus" — [TRM Senior](https://jobs.ashbyhq.com/trm-labs/990a102e-3596-49ac-b527-9addc25771c4), [TRM Staff](https://jobs.ashbyhq.com/trm-labs/e989a9b7-103d-46fb-9787-7f81c8f361c4)
- Block, *Software Engineer, Data Platform* (2026-08-28): "Data platforms: Snowflake, Databricks, Apache Iceberg" — [Block](http://block.xyz/careers/jobs/5381381008?gh_jid=5381381008)
- Toast, *Staff Software Engineer - Data Platform* (2026-07-30): owns "a cloud-native data lakehouse, feature serving for ML-driven product experiences" — [Toast](https://careers.toasttab.com/jobs?gh_jid=8068781)
- Upstart, *Senior Data Platform Engineer* (2026-09-29): team "owns Upstart's Lakehouse (Databricks) infrastructure… the platform that Machine Learning, Analytics, and Software Engineering teams use" (Iceberg and Delta both mentioned) — [Upstart](https://careers.upstart.com/jobs?gh_jid=8214129)
- Airbnb, *Senior Data Engineer Tech Foundations* (2026-11-17): "Familiarity with… modern table formats such as Apache Iceberg is also valuable" (preferred), next to "financial and payments datasets is a plus" — [Airbnb](https://careers.airbnb.com/positions/8396777?gh_jid=8396777)
- SoFi, *Principal Software Engineer, Data Platform — Data Trust & AI Context* (2026-10-23): "technical direction for data contracts, metadata and catalog modernization, lineage, data quality, privacy, and access controls" — [SoFi](https://sofi.com/careers/job/8037984003?gh_jid=8037984003)
- OpenAI, *Software Engineer, Data Infrastructure* (first published 2024-06-27, still open): "data lakes and metadata systems on Iceberg and Delta" — [OpenAI](https://jobs.ashbyhq.com/openai/f763c6b3-5167-4a67-b691-4c3fa2c44156)

**Capability language, which carries as much weight as tool names:**
- Chime, *Senior SWE, Data Platform*: "design data contracts… Architect and enforce data lineage" — [Chime](https://boards.greenhouse.io/chime/jobs/8840193002?gh_jid=8840193002)
- Chime, *Senior SWE, ML Platform*: "integrate ML or foundation models through reliable APIs, workflows, and data contracts" — [Chime](https://boards.greenhouse.io/chime/jobs/8765684002?gh_jid=8765684002)
- Coinbase, *Staff Analytics Engineer*: "data quality and reconciliation frameworks (tests, monitoring, alerting, SLAs)… Drive data contracts with upstream engineering teams" — [Coinbase](https://www.coinbase.com/careers/positions/8047150?gh_jid=8047150)
- SoFi, *Senior SWE, Data Platform*: "Data Governance enforcement and tooling (Data Contracts, RBAC mechanisms)" — [SoFi](https://sofi.com/careers/job/8207529003?gh_jid=8207529003)
- Block, *Staff Data Engineer, AIM*: "Partner with AIM's ML engineers to establish the datasets, features, and data contracts" — [Block](http://block.xyz/careers/jobs/5473605008?gh_jid=5473605008)
- Plaid, *Staff SWE - Data Infrastructure*: "domain experts in Data Warehouse, Data Lakehouse, Spark, Workflow Orchestration, and Streaming" — [Plaid](https://jobs.ashbyhq.com/plaid/127d31ff-3a16-488b-ba01-6e87dbb96957)

**Bank and consultancy postings found through search** (not in the API sample, which has no Workday boards):
- Citi, *Lead Data Engineer (VP)*, dated 2026-07-30, asks for Apache Iceberg, Flink and Kafka — [Citi](https://jobs.citi.com/job/jersey-city/lead-data-engineer-vice-president/287/98511094016)
- NTT DATA, Bangalore, March 2026: a Hadoop-to-Iceberg migration engagement — [NTT DATA](https://careers-inc.nttdata.com/job/Bangalore-Data-Engineer-Iceberg-Migration-KA/1376900600/)

### Inferences
- For the candidate's target (ML / ML-platform, fraud/AML), "Iceberg" as a keyword buys almost nothing: 0 of 79 ML-titled postings mention it. Spark and Airflow are where the volume is, which matches the earlier 58-posting fraud/ML study (Spark 41% there, 38.8% here).
- Iceberg does carry signal at the senior/staff data-platform level at payments and AML firms: Stripe Risk, TRM Labs, Block, Toast. Stripe's Risk Data Engineering stack (Iceberg + Kafka/CDC + Flink + Spark + Airflow + Trino) is the closest public match to a fraud-feature lakehouse, and it is a useful "this is what real looks like" reference.
- The capability terms (data contracts, lineage, data quality, RBAC/access control, reconciliation, SLAs) cluster in the same senior postings. That supports building the lakehouse around those capabilities rather than around a list of tools.
- A Trino + Iceberg + Airflow + dbt combination maps onto the most-requested tools, while Polaris/Lakekeeper/Nessie are implementation details that no posting names.

### Gaps
- No Workday boards (JPMorgan, Capital One, Amex, Wells Fargo) are in the API sample, so large banks are under-represented. Only Citi and NTT DATA were seen through search.
- The required vs preferred split is a text-position heuristic, not a hand label. Treat it as directional.
- Single snapshot (2026-11-18). There is no time series from this sample, so it says nothing about whether Iceberg is rising.
- The selected set over-represents a few companies (Coinbase 14, Airbnb 14, TRM Labs 14, OpenAI 10, Airwallex 10).

## Q2. Is Iceberg a rising hiring signal in 2026?

### Takeaway
Adoption interest is real but production use is still a minority, and job-ad data is noisy and contradictory. The best neutral survey (dbt Labs, n=363) has **9% using Iceberg in production** and 68% with no plans. The Joe Reis practitioner survey (n≈1,101) puts lakehouses as the primary environment for about 27% versus 44% for cloud warehouses. Higher adoption numbers come from vendor-run surveys.

### Cited Findings
- **dbt Labs 2026 State of Analytics Engineering** (vendor, but its business does not depend on any one table format; n=363; collected 2025-12-05 to 2026-02-01; 73% practitioners): 9% use Iceberg in production, 6% plan to, 12% are in proof-of-concept (27% engaged in total), 68% have no current plans. Top motivation is multi-engine compatibility (22%); top barriers are knowledge gaps (27%) and unclear use cases (27%). The report calls Iceberg a "strategic, forward-looking investment". Trust rated important rose from 66% to 83%. Ambiguous data ownership is cited by 41%. — [dbt Labs](https://www.getdbt.com/resources/state-of-analytics-engineering-2026)
- **Joe Reis / Practical Data Community 2026 State of Data Engineering** (independent practitioner community; around 1,101 respondents, and the page also shows 1,001, an inconsistency): about 44% (43.8%) say their primary environment is a cloud data warehouse, about 27% (26.8%) a lakehouse. No separate Iceberg share was reported. — [Reis survey](https://joereis.github.io/practical_data_data_eng_survey/); [Reis substack](https://joereis.substack.com/p/the-2026-state-of-data-engineering); [secondary analysis](https://stats.conversationalgeek.com/analysis/practical-data-community-2026-data-architecture)
- **UK job ads (ITJobsWatch):** contract ads citing Apache Iceberg are reported as falling (234 in the 2024 period → 88 in 2025 → 55 in the six months to 5 Oct 2026). The permanent-ads snapshot shows a different pattern, and page metadata is inconsistent. Noisy and conflicting. — [ITJobsWatch contracts](https://www.itjobswatch.co.uk/contracts/uk/apache%20iceberg.do); [ITJobsWatch perm](https://www.itjobswatch.co.uk/jobs/uk/apache%20iceberg.do?p=6)
- **Jobspipe** (aggregator, inferred from postings): 1,554 companies whose postings show Iceberg use (258 confirmed) as of Sep 2026. Top confirmed names include Cloudera and Citi. — [Jobspipe](https://jobspipe.dev/technologies/apache-iceberg)
- **Teal**: 284 Apache Iceberg jobs listed as of 2026-01-23 (point-in-time, no trend). — [Teal](https://www.tealhq.com/jobs/skill/apache-iceberg)
- **VENDOR**: Ryft / TrendCandy survey of 252 senior data and IT leaders reports 58% using Iceberg for business-critical analytics. Ryft sells Iceberg management, so this likely overstates adoption. — [Ryft](https://www.ryft.io/the-state-of-apache-iceberg)
- **VENDOR-ADJACENT**: "State of the Apache Iceberg Ecosystem" survey run by Data Lakehouse Hub (Alex Merced, a Dremio developer advocate). Data engineers were 29.6% of respondents. It measures who uses Iceberg, not hiring demand. — [Data Lakehouse Hub](https://datalakehousehub.com/blog/2026-02-state-of-the-apache-iceberg-ecosystem/); [survey](https://icebergsurvey.datalakehousehub.com/)
- **VENDOR**: Dremio "2026 State of the Data Lakehouse & AI" (behind a registration wall, not read). — [Dremio](https://hello.dremio.com/wp-state-of-the-data-lakehouse-2026-reg.html)
- dbt Labs and Fivetran are pushing dbt workloads onto Iceberg through REST catalogs (including Apache Polaris). That is ecosystem momentum from vendors, not hiring evidence. — [dbt blog](https://www.getdbt.com/blog/dbt-lake-compute-data-lake-workloads); [dbt on Iceberg catalogs](https://www.getdbt.com/blog/apache-iceberg-and-the-catalog-layer)

### Inferences
- It is fair to call Iceberg "early-majority infrastructure that is gaining ground". It is not fair to call it a hot hiring keyword. Its 7% posting share (this sample) and 9% production use (dbt) line up.
- "Knowledge gaps" as the top barrier (dbt) suggests that someone who has actually run Iceberg maintenance and catalogs has a rare skill. That argues for depth (operations, failure modes) over just saying "used Iceberg".

### Gaps
- No independent US/global longitudinal job-trend series for Iceberg was found. Stack Overflow's survey was not checked for table formats, and as far as I know it does not ask about them.
- Dremio's report figures were not read.

## Q3. Reference architectures for local / single-node lakehouses

### Takeaway
There is a crowded field of small docker-compose demos, almost all with 0 to 5 stars and created in 2025-2026, plus a few established older ones. The most instructive recent repo is **technobasant/lakehouse-lab** (Polaris + MinIO STS + Trino + StarRocks + dbt + Airflow, around 12 GB, measured maintenance results). The catalog projects are healthy: Polaris about 2.1k stars, Nessie about 1.5k, Lakekeeper about 1.5k, all pushed within the last day. Common pitfalls are MinIO/S3 STS incompatibilities, catalog bootstrap/auth, lost data from missing volumes, and RAM floors of roughly 4 to 12 GB.

### Cited Findings
Star counts and dates were read from the GitHub API on 2026-11-18.

**Catalogs (the component choices):**
- apache/polaris: 2,122 stars, created 2024-05, pushed 2026-11-18. "Interoperable, open source catalog for Apache Iceberg." — [GitHub](https://github.com/apache/polaris)
- lakekeeper/lakekeeper: 1,509 stars, created 2024-04, pushed 2026-11-17. Rust Iceberg REST catalog with "access control, credential vending and audit". — [GitHub](https://github.com/lakekeeper/lakekeeper)
- projectnessie/nessie: 1,534 stars, created 2020-04, pushed 2026-11-18. Git-like branching for catalogs. — [GitHub](https://github.com/projectnessie/nessie)

**Reference stacks:**
- **technobasant/lakehouse-lab** (0 stars, created 2026-10-13): MinIO RELEASE.2025-09-07, Polaris 1.7.0, Postgres 18.1, Trino 483 (1 coordinator + 1 worker), dbt-core 1.12.2 / dbt-trino 1.10.3, Airflow 3.3.1, StarRocks 4.1.4. Docker needs "about 8 CPUs and 12 GB of memory"; measured host 8 CPU / 11.67 GB; no per-service RAM or heap figures.
  - What it did well, with measured results: compaction 20 files → 1, 1,006 KB → 430 KB, partition query 184 ms → 69 ms, job 1.4 s. `rollback_to_snapshot` recovered 909,968 rows in 589 ms after a DELETE. `expire_snapshots` went from 25 snapshots to 1, with time travel to the old snapshot then failing, as it should.
  - Access control: engines authenticate to Polaris over OAuth2 and hold no standing S3 key. Polaris vends short-lived, table-scoped MinIO STS credentials. `verify-scoping.sh` proves the vended credential gets ALLOW on its own table prefix and DENY on the sibling table and on the whole bucket.
  - Pitfalls it reports:
    - Polaris reports healthy on an empty Postgres but fails every request until the schema is bootstrapped.
    - MinIO rejects AssumeRole for its root user.
    - Polaris adds a KMS policy statement that MinIO rejects, so `kmsUnavailable: true` is needed; without it, CTAS succeeds but every SELECT fails with "Failed to load table".
    - Three S3-vs-MinIO workarounds were needed in total.
    - Trino 483 will not start with `iceberg.register-table-procedure.enabled` plus vended credentials.
    - dbt-trino silently ignores `partitioning` set at config level (it belongs under `properties`).
    - `+schema: silver` becomes `silver_silver`.
    - `--full-refresh` fails because of a 403 on purge.
    - Dev-only plaintext credentials, HTTP everywhere, all Airflow users are admin.
  - [GitHub](https://github.com/technobasant/lakehouse-lab)
- **databricks/docker-spark-iceberg** (formerly tabular-io): 388 stars, created 2021, pushed 2026-02. The canonical Spark + Iceberg REST + MinIO quickstart. — [GitHub](https://github.com/databricks/docker-spark-iceberg)
- **dominikhei/Local-Data-LakeHouse**: 81 stars, last push 2023-09. Iceberg + MinIO + Trino + Hive Metastore. Older, Hive-based catalog. — [GitHub](https://github.com/dominikhei/Local-Data-LakeHouse)
- **njanakiev/trino-minio-docker**: 53 stars, 2022. Minimal Trino + MinIO + Hive standalone metastore. — [GitHub](https://github.com/njanakiev/trino-minio-docker)
- **Mjsv31/Lakahouse** (0 stars, 2026-10, Spanish): Spark, Iceberg 1.11.0, Delta, Hive Metastore (bronze/silver), Polaris 1.7.0 (gold only), Trino 483, MinIO. The widest component spread, at the cost of two catalogs. — [GitHub](https://github.com/Mjsv31/Lakahouse)
- **BoonLeeEu/minio-polaris** (0 stars): minimal Trino + Polaris + MinIO. Its README warns that MinIO objects and Polaris metadata in Postgres are lost on `docker compose down` because no volumes are defined. — [GitHub](https://github.com/BoonLeeEu/minio-polaris)
- **AlexMercedCoder/Apache-Polaris-Apache-Iceberg-Minio-Spark-Quickstart** (5 stars, 2025-10; author is a Dremio advocate): Polaris + MinIO + Spark. — [GitHub](https://github.com/AlexMercedCoder/Apache-Polaris-Apache-Iceberg-Minio-Spark-Quickstart)
- **darshansatpathy/lakehouse-iceberg-trino** (0 stars, 2026-11): CDC into Iceberg, one JDBC catalog shared by PyIceberg and Trino, dbt. Its README notes that **MinIO stopped publishing community container images in 2025**, which matters for choosing an S3 layer (alternatives: Garage, Ceph RGW, SeaweedFS). — [GitHub](https://github.com/darshansatpathy/lakehouse-iceberg-trino)
- **thescriptingcave/iceberg-polaris-trino-spark-**: Spark + Trino + Polaris + Garage S3, with labs on ACID, time travel and schema evolution. (The GitHub API returned nothing; the repo may have been renamed or deleted.) — [GitHub](https://github.com/thescriptingcave/iceberg-polaris-trino-spark-)
- **dauglyon/minilakehouse**: OPA-gated Iceberg tables with Trino, Polaris and Ceph RGW. Explicitly dev-only, no TLS. (The API returned nothing; it may now be private.) — [GitHub](https://github.com/dauglyon/minilakehouse)
- **Jsarde/iceberg-lakehouse** (1 star, 2024-12): MinIO + Trino + Nessie with default credentials and no resource guidance. — [GitHub](https://github.com/Jsarde/iceberg-lakehouse)
- **OLake blog**: MinIO + Lakekeeper + Trino in one compose file, a minimal example with no tuning notes. — [OLake](https://olake.io/blog/building-modern-data-lakehouse-with-olake-iceberg-lakekeeper-trino/)
- **"Iceduck"** (DEV Community): a local Iceberg + DuckDB learning stack. — [DEV](https://dev.to/pfabricius/iceduck-a-local-data-lakehouse-stack-for-learning-no-cloud-needed-26e1)
- Medium (Gilles Philippart): Iceberg + Polaris + Trino + MinIO build walkthrough. — [Medium](https://medium.com/@gilles.philippart/build-a-data-lakehouse-with-apache-iceberg-polaris-trino-minio-349c534ecd98)
- Guidance from iceberglakehouse.com: make the local topology match production (REST catalog on MinIO with Spark/Trino if production is Polaris on S3), and use in-memory catalogs for CI. — [iceberglakehouse.com](https://iceberglakehouse.com/posts/local-iceberg-development-environments/)
- One Trino demo lists about 4 GB available to Docker as a whole-stack floor. — [Starburst](https://www.starburst.io/blog/lakehouse-data-pipeline-dbt-trino/etl/)

### Inferences
- A full Polaris + Trino + Airflow + StarRocks stack measured around 12 GB. That is well over GraphGuard's roughly 4 GB budget on a box with 99% swap. A RAM-measured, trimmed design (for example one engine, a lightweight catalog, PyIceberg/DuckDB for small jobs) would set it apart from every repo above, none of which reports per-service RAM.
- Given MinIO's 2025 change to community images and its STS/KMS quirks with Polaris, the choice of S3 layer is a real design decision worth documenting.
- Lakekeeper (Rust, small footprint, built-in authz) and Polaris (Apache, the most stars, dbt/Fivetran support) are the two credible REST catalogs in 2026. Nessie is mature but its git-branching model is a separate selling point.

### Gaps
- No source gave measured Java heap / RSS per service for Trino, Polaris, Nessie or Spark on a single node. RAM figures here are whole-stack floors only.
- Star counts for most 2026 repos are 0. "Activity" is mostly a single author.
- No well-known "Databricks-style mini platform" homelab write-up with measured numbers was found within the budget.

## Q4. What makes a portfolio lakehouse look senior instead of a toy?

### Takeaway
Senior signals map directly onto the capability language in staff-level postings: data contracts, lineage, data quality/reconciliation with SLAs, access control/RBAC, and operations (compaction, snapshot expiry, rollback), all **measured and tested**. No survey of hiring managers exists. The evidence is the posting language plus practitioner and bootcamp opinion, labelled as such.

### Cited Findings
- Staff/principal postings name these capabilities directly:
  - SoFi: "data contracts, metadata and catalog modernization, lineage, data quality, privacy, and access controls" — [SoFi](https://sofi.com/careers/job/8037984003?gh_jid=8037984003)
  - SoFi: "Data Contracts, RBAC mechanisms" — [SoFi](https://sofi.com/careers/job/8207529003?gh_jid=8207529003)
  - Coinbase: "reconciliation frameworks (tests, monitoring, alerting, SLAs)" — [Coinbase](https://www.coinbase.com/careers/positions/8047150?gh_jid=8047150)
  - Chime: "enforce data lineage" — [Chime](https://boards.greenhouse.io/chime/jobs/8840193002?gh_jid=8840193002)
- Lakehouse feature serving tied to ML appears in Toast's staff posting ("cloud-native data lakehouse, feature serving for ML-driven product experiences"), and Upstart's lakehouse is "the platform that Machine Learning… teams use" — [Toast](https://careers.toasttab.com/jobs?gh_jid=8068781); [Upstart](https://careers.upstart.com/jobs?gh_jid=8214129)
- The dbt survey says trust and governance lag AI speed: 83% rate trust as important, and only 24% prioritise AI for testing/observability. Reliability work is the gap employers feel. — [dbt Labs](https://www.getdbt.com/resources/state-of-analytics-engineering-2026)
- lakehouse-lab is a worked example of "every figure measured": compaction, rollback and expiry with numbers, plus a negative test that credential scoping denies sibling tables. — [GitHub](https://github.com/technobasant/lakehouse-lab)
- Practitioner/bootcamp opinion (training vendors, lower weight):
  - Depth over breadth; reviewers spot tutorial datasets and trivial CSV-to-warehouse loads — [Data Engineer Academy](https://dataengineeracademy.com/blog/data-engineer-portfolio-review-checklist-2026-what-hiring-managers-actually-score/)
  - A strong project names a consumer, has automated runs and a failure-handling story, and shows backfills with late or missing partitions — [DataTalks.Club](https://datatalks.club/podwiki/wiki/data-engineering-portfolio-projects/)
  - Idempotency is the prerequisite for safe backfills — [Data Lakehouse Hub glossary](https://datalakehousehub.com/knowledgebase/backfilling-data/); [DEV](https://dev.to/chaets/why-idempotency-is-so-important-in-data-engineering-24mj)

### Inferences
Senior vs toy checklist, synthesised from the above. These are inferences, not survey findings.

| Toy | Senior |
|---|---|
| `docker compose up` with tutorial data | A named consumer, here the GraphGuard XGBoost training and scoring path |
| "Uses Iceberg" | Every model run in MLflow logs the Iceberg **snapshot ID** of its training data, so the exact training set can be rebuilt by time travel. This ties directly to the project's leakage contract and determinism rules. |
| Ad-hoc tables | Data contracts (Pandera / dbt contracts) enforced in CI; schema evolution handled on purpose |
| No ops | Scheduled compaction, `expire_snapshots`, orphan-file cleanup, rollback drill, with before/after numbers |
| Root keys everywhere | Catalog RBAC plus vended, scoped credentials, with a negative test proving a denial |
| No numbers | Per-service RSS / heap caps measured under load, and a cost-per-GB / RAM budget table |
| No failure story | An idempotent rerun, a backfill of a late partition, and a documented incident or rollback |
| Tool salad | One engine chosen with the trade-off written down (and why Polaris/Hudi/etc. were not used) |

- For an ML-platform candidate, the strongest framing is "lakehouse as the reproducibility and point-in-time-correctness layer for an ML model". The posting data shows ML roles do not ask for Iceberg by name but do ask for Spark/Airflow, feature serving and data contracts.

### Gaps
- No survey of hiring managers on portfolio evaluation was found. The portfolio advice comes from training vendors with a commercial interest.

---

## Appendix: the 139 sampled postings (pulled 2026-11-18 from public Greenhouse / Ashby / Lever APIs)

"First published" is Greenhouse `first_published`, Ashby `publishedAt` or Lever `createdAt`. The terms column lists which tracked keywords appear anywhere in the posting text.

| # | Company | Title | First published | Lakehouse-relevant terms found | URL |
|---|---|---|---|---|---|
| 1 | adyen | Senior Data Engineer | 2025-06-27 | Spark, Kafka, Airflow, catalog/governance | https://job-boards.greenhouse.io/adyen/jobs/6919020 |
| 2 | adyen | Senior Machine Learning Engineer - AML Tech | 2026-10-16 | Spark, Airflow, Trino/Presto, Kubernetes, MLflow | https://job-boards.greenhouse.io/adyen/jobs/8288674 |
| 3 | adyen | Staff Machine Learning Engineer, Financial Products | 2026-09-15 | Spark, Airflow, Trino/Presto, feature store, Kubernetes, MLflow | https://job-boards.greenhouse.io/adyen/jobs/8160968 |
| 4 | affirm | Machine Learning Engineer II (ROA + LTV ML) | 2026-10-16 | Spark, Ray | https://job-boards.greenhouse.io/affirm/jobs/8033261003 |
| 5 | affirm | Senior Machine Learning Engineer (Fraud) | 2026-07-21 | Spark, Airflow, MLflow, Ray | https://job-boards.greenhouse.io/affirm/jobs/7806920003 |
| 6 | affirm | Senior Software Engineer, Backend (AI Platform) | 2026-10-26 | Kubernetes | https://job-boards.greenhouse.io/affirm/jobs/8040267003 |
| 7 | affirm | Senior Software Engineer, Backend (ML Feature Platform) | 2026-11-12 | feature store, Kubernetes | https://job-boards.greenhouse.io/affirm/jobs/8199419003 |
| 8 | airbnb |  Senior Machine Learning Engineer, Payments | 2026-03-26 | Spark, Kafka, Airflow, Ray, catalog/governance | https://careers.airbnb.com/positions/7755758?gh_jid=7755758 |
| 9 | airbnb | Machine Learning Engineer, Assistance Engineering | 2026-03-22 | - | https://careers.airbnb.com/positions/7716341?gh_jid=7716341 |
| 10 | airbnb | Principal Machine Learning Engineer- LLM Fine-tuning and Optimization  | 2026-05-24 | - | https://careers.airbnb.com/positions/7955579?gh_jid=7955579 |
| 11 | airbnb | Senior Data Engineer Tech Foundations | 2026-11-17 | Iceberg, Spark, data quality, lineage, catalog/governance | https://careers.airbnb.com/positions/8396777?gh_jid=8396777 |
| 12 | airbnb | Senior Machine Learning Engineer, Assistance Engineering | 2026-06-02 | - | https://careers.airbnb.com/positions/7975743?gh_jid=7975743 |
| 13 | airbnb | Senior Machine Learning Engineer, Query Intelligence | 2026-07-14 | Spark, Kafka, Airflow, Hive, Kubernetes | https://careers.airbnb.com/positions/8065789?gh_jid=8065789 |
| 14 | airbnb | Senior Machine Learning Engineer, Relevance | 2026-11-03 | Spark, Kafka, Airflow, feature store, Hive, Kubernetes | https://careers.airbnb.com/positions/8351417?gh_jid=8351417 |
| 15 | airbnb | Senior Machine Learning Engineer, Trust | 2026-09-24 | - | https://careers.airbnb.com/positions/8232153?gh_jid=8232153 |
| 16 | airbnb | Senior Staff Data Engineer, Foundational Data | 2026-09-22 | Airflow | https://careers.airbnb.com/positions/8224032?gh_jid=8224032 |
| 17 | airbnb | Senior Staff Machine Learning Engineer, Data & Eval | 2025-03-30 | data quality, catalog/governance | https://careers.airbnb.com/positions/6757302?gh_jid=6757302 |
| 18 | airbnb | Senior Staff Machine Learning Engineer, Post Training | 2026-05-05 | - | https://careers.airbnb.com/positions/7858738?gh_jid=7858738 |
| 19 | airbnb | Senior Staff Machine Learning Engineer, Trust | 2026-02-05 | Kubernetes | https://careers.airbnb.com/positions/7592146?gh_jid=7592146 |
| 20 | airbnb | Staff Machine Learning Engineer, Assistance Engineering | 2026-06-23 | - | https://careers.airbnb.com/positions/8024316?gh_jid=8024316 |
| 21 | airbnb | Staff Machine Learning Engineer, Traffic Intelligence | 2026-08-13 | catalog/governance | https://careers.airbnb.com/positions/8129371?gh_jid=8129371 |
| 22 | airwallex | Data Platform Principal Architect, Seattle/San Francisco | 2026-11-16 | Delta Lake, Databricks, Unity Catalog, Spark, Kafka, lineage, catalog/governance | https://jobs.ashbyhq.com/airwallex/eb6603a0-87a5-4847-bbc7-b17d7897f9ad |
| 23 | airwallex | Senior Data Engineer (San Francisco) | 2026-10-08 | Snowflake, Airflow, BigQuery, data quality, catalog/governance | https://jobs.ashbyhq.com/airwallex/31dfbbce-3274-4dca-8939-36cceff1c60e |
| 24 | airwallex | Senior Data Engineer (Seattle) | 2026-10-08 | Snowflake, Airflow, BigQuery, data quality, catalog/governance | https://jobs.ashbyhq.com/airwallex/5baeefbf-f0d1-4e50-9b4d-f983fcc74738 |
| 25 | airwallex | Senior Data Engineer, Data and AI, Customer Data Platform | 2026-11-03 | Databricks, Snowflake, Spark, Flink, Kafka, dbt, Airflow | https://jobs.ashbyhq.com/airwallex/7b252696-914f-49a9-86ff-5a6b10136219 |
| 26 | airwallex | Senior Data Engineer, Knowledge Platform, Foundational Data | 2026-10-19 | Databricks, Snowflake, Spark, Kafka, dbt, Airflow, data quality, catalog/governance | https://jobs.ashbyhq.com/airwallex/39069d1d-9a56-4ef2-b326-8cc1f46a25f9 |
| 27 | airwallex | Senior Data Platform Engineer, Knowledge Platform & AI Enablement | 2026-03-06 | lakehouse, Databricks, Snowflake, Spark, Flink, Kafka, dbt, BigQuery, catalog/governance | https://jobs.ashbyhq.com/airwallex/6e975468-e033-4f50-95fe-0f4351457003 |
| 28 | airwallex | Senior Software Engineer, Data Platform & AI Enablement | 2026-09-10 | Databricks, Spark, Flink, Kafka, Kubernetes, catalog/governance | https://jobs.ashbyhq.com/airwallex/396cd4cf-a1c6-47fa-829b-b7ee6c963206 |
| 29 | airwallex | Senior Software Engineer, Machine Learning Platform | 2026-10-08 | Airflow, Kubernetes, Ray | https://jobs.ashbyhq.com/airwallex/89fccb81-c8cc-4769-be0c-9ed078e1a03b |
| 30 | airwallex | Staff Data Engineer, Data and AI, Customer Data Platform | 2026-11-03 | Databricks, Snowflake, Spark, Flink, Kafka, dbt, Airflow | https://jobs.ashbyhq.com/airwallex/e77c835b-90e8-4d77-9a44-38d2f6d929fd |
| 31 | airwallex | Staff Data Platform Engineer, Knowledge Platform | 2026-05-22 | lakehouse, Databricks, Spark, Kafka, dbt, Airflow, BigQuery, Kubernetes, catalog/governance | https://jobs.ashbyhq.com/airwallex/5fa97d90-9c8c-452a-9ec0-d0949ec10ae0 |
| 32 | alloy | Senior Analytics Engineer | 2026-07-07 | Snowflake, dbt, data quality, catalog/governance | https://jobs.ashbyhq.com/5c335d0c-0c96-4b85-a913-db4ce4f02651/2f8a5d60-8dd8-49e3-b260-7fa533cf9b5e |
| 33 | alloy | Senior Machine Learning Engineer | 2026-04-07 | catalog/governance | https://jobs.ashbyhq.com/5c335d0c-0c96-4b85-a913-db4ce4f02651/3ce8dae1-9bd4-4b0c-b19d-721be8f057c6 |
| 34 | block | Senior Analytics Engineer, AI & DX Analytics | 2026-09-24 | Snowflake, dbt, catalog/governance | http://block.xyz/careers/jobs/5434325008?gh_jid=5434325008 |
| 35 | block | Senior Data Engineer, Product | 2026-10-08 | Databricks, Snowflake, dbt, Airflow, data quality, lineage, Terraform | http://block.xyz/careers/jobs/5442647008?gh_jid=5442647008 |
| 36 | block | Senior Machine Learning Engineer, Platform | 2026-11-13 | Databricks, Spark, feature store | http://block.xyz/careers/jobs/5481625008?gh_jid=5481625008 |
| 37 | block | Software Engineer, Data Platform | 2026-08-28 | Iceberg, Databricks, Snowflake, dbt, Airflow, data quality, lineage, Terraform, catalog/governance | http://block.xyz/careers/jobs/5381381008?gh_jid=5381381008 |
| 38 | block | Staff Data Engineer, Advanced Insights & Modeling | 2026-11-12 | Snowflake, dbt, Airflow, data contracts, data quality, lineage | http://block.xyz/careers/jobs/5473605008?gh_jid=5473605008 |
| 39 | brex | Data Engineer | 2026-04-24 | Snowflake, dbt, Airflow | https://www.brex.com/careers/8523806002?gh_jid=8523806002 |
| 40 | brex | Staff Software Engineer, Product Data Platform | 2026-02-19 | Flink, Kafka | https://www.brex.com/careers/8430196002?gh_jid=8430196002 |
| 41 | checkr | Senior Machine Learning Engineer | 2026-11-09 | Snowflake, Spark, dbt, MLflow | https://job-boards.greenhouse.io/checkr/jobs/8369164 |
| 42 | chime | AI/ML Engineer | 2026-06-08 | Snowflake, Spark, Kafka, Airflow, catalog/governance | https://boards.greenhouse.io/chime/jobs/8569366002?gh_jid=8569366002 |
| 43 | chime | Senior Software Engineer, Data Engineering | 2026-04-23 | Snowflake, Spark, Airflow, Redshift, data quality, catalog/governance | https://boards.greenhouse.io/chime/jobs/8505462002?gh_jid=8505462002 |
| 44 | chime | Senior Software Engineer, Data Platform | 2026-10-02 | Snowflake, Flink, Kafka, dbt, Airflow, Dagster, BigQuery, Redshift, data contracts, data quality, lineage, Terraform, catalog/governance | https://boards.greenhouse.io/chime/jobs/8840193002?gh_jid=8840193002 |
| 45 | chime | Senior Software Engineer, Machine Learning Platform | 2026-09-11 | Spark, Flink, Kafka, data contracts, feature store, Kubernetes, Terraform, Ray, catalog/governance | https://boards.greenhouse.io/chime/jobs/8765684002?gh_jid=8765684002 |
| 46 | chime | Staff AI/ML Engineer | 2026-10-15 | Snowflake, Spark, Kafka, Airflow, catalog/governance | https://boards.greenhouse.io/chime/jobs/8840205002?gh_jid=8840205002 |
| 47 | coinbase | Machine Learning Engineer | 2026-06-22 | - | https://www.coinbase.com/careers/positions/7985187?gh_jid=7985187 |
| 48 | coinbase | Machine Learning Engineer, CX Intelligence | 2026-07-07 | - | https://www.coinbase.com/careers/positions/8031260?gh_jid=8031260 |
| 49 | coinbase | Senior Machine Learning Engineer | 2026-11-06 | Databricks, Spark, Kafka, Feast/Tecton, Ray | https://www.coinbase.com/careers/positions/8347602?gh_jid=8347602 |
| 50 | coinbase | Senior Machine Learning Engineer, CX  | 2026-10-16 | - | https://www.coinbase.com/careers/positions/8292793?gh_jid=8292793 |
| 51 | coinbase | Senior Machine Learning Engineer, CX Intelligence  | 2026-06-15 | - | https://www.coinbase.com/careers/positions/8008569?gh_jid=8008569 |
| 52 | coinbase | Senior Machine Learning Platform Engineer - Identity | 2026-09-17 | data quality, feature store | https://www.coinbase.com/careers/positions/8211490?gh_jid=8211490 |
| 53 | coinbase | Senior Market Data Engineer | 2026-09-04 | - | https://www.coinbase.com/careers/positions/8180833?gh_jid=8180833 |
| 54 | coinbase | Senior Software Engineer - Data Platform | 2026-10-27 | Spark, Kafka, Airflow, lineage, data lake | https://www.coinbase.com/careers/positions/8325213?gh_jid=8325213 |
| 55 | coinbase | Senior Software Engineer, Data Engineering Platform | 2026-07-24 | Databricks, Snowflake, Airflow, data quality, lineage | https://www.coinbase.com/careers/positions/8082199?gh_jid=8082199 |
| 56 | coinbase | Staff Analytics Engineer | 2026-10-30 | lakehouse, Databricks, Snowflake, dbt, Airflow, BigQuery, Redshift, data contracts, data quality, lineage | https://www.coinbase.com/careers/positions/8047150?gh_jid=8047150 |
| 57 | coinbase | Staff Data Engineer, Market Data | 2026-08-20 | - | https://www.coinbase.com/careers/positions/8144836?gh_jid=8144836 |
| 58 | coinbase | Staff Machine Learning Engineer | 2026-10-09 | - | https://www.coinbase.com/careers/positions/8267151?gh_jid=8267151 |
| 59 | coinbase | Staff Machine Learning Engineer(Platform - Identity) | 2026-06-10 | - | https://www.coinbase.com/careers/positions/7891045?gh_jid=7891045 |
| 60 | coinbase | Staff Machine Learning Engineer, Compliance Automation (Platform) | 2026-10-29 | Spark, Airflow | https://www.coinbase.com/careers/positions/8333165?gh_jid=8333165 |
| 61 | figma | Software Engineer - AI Platforms | 2025-11-01 | - | https://boards.greenhouse.io/figma/jobs/5691886004?gh_jid=5691886004 |
| 62 | figma | Software Engineer - Data Infrastructure | 2025-06-02 | Snowflake, Spark, Flink, Kafka, dbt, Airflow, Dagster, data quality, feature store, data lake, catalog/governance | https://boards.greenhouse.io/figma/jobs/5551686004?gh_jid=5551686004 |
| 63 | gemini | Senior Data Engineer | 2026-07-21 | Databricks, Snowflake, Spark, Flink, Kafka, Airflow, BigQuery, data quality, lineage, catalog/governance | https://boards.greenhouse.io/embed/job_app?for=gemini&token=8076827&gh_jid=8076827 |
| 64 | gocardless | Analytics engineer | 2026-03-16 | dbt, lineage, catalog/governance | https://job-boards.greenhouse.io/gocardless/jobs/7699256 |
| 65 | gocardless | Data Engineer | 2026-09-24 | dbt, Airflow, BigQuery, data quality, Terraform, catalog/governance | https://job-boards.greenhouse.io/gocardless/jobs/8210486 |
| 66 | gusto | Staff Machine Learning Engineer - Risk | 2026-11-05 | - | https://job-boards.greenhouse.io/gusto/jobs/7168696 |
| 67 | gusto | Staff Software Engineer, Core AI Platforms | 2026-03-27 | - | https://job-boards.greenhouse.io/gusto/jobs/7760341 |
| 68 | instacart | Senior Machine Learning Engineer, Fulfillment | 2026-10-30 | Spark, Airflow, feature store, Kubernetes | https://instacart.careers/job/?gh_jid=8240305 |
| 69 | instacart | Senior Machine Learning Engineer, Operations Research | 2026-04-09 | - | https://instacart.careers/job/?gh_jid=7793089 |
| 70 | instacart | Staff Software Engineer, Ads Data Platform | 2026-11-10 | Databricks, Snowflake, Spark, dbt, Airflow, Terraform | https://instacart.careers/job/?gh_jid=8372848 |
| 71 | lyft | Data Engineer | 2026-11-10 | Kafka, Airflow, BigQuery | https://app.careerpuck.com/job-board/lyft/job/8931413002?gh_jid=8931413002 |
| 72 | lyft | Data Engineer, Marketplace | 2026-11-13 | Spark, Airflow, data quality | https://app.careerpuck.com/job-board/lyft/job/8940409002?gh_jid=8940409002 |
| 73 | lyft | ML Engineer, Marketplace | 2026-11-17 | - | https://app.careerpuck.com/job-board/lyft/job/8944659002?gh_jid=8944659002 |
| 74 | lyft | Machine Learning Engineer, Safety and Customer Care AI | 2026-08-06 | - | https://app.careerpuck.com/job-board/lyft/job/8684440002?gh_jid=8684440002 |
| 75 | lyft | Senior Machine Learning Engineer, Recommendations | 2026-02-20 | - | https://app.careerpuck.com/job-board/lyft/job/8430552002?gh_jid=8430552002 |
| 76 | mercury | Senior Analytics Engineer | 2026-10-05 | Snowflake, dbt, Airflow, data quality, catalog/governance | https://job-boards.greenhouse.io/mercury/jobs/6217794004 |
| 77 | notion | Data Engineer, Product | 2026-10-28 | Snowflake, Spark, dbt, Airflow, Redshift, Parquet, Hive | https://jobs.ashbyhq.com/notion/73a71747-28d3-4dda-a718-77336056e687 |
| 78 | openai | Data Engineer | 2023-09-26 | Spark, Flink, Airflow, Dagster, S3 | https://jobs.ashbyhq.com/openai/fc5bbc77-a30c-4e7a-9acc-8a2e748545b4 |
| 79 | openai | Data Engineer, Core Experimentation | 2026-10-06 | Spark, Flink, Airflow, Dagster, S3 | https://jobs.ashbyhq.com/openai/2796d32a-9f7c-4008-a2c5-50dd53b0f2fe |
| 80 | openai | Data Engineer, Hardware & Consumer Devices | 2026-10-01 | data quality | https://jobs.ashbyhq.com/openai/c25fd30e-056e-4a26-af80-7ea1074fc56e |
| 81 | openai | Machine Learning Engineer, API Multicloud | 2026-08-13 | - | https://jobs.ashbyhq.com/openai/5acf4854-1d42-40ca-bff8-4f6f04cdce68 |
| 82 | openai | Machine Learning Engineer, Core Experimentation | 2026-09-24 | lineage | https://jobs.ashbyhq.com/openai/9d4d2727-27f3-4a63-857c-a96466130645 |
| 83 | openai | Machine Learning Engineer, Implicit Signals | 2026-10-13 | - | https://jobs.ashbyhq.com/openai/a01fc9ed-de08-4326-9206-4ee3f08000dc |
| 84 | openai | Machine Learning Engineer, Monetization AI/ML | 2026-09-21 | - | https://jobs.ashbyhq.com/openai/80f9f564-d789-47bc-91c3-3babf5a1a33d |
| 85 | openai | Software Engineer, CI/CD & ML Infrastructure | 2026-10-19 | - | https://jobs.ashbyhq.com/openai/a5dd77a2-9ab1-4165-98aa-c7bb0260985b |
| 86 | openai | Software Engineer, Data Infrastructure | 2024-06-27 | Iceberg, Spark, Flink, Kafka, Airflow, Trino/Presto, Terraform | https://jobs.ashbyhq.com/openai/f763c6b3-5167-4a67-b691-4c3fa2c44156 |
| 87 | openai | Software Engineer, Monetization ML Infrastructure | 2026-06-01 | - | https://jobs.ashbyhq.com/openai/348ac6bf-a5c3-43d1-a14a-5f1a3c8d90fa |
| 88 | palantir | Data Engineer - Talent Acquisition Operations | 2026-10-07 | Spark, Polars, data quality, catalog/governance | https://jobs.lever.co/palantir/1b690123-1766-4e75-a0ef-0f58afa864b4 |
| 89 | plaid | Machine Learning Engineer - Income Insights | 2026-11-02 | Spark | https://jobs.ashbyhq.com/plaid/8d8378cf-edf2-4c86-afcc-49df91ece2e4 |
| 90 | plaid | Senior Analytics Engineer | 2026-10-16 | Databricks, Snowflake, dbt, BigQuery, Redshift | https://jobs.ashbyhq.com/plaid/98c030bd-a72d-4045-87aa-b8ff7d0d43fb |
| 91 | plaid | Senior Data Engineer | 2026-09-03 | Databricks, Snowflake, Spark, Kafka, dbt, Airflow, Redshift, data quality, data lake | https://jobs.ashbyhq.com/plaid/eeb094c3-da73-411e-8dda-b3f4ee397f97 |
| 92 | plaid | Senior Machine Learning Engineer - Embedded Insights | 2026-09-10 | - | https://jobs.ashbyhq.com/plaid/a1db9566-d51d-495e-9e87-4d57ac307d3c |
| 93 | plaid | Senior Machine Learning Engineer - Fraud | 2026-11-17 | - | https://jobs.ashbyhq.com/plaid/e9a9aeab-be90-43f3-b898-63a846cb5777 |
| 94 | plaid | Staff Machine Learning Engineer (Research Scientist) - DFAI | 2026-10-21 | feature store | https://jobs.ashbyhq.com/plaid/dab31ae8-1e25-4b63-8008-d6930ff72369 |
| 95 | plaid | Staff Machine Learning Engineer (Research Scientist) - Fraud | 2026-11-17 | - | https://jobs.ashbyhq.com/plaid/5e56c0a6-3caa-4255-8c63-95c29cbc2a32 |
| 96 | plaid | Staff Machine Learning Engineer - Fraud | 2026-11-17 | data quality | https://jobs.ashbyhq.com/plaid/85cd5d07-9920-45fa-931a-daf8c3558e5b |
| 97 | plaid | Staff Software Engineer - Data Infrastructure | 2026-11-17 | lakehouse, Databricks, Spark, Airflow | https://jobs.ashbyhq.com/plaid/127d31ff-3a16-488b-ba01-6e87dbb96957 |
| 98 | ramp | Machine Learning Engineer | 2026-09-23 | Snowflake, dbt | https://jobs.ashbyhq.com/ramp/2888b101-b1da-4e53-a02e-1bb9b1b5a951 |
| 99 | ripple | Staff Software Engineer, AI Platform | 2026-08-14 | Kubernetes, Terraform | https://ripple.com/careers/all-jobs/job/8129139?gh_jid=8129139 |
| 100 | robinhood | Senior Staff Software Engineer, Data Platform | 2026-03-18 | Delta Lake, Spark, Flink, Kafka, Kubernetes, data lake | https://boards.greenhouse.io/robinhood/jobs/7729014?t=gh_src=&gh_jid=7729014 |
| 101 | robinhood | Software Developer, Data Engineering | 2024-01-22 | Spark, Airflow, Trino/Presto, data lake | https://boards.greenhouse.io/robinhood/jobs/5616144?t=gh_src=&gh_jid=5616144 |
| 102 | robinhood | Staff Machine Learning Engineer, AI Platform & Agentic Apps | 2026-09-19 | Spark | https://boards.greenhouse.io/robinhood/jobs/8107212?t=gh_src=&gh_jid=8107212 |
| 103 | sardine | Machine Learning Engineer | 2025-09-09 | Kubernetes | https://jobs.ashbyhq.com/sardine/2c8f0342-b8af-4cc2-85cd-67bc48275568 |
| 104 | sift | Machine Learning Engineer | 2026-10-28 | Databricks, Spark, Flink, Kafka, Kubernetes | https://jobs.ashbyhq.com/sift/45b22605-1abb-483e-8ef7-5ceaf04f5868 |
| 105 | socure | Senior Data Engineer | 2026-03-26 | lakehouse, Spark, Kafka, Airflow, S3 | https://jobs.ashbyhq.com/socure/6b0e7888-8842-49ca-a9d0-97eddde7003a |
| 106 | sofi | Principal Software Engineer, Data Platform — Data Trust & AI Context | 2026-10-23 | Iceberg, Snowflake, Kafka, data contracts, data quality, lineage, Terraform, catalog/governance | https://sofi.com/careers/job/8037984003?gh_jid=8037984003 |
| 107 | sofi | Senior Data Engineer | 2026-10-23 | Snowflake, dbt, Airflow, data quality, catalog/governance | https://sofi.com/careers/job/8040823003?gh_jid=8040823003 |
| 108 | sofi | Senior Data Engineer- People Analytics  | 2026-08-24 | Snowflake, dbt, Airflow, Redshift, data quality, catalog/governance | https://sofi.com/careers/job/7963974003?gh_jid=7963974003 |
| 109 | sofi | Senior Software Engineer, AI Platform - Prism | 2026-11-06 | Kubernetes, catalog/governance | https://sofi.com/careers/job/8197346003?gh_jid=8197346003 |
| 110 | sofi | Senior Software Engineer, Data Platform | 2026-11-17 | Snowflake, Kafka, Airflow, S3, data contracts, Kubernetes, catalog/governance | https://sofi.com/careers/job/8207529003?gh_jid=8207529003 |
| 111 | stripe | Machine Learning Engineer, Growth Platform | 2026-09-28 | Spark | https://stripe.com/jobs/search?gh_jid=8224915 |
| 112 | stripe | Machine Learning Engineer, Link | 2026-09-21 | Spark | https://stripe.com/jobs/search?gh_jid=8197886 |
| 113 | stripe | Machine Learning Engineer, Radar | 2026-06-23 | - | https://stripe.com/jobs/search?gh_jid=7983456 |
| 114 | stripe | Machine Learning Engineer, Transaction Risk | 2026-11-10 | - | https://stripe.com/jobs/search?gh_jid=8187574 |
| 115 | stripe | Senior Staff Engineer, Big Data Infrastructure | 2026-11-04 | Iceberg, Spark, Airflow, S3, Hive, Kubernetes, data lake, catalog/governance | https://stripe.com/jobs/search?gh_jid=8317306 |
| 116 | stripe | Staff Machine Learning Engineer, Financial Connections | 2026-08-24 | Spark, data quality | https://stripe.com/jobs/search?gh_jid=8148653 |
| 117 | stripe | Staff Machine Learning Engineer, Radar | 2026-10-07 | - | https://stripe.com/jobs/search?gh_jid=8243615 |
| 118 | stripe | Staff Software Engineer, Risk Data Engineering | 2026-08-06 | Iceberg, Spark, Flink, Kafka, Airflow, Trino/Presto, data quality, Hive | https://stripe.com/jobs/search?gh_jid=8112043 |
| 119 | toast | Data Engineer | 2026-11-17 | Delta Lake, lakehouse, Snowflake, dbt, Airflow, BigQuery, Redshift, data quality, lineage, Terraform, catalog/governance | https://careers.toasttab.com/jobs?gh_jid=8359240 |
| 120 | toast | Principal Machine Learning Engineer, Vision AI | 2026-11-13 | Kafka | https://careers.toasttab.com/jobs?gh_jid=8368740 |
| 121 | toast | Staff Machine Learning Engineer - Vision AI | 2026-11-13 | - | https://careers.toasttab.com/jobs?gh_jid=8368738 |
| 122 | toast | Staff Software Engineer - Data Platform | 2026-07-30 | Iceberg, lakehouse, Databricks, Spark, Kafka, feature store | https://careers.toasttab.com/jobs?gh_jid=8068781 |
| 123 | toast | Staff/Senior Software Engineer, Voice AI Platform | 2026-08-16 | - | https://careers.toasttab.com/jobs?gh_jid=8131117 |
| 124 | trm-labs | Data Engineer, AI Platform | 2026-07-22 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/13abf238-3475-4227-91cd-ac470973080f |
| 125 | trm-labs | Data Platform Engineer - AI Platform | 2026-08-12 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/2a784630-702d-4b49-a033-5cbd0d9c8a94 |
| 126 | trm-labs | Senior Data Engineer - AI Platform | 2026-08-12 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/45e886bf-748d-41cb-9748-258440d12b61 |
| 127 | trm-labs | Senior Data Engineer, Graph Analytics | 2025-11-06 | Spark | https://jobs.ashbyhq.com/trm-labs/20f7a5b3-94c6-4b9d-9e4a-002aa2ef6906 |
| 128 | trm-labs | Senior Data Platform Engineer - AI Platform | 2026-08-12 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/cf1c3e90-d709-4a64-825f-7c0f0768965a |
| 129 | trm-labs | Senior Machine Learning Engineer, Knowledge Layer | 2026-10-27 | - | https://jobs.ashbyhq.com/trm-labs/f906798e-b5da-440b-80a0-639356e72e1d |
| 130 | trm-labs | Senior Software Engineer, Data Infrastructure (RDBMS)  | 2026-09-22 | - | https://jobs.ashbyhq.com/trm-labs/33af3036-a865-44cd-a609-76f91d3c203d |
| 131 | trm-labs | Senior Software Engineer, Data Infrastructure (RDBMS) (LATAM) | 2026-10-21 | - | https://jobs.ashbyhq.com/trm-labs/bf05e1f6-17e2-4639-ae9c-9afe0199a028 |
| 132 | trm-labs | Senior Software Engineer, Data Infrastructure - AI Platform | 2026-08-12 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/75699d68-f602-46f3-b51e-4ccc283a727d |
| 133 | trm-labs | Senior Software Engineer, Data Platform | 2026-09-23 | Iceberg, Spark, Flink, Kafka, dbt, Airflow, Trino/Presto, BigQuery, Kubernetes, Terraform | https://jobs.ashbyhq.com/trm-labs/990a102e-3596-49ac-b527-9addc25771c4 |
| 134 | trm-labs | Software Engineer, Data Infrastructure - AI Platform | 2026-08-12 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/85d748d0-5377-486f-9209-c811704dbdaa |
| 135 | trm-labs | Staff Data Engineer - AI Platform | 2026-08-12 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/74fc12c1-be22-496e-812d-1316276c91e8 |
| 136 | trm-labs | Staff Data Platform Engineer - AI Platform | 2026-08-12 | Trino/Presto | https://jobs.ashbyhq.com/trm-labs/a1ed36fb-8be9-40a9-8452-5641996130c3 |
| 137 | trm-labs | Staff Software Engineer, Data Platform | 2026-09-23 | Iceberg, Spark, Flink, Kafka, dbt, Airflow, Trino/Presto, BigQuery, Kubernetes, Terraform | https://jobs.ashbyhq.com/trm-labs/e989a9b7-103d-46fb-9787-7f81c8f361c4 |
| 138 | upstart | Senior Data Platform Engineer | 2026-09-29 | Iceberg, Delta Lake, lakehouse, Databricks, Snowflake, Spark, Kafka, S3, data quality, Kubernetes, Terraform | https://careers.upstart.com/jobs?gh_jid=8214129 |
| 139 | upstart | Staff/Principal Machine Learning Engineer | 2025-11-19 | Spark, feature store | https://careers.upstart.com/jobs?gh_jid=7370621 |
