# Platform layers of Databricks/Snowflake and their open-source single-box equivalents (as of Nov 2026)

Scope note: research done 2026-11-18 with ~24 searches/fetches. Many RAM figures in this space are vendor or forum numbers, not measurements. Each one below is labelled **[official]**, **[vendor]**, **[forum/3rd-party]**, **[measured locally]** or **[inference]**. The one locally measured number is from this project's own CLAUDE.md: MLflow idles at ~695MB and is capped at 1200M, with Postgres capped at 512M.

## 1. Medallion architecture (bronze/silver/gold): definition, Iceberg implementation, still recommended?

### Takeaway
Databricks' own docs still describe medallion as a "recommended best practice but not a requirement". It is a naming convention for quality tiers, not a technology, so it maps directly onto three Iceberg namespaces (bronze/silver/gold) in any REST catalog.

### Cited Findings
- Databricks defines medallion as "a series of data layers that denote the quality of data stored in the lakehouse": bronze (raw), silver (validated), gold (enriched). The aim is to "incrementally and progressively improve the structure and quality of data" — [Databricks docs: medallion](https://docs.databricks.com/aws/en/lakehouse/medallion.html)
- Silver tables are built by reading bronze or silver tables. Databricks does not recommend writing to silver directly from ingestion — [Databricks docs](https://docs.databricks.com/aws/en/lakehouse/medallion.html)
- The docs call the pattern a recommended best practice, not a requirement — [Databricks docs](https://docs.databricks.com/lakehouse/medallion)
- Also called "multi-hop" architecture. Databricks markets Spark Declarative Pipelines as the way to build bronze/silver/gold tables (vendor marketing) — [Databricks blog: What is medallion architecture](https://www.databricks.com/blog/what-is-medallion-architecture)
- On Iceberg: DuckDB's Iceberg extension can CREATE SCHEMA/TABLE, INSERT, UPDATE, DELETE, MERGE INTO and ALTER TABLE once a REST catalog is attached. Writes require the catalog because it commits the metadata. UPDATE/DELETE are merge-on-read only (positional delete files), and copy-on-write is not supported — [DuckDB docs: Iceberg writing](https://duckdb.org/docs/current/core_extensions/iceberg/writing.html); [DuckDB blog: Writes in DuckDB-Iceberg (2025-11-28)](https://duckdb.org/2025/11/28/iceberg-writes-in-duckdb)
- DuckDB's REST catalog support covers S3, S3 Tables and GCS backends. "Other storage backends are not yet available" — [DuckDB docs: Iceberg catalogs](https://duckdb.org/docs/current/core_extensions/iceberg/catalogs)
- Version history conflicts. A third-party blog says writes landed in DuckDB 1.4.0 (Sept 2025), with MERGE INTO and full schema evolution in 1.5.3. The 1.4 docs still list MERGE INTO as unsupported — [DuckDB 1.4 REST catalog docs](https://duckdb.org/docs/1.4/core_extensions/iceberg/iceberg_rest_catalogs); [datalakehousehub (3rd-party)](https://datalakehousehub.com/blog/2026-05-duckdb-polars-iceberg/)

### Inferences
- For GraphGuard, a natural mapping is: `bronze.transactions_raw` (the Kaggle CSV landed as-is, append-only); `silver.transactions` (Pandera-validated, typed, deduped, artifact columns from FINDING-006 dropped); `gold.features_asof` (point-in-time features per transaction); and `gold.scores`/`gold.alerts`. Each layer is one Iceberg namespace. Each snapshot id becomes the version key that MLflow records (see section 9).
- DuckDB's storage limit (S3/GCS only for REST writes) means a single box needs a local S3-compatible store (MinIO, Garage or similar) or a real S3 bucket, not plain local disk, to get DuckDB writes through a REST catalog. PyIceberg/Polars writers may differ; that was not verified here.
- Medallion is cheap "platform value": it costs zero RAM and is the vocabulary interviewers expect.

### Gaps
- I found no 2026-dated revision of the Databricks medallion page and no authoritative 2026 critique ("medallion is dead" style posts exist, but I did not verify a credible one).
- Polars/PyIceberg write maturity against Lakekeeper/Polaris was not checked in this pass.

## 2. Transformations: dbt Core / dbt Fusion / SQLMesh / dbt-duckdb

### Takeaway
After the Fivetran–dbt Labs merger closed (2026-06-01), dbt v1.x Core stays Apache 2.0. The Fusion engine runtime was open-sourced as "dbt Core v2.0 (alpha)" under Apache 2.0, but the main "dbt" distribution includes proprietary pieces under a separate licence. SQLMesh was donated to the Linux Foundation (announced 2026-03-25). For a Python/Polars-heavy pipeline, neither tool is required: plain Python assets plus Pandera may be the honest choice, and SQLMesh is the cleanest open-governance option if a SQL layer is wanted.

### Cited Findings
- Fivetran and dbt Labs completed an all-stock merger on 2026-06-01. It was first announced in October 2025 — [Fivetran press release](https://www.fivetran.com/press/fivetran-dbt-labs-complete-merger-to-create-the-data-infrastructure-for-trusted-ai-agents); [BusinessWire](https://www.businesswire.com/news/home/20260601514374/en/)
- The press release describes "the open sourcing of the dbt Fusion engine runtime, released as dbt Core v2.0 under an Apache 2.0 license" (alpha) — [Fivetran press release](https://www.fivetran.com/press/fivetran-dbt-labs-complete-merger-to-create-the-data-infrastructure-for-trusted-ai-agents)
- dbt Licensing FAQ: the dbt Core v1.x licence is still Apache 2.0. The main distribution, now just called "dbt", contains everything in dbt OSS plus features derived from proprietary code (e.g. SQL comprehension) and is governed by a dbt Product Licensing Agreement. The FAQ says the "dbt Core" name no longer applies to any v2 distribution, which conflicts with the press-release wording above — [dbt Licensing FAQ](https://www.getdbt.com/licenses-faq); [dbt blog: Fivetran and dbt are one company now](https://getdbt.com/blog/fivetran-and-dbt-are-one-company-now-here-s-what-that-means)
- A competitor's blog voices concern that investment may shift to dbt Cloud/Fusion, leaving Core with mostly fixes. This is opinion, not an observed outcome — [Peliqan (competitor blog)](https://peliqan.io/blog/dbt-fivetran-merger-explained/)
- Fivetran acquired Tobiko Data (SQLMesh's maker) in 2025, then contributed SQLMesh to the Linux Foundation (announced 2026-03-25). Founding members are Benzinga, CloudKitchens, Harness, Infinite Lambda, Jump AI and Minerva. Code and docs stay on GitHub — [Fivetran press release](https://www.fivetran.com/press/fivetran-contributes-sqlmesh-to-the-linux-foundation-to-advance-open-data-infrastructure); [The New Stack](https://thenewstack.io/fivetran-donates-sqlmesh-lf/); [Techzine](https://www.techzine.eu/news/analytics/139955/fivetran-donates-sqlmesh-to-the-linux-foundation/)
- Fivetran now owns or stewards dbt, SQLMesh (donated to LF) and Great Expectations (see section 3) — [The New Stack](https://thenewstack.io/fivetran-donates-sqlmesh-lf/); [Fivetran GX press release](https://wf-prod.fivetran.com/press/fivetran-to-become-steward-of-the-great-expectations-open-source-community-and-gx-core-project)

### Inferences
- The licensing story is now murky enough that a portfolio write-up should name the exact distribution and licence used (e.g. "dbt-core 1.x, Apache 2.0" or "SQLMesh, LF-hosted").
- GraphGuard's point-in-time features are Python/Polars window logic that is already guarded by `leakage_guard.py`. Rewriting them in SQL to "use dbt" adds a second implementation and a train/serve-parity risk. The most defensible use of a SQL transform tool would be bronze→silver cleaning and gold reporting tables, not the feature logic itself.
- RAM: dbt and SQLMesh are CLI/Python processes that run only during a job, so their idle footprint is ~0 **[inference]**. SQLMesh's optional UI would be a long-running process (not measured).

### Gaps
- dbt-duckdb's Iceberg (REST catalog) support: no source found in this pass.
- SQLMesh release cadence after the LF donation: not checked.
- I could not find a measured RAM figure for a dbt or SQLMesh run.

## 3. Data quality and contracts: Pandera, GX Core, Soda Core, dbt tests

### Takeaway
GX Core is alive (1.24.1, 2026-10-22) and now under Fivetran stewardship. Soda Core 4 (Jan 2026) moved to data-contract YAML and reportedly to the Elastic License 2.0, so it is no longer OSI open source. Pandera, which the project already uses, stays the lowest-footprint fit for a Polars pipeline. Adding GX or Soda would mostly duplicate it.

### Cited Findings
- GX Core latest is 1.24.1 (2026-10-22). It fixes Snowflake key-pair auth, and the changelog has a deprecation table targeting 2.0.0 — [GX changelog](https://docs.greatexpectations.io/docs/core/changelog)
- On 2026-05-13 Fivetran announced it would become steward of the Great Expectations OSS community and GX Core — [Fivetran press release](https://wf-prod.fivetran.com/press/fivetran-to-become-steward-of-the-great-expectations-open-source-community-and-gx-core-project); [BusinessWire](https://www.businesswire.com/news/home/20260513083026/en/)
- Soda Core 4.0.5 was the first public v4 release (2026-01-28). It makes data contracts the default and is a breaking change from SodaCL checks. 4.7.0 shipped 2026-04-17 — [Soda Core release notes](https://docs.soda.io/soda-v4/release-notes/soda-core-release-notes); [Soda blog: Introducing Soda 4.0 (vendor)](https://soda.io/blog/introducing-soda-4.0)
- Licence: datacontract.com's comparison says Soda Core moved from Apache 2.0 to Elastic License 2.0 with v4. One tool directory still says Apache 2.0 (probably outdated). The official licence statement was not found — [datacontract.com comparison](https://docs.datacontract.com/comparison)

### Inferences
- The 2026 "standard" is fragmented. For this repo, Pandera schemas asserted as tests (already in place) plus the three leakage guards are stronger evidence than a GX/Soda bolt-on. A data contract per medallion layer (one Pandera schema for each of bronze, silver and gold) is the platform-looking upgrade, at zero RAM.
- GX's own data docs site could make a nice visual artifact, but it adds dependency weight for no new guarantees.

### Gaps
- No evidence was found on Pandera's 2026 release status in this pass (not searched).
- The Soda licence change needs confirming from the GitHub LICENSE file.

## 4. Lineage and catalog/discovery

### Takeaway
OpenMetadata and DataHub are far too heavy for a ~1GB spare budget: they officially need 16GiB and 8GB respectively. OpenLineage (the spec) is active (1.51/1.52 in 2026). Marquez is the reference lineage server, but its stock compose includes OpenSearch, which is the RAM hog. Lightweight paths are: Marquez without search, emitting OpenLineage to a file/console, or leaning on MLflow plus Iceberg snapshot metadata as the lineage record.

### Cited Findings
- OpenMetadata minimum: 4 vCPU / 16 GiB memory for the server plus MySQL/Postgres, and ElasticSearch/OpenSearch at 2 vCPU / 8 GiB per node **[official]** — [OpenMetadata minimum requirements](https://docs.open-metadata.org/latest/deployment/minimum-requirements); [production requirements v2.0.x](https://docs.open-metadata.org/v2.0.x/deployment/production-ready-requirements)
- DataHub quickstart tested config: 2 CPUs, 8GB RAM, 2GB swap **[official]**. A forum user reports a v0.12.1 local Docker setup using "a little more than 5GB" **[forum, measured by user]** — [DataHub quickstart](https://datahubproject.io/docs/quickstart); [DataHub troubleshooting](https://docs.datahub.com/docs/troubleshooting/quickstart); [DataHub forum](https://forum.datahubproject.io/t/recommended-vm-specs-for-deploying-datahub-for-a-poc/755)
- OpenLineage 1.51.0 (2026-07-06) added an OSS Unity Catalog handler and fully qualified UC symlinks. 1.52.0 is listed as latest — [OpenLineage 1.51.0 release notes](https://openlineage.io/docs/releases/1_51_0)
- Marquez: a GitHub discussion shows exit 137 (OOM) caused by its OpenSearch container. The suggested fix was more memory or disabling the search container **[forum]** — [Marquez discussion #3068](https://github.com/MarquezProject/marquez/discussions/3068)
- Ilum publishes a Marquez fork with a backend "rewritten from Java [in Rust] for lower latency and memory footprint" (vendor claim). Tags 0.54.0 and 0.54.0-java exist. Images are ~185MB (0.53.0) vs ~269MB (0.50.0) compressed, which is not RAM — [Docker Hub ilum/marquez](https://hub.docker.com/r/ilum/marquez)
- Snowflake Horizon stitches lineage from query history, external logs, BI and OpenLineage feeds into a column-level graph. Airflow can post OpenLineage events to a Snowflake endpoint (vendor docs) — [Snowflake Horizon Context](https://docs.snowflake.com/en/user-guide/snowflake-horizon/horizon-context)

### Inferences
- OpenLineage is the portable "Unity Catalog lineage" equivalent. Airflow and Dagster both have OpenLineage integrations (not re-verified here). Emitting events costs nothing; storing and viewing them is where RAM goes.
- Marquez API + Postgres without OpenSearch is plausibly a few hundred MB **[inference, not measured]**. It is borderline within ~1GB spare and could reuse GraphGuard's MLflow Postgres (separate DB) to avoid a second Postgres.
- On a 1GB budget, the best value is probably to record lineage as data. Write OpenLineage JSON events to an Iceberg/Parquet "audit" table, link the MLflow run to Iceberg snapshot ids, and show it in a notebook. Then show a Marquez screenshot from a temporary run rather than keeping it resident.

### Gaps
- No measured upstream Marquez RAM figure was found.
- The Unity Catalog OSS lineage feature set (vs Databricks UC) was not confirmed.
- Upstream Marquez's latest release version and date were not confirmed.

## 5. Governance: row/column access, tags, audit — open catalogs vs extra tooling

### Takeaway
Open Iceberg REST catalogs (Lakekeeper, Polaris, Unity OSS) govern **which tables/namespaces** a principal may touch, plus credential vending. None of the sources show them giving Snowflake-style row-access or masking policies enforced across engines. Those need an engine-side layer, or they get faked with gold-layer views.

### Cited Findings
- Snowflake Horizon: masking and row-access policies are "enforced across any Iceberg REST Catalog-compatible engine". Tag-based masking attaches policies to tags, e.g. DATA_CLASSIFICATION='PII' auto-masks (vendor docs) — [Snowflake Horizon Catalog](https://docs.snowflake.com/en/user-guide/snowflake-horizon); [Snowflake Horizon governance guide](https://snowflake.com/en/developers/guides/getting-started-with-horizon-for-data-governance-in-snowflake/)
- Snowflake audit: ACCESS_HISTORY in ACCOUNT_USAGE. Retention of "a year" is a third-party claim — [Versent (3rd-party)](https://versent.com.au/blog/snowflake-data-governance-overview); [Snowflake eng blog](https://www.snowflake.com/en/engineering-blog/cortex-code-governance-skills)
- Lakekeeper uses OpenFGA as its default fine-grained authorizer, and OpenFGA ships in its compose/Helm. Other authorizers can be plugged in via the `Authorizer` trait. A Cedar authorizer is commercial-only (Lakekeeper+) — [Lakekeeper GitHub](https://github.com/lakekeeper/lakekeeper); [Lakekeeper docs](https://docs.lakekeeper.io/)
- Apache Polaris 1.2 added finer-grained privileges for individual table-update operations (previously broad, e.g. TABLE_WRITE_PROPERTIES). 1.5 added pluggable authorization. A 1.6.0 release exists. Polaris access-control docs still say privileges are granted at catalog level with no fine-grained access, which is probably stale — [Snowflake blog: Polaris 1.2 (vendor)](https://www.snowflake.com/en/blog/engineering/apache-polaris-1-2-release/); [Snowflake blog: Polaris 1.5 (vendor)](https://www.snowflake.com/en/blog/engineering/apache-polaris-1-5-release/); [Polaris access control docs](https://polaris.apache.org/docs/access-control); [Polaris 1.6.0 release index](https://polaris.apache.org/releases/1.6.0/index.xml)
- Unity Catalog OSS implements the Iceberg REST catalog API. A wiki-style page lists 0.4.0 as released 2026-02-14 (unverified). Databricks' Data+AI Summit 2026 post covers Iceberg REST scan planning needing Iceberg ≥1.11 — [Databricks: Year of interoperability](https://www.databricks.com/blog/year-interoperability-how-enterprises-are-scaling-governance-unity-catalog); [Databricks: What's new in UC, DAIS 2026](https://www.databricks.com/blog/whats-new-unity-catalog-data-ai-summit-2026); [everybodywiki (weak)](https://en.everybodywiki.com/Unity_Catalog)
- Feast's blog notes that OSS Unity Catalog has no credential vending, and REST reads need a `uniform_iceberg_metadata_location` setting in its H2 DB, so Feast recommends the SQL catalog for that setup — [Feast blog, 2026-07-18](https://feast.dev/blog/feast-unity-catalog-integration)

### Inferences
- Lakekeeper is a single Rust binary plus Postgres. Its OpenFGA authz is the closest open analogue to Unity Catalog grants, and the most "platform-looking" governance for little RAM **[inference, no measured figure found]**. Polaris is a JVM (Quarkus) service and probably heavier **[inference]**.
- Column masking/row filters: the honest single-box approach is gold-layer views (e.g. hashed account ids for the UI) plus a written policy doc. Real cross-engine masking (Horizon-style) is not available in open catalogs per these sources.
- Audit: the catalog's own event logs (Polaris 1.2 mentions event persistence in a Dremio post title, not verified) or Iceberg snapshot history (`snapshots` metadata table) give a "who changed what when" record.

### Gaps
- No measured RAM for Lakekeeper, Polaris, or Unity OSS.
- Whether Lakekeeper or Polaris offer column-level masking or row filters in 2026 is not confirmed (I found no evidence that they do).

## 6. Notebooks / SQL UI

### Takeaway
DuckDB's built-in UI (`duckdb -ui`) is the closest zero-cost analogue to a Snowflake worksheet. marimo (reactive, stored as plain .py, DuckDB-integrated) is the closest to a Databricks notebook that is also git- and CI-friendly. Superset and Metabase are real BI servers with official/forum floors of 1–8GB, which is overkill here.

### Cited Findings
- DuckDB UI: start with `duckdb -ui` or `CALL start_ui();`. Notebook cells run SQL, data stays local (MotherDuck opt-in), notebooks are saved in `ui.db`, and the UI does not support read-only databases — [DuckDB UI docs](https://duckdb.org/docs/current/core_extensions/ui); [DuckDB blog: Local UI (2025-03-12)](https://duckdb.org/2025/03/12/duckdb-ui.html)
- marimo: an open-source reactive notebook for Python and SQL, tightly integrated with DuckDB. `pip install "marimo[sql]"`. Notebooks are plain Python, git-friendly and runnable as scripts — [DuckDB guide: marimo](https://duckdb.org/docs/current/guides/python/marimo)
- Metabase: the floor is 1 CPU / 1GB RAM per staff and vendor guidance. One user found a 1GB container gave the JVM only ~247MB. A community suggestion is 8GB for general use **[forum]** — [Metabase forum: minimum resources](https://discourse.metabase.com/t/what-are-metabase-minimum-resources/21470); [Metabase forum: docker memory](https://discourse.metabase.com/t/metabase-memory-usage-on-docker/25583)
- Superset: 8GB RAM for a single-host evaluation with Postgres and Redis on the same machine (Canonical docs) — [Canonical: Superset system requirements](https://canonical-data-mesh-documentation.readthedocs-hosted.com/en/latest/reference/superset/system-requirements/)

### Inferences
- JupyterLab works but stores JSON with outputs, which is noisy in git. marimo fits the repo's "reproducible from clean clone" rule better and can run in CI as a script.
- Evidence (markdown+SQL static BI) builds static HTML. It would have ~0 runtime RAM if served by the existing nginx/Caddy **[inference; not researched in this pass]**.
- DuckDB UI and marimo should run on demand over an SSH tunnel, not as resident services. That keeps them at 0 resident MB.

### Gaps
- No measured RAM for marimo, JupyterLab, DuckDB UI or Evidence.
- Evidence's 2026 status/licence was not checked.

## 7. Orchestration: Airflow 3.x vs Dagster vs Prefect

### Takeaway
Airflow 3 officially recommends ≥4GB RAM, which is the whole project budget. Dagster's software-defined assets fit a lakehouse best (each Iceberg table is an asset with lineage, partitions and checks). Prefect announced the acquisition of Dagster Labs on 2026-07-13, with Dagster's name, OSS licence and roadmap said to continue. This is a material 2026 change to note in any write-up.

### Cited Findings
- Airflow 3.1 prerequisites: "at least 4GB of RAM" recommended, actual needs depend on deployment. Python 3.10–3.13 and Postgres 13–17 are tested. Docs exist up to 3.3.1 **[official]** — [Airflow 3.1.0 prerequisites](https://airflow.apache.org/docs/apache-airflow/3.1.0/installation/prerequisites.html); [Airflow 3.3.1 prerequisites](https://airflow.apache.org/docs/apache-airflow/3.3.1/installation/prerequisites.html)
- Dagster 1.13 (latest patch seen: 1.13.21) is framed around easier adoption and scale. 1.13.21 fixed a Postgres connection leak that could exhaust the webserver pool — [Dagster 1.13 blog](https://dagster.io/blog/dagster-1-13-octopuss-garden); [Dagster 1.13.21 release](https://newreleases.io/project/github/dagster-io/dagster/release/1.13.21)
- Prefect is acquiring Dagster Labs (announced 2026-07-13, terms undisclosed). Dagster and Dagster+ keep their names, OSS licence and roadmap. The founders become advisors. The closing date is unclear: the Dagster site carries a "Dagster is now part of Prefect" banner, while a 2026-11-06 Orchestra guide found no closing announcement — [Dagster blog: Prefect is acquiring Dagster](https://dagster.io/blog/prefect-is-acquiring-dagster); [Dagster customer FAQ](https://dagster.io/dagster-customer-faq); [The New Stack](https://thenewstack.io/prefect-acquires-dagster-orchestrator/); [Orchestra guide](https://www.getorchestra.io/guides/dagster-acquisition)
- An older community thread reports a Dagit pod's memory creeping on k8s **[forum, pre-1.12]** — [Dagster discuss](https://discuss.dagster.io/t/2646312/hi-team-wave-we-have-recently-deployed-dagster-to-our-k8s-cl)

### Inferences
- Dagster's webserver plus daemon with a Postgres storage (reusing MLflow's Postgres instance) is commonly assumed to run in roughly 0.5–1GB **[inference; no official or measured figure found]**. That is tight but feasible within ~1GB spare, and it must be measured before committing, as was done for MLflow.
- Airflow 3 at the official 4GB recommendation is overkill for one retraining DAG on this box. Prefect's server is also an option, but its asset model is weaker than Dagster's for lakehouse tables **[inference]**.
- Given the acquisition, the write-up should say "Dagster (OSS, Apache 2.0; Prefect-owned since 2026)" or similar, once the close is verified.

### Gaps
- No measured RAM for Dagster 1.13, Airflow 3.x minimal (standalone / LocalExecutor) or Prefect 3 server.
- The deal-close date is unverified.

## 8. Feature store on a lakehouse

### Takeaway
Feast 0.64+ (blog dated 2026-07-18) has native Iceberg offline-store support via DuckDB (in-process) or Spark, through PyIceberg, with REST/SQL/Hive/Glue catalogs. It is read-only: Feast cannot write features back to Iceberg or create tables. Databricks Feature Engineering in UC does point-in-time joins via `timeseries_columns` and serves online from Lakebase. The open equivalent is Feast DuckDB-offline → Redis-online.

### Cited Findings
- Feast native Iceberg: `pip install "feast[iceberg]"`, Feast ≥0.64. DuckDB and Spark offline stores support `feast apply`, `get_historical_features`, `materialize`/`materialize-incremental` and `get_online_features`. Catalog types are `rest` (Unity Catalog, Polaris, Nessie, Snowflake Open Catalog), `sql`, `hive`, `glue` and `dynamodb`. Lakekeeper is not named, but it is a REST catalog. There is no write-back (`write_to_offline_store` supports only FileSource/SparkSource) and no table creation — [Feast blog, 2026-07-18](https://feast.dev/blog/feast-unity-catalog-integration)
- Feast's DuckDB offline store supports point-in-time correct `get_historical_features` over Parquet/Delta FileSources — [Feast docs: DuckDB offline store](https://docs.feast.dev/reference/offline-stores/duckdb)
- Feast v0.68.0 exists (DuckDB lazily scans Lance sources). A third-party radar says v0.62–0.66 shipped Apr–Aug 2026 — [Feast v0.68.0 release](https://newreleases.io/project/github/feast-dev/feast/release/v0.68.0); [rubinlake radar (3rd-party)](https://rubinlake.com/es/technology-radar/data-platforms-and-mlops/feast)
- A 2026-08 third-party write-up warns that point-in-time SQL differs by provider and contributed integrations vary in maturity, citing duplicates and late rows — [OneUptime blog](https://oneuptime.com/blog/post/2026-08-15-feast-point-in-time-duplicates-late-rows/view)
- Databricks: point-in-time logic needs `timeseries_columns` (UC) / `timestamp_keys` (legacy). It matches the latest value before the lookup timestamp, does not skip null feature values, is unrelated to Delta time travel, and Liquid Clustering is recommended. The online store is powered by Lakebase (vendor docs) — [Databricks: point-in-time feature joins](https://docs.databricks.com/aws/machine-learning/feature-store/time-series); [Databricks: feature store concepts](https://docs.databricks.com/aws/machine-learning/feature-store/concepts)

### Inferences
- For GraphGuard's leakage contract, Feast's PIT join gives a second, independent check. Compute gold features in Polars (as-of semantics already guarded), then assert that Feast `get_historical_features` returns byte-identical values for a sample. That is a train/serve-parity test that reads like a platform feature.
- The "latest value strictly before the timestamp" semantics must be checked against GraphGuard's rule on same-timestamp transactions (`<` vs `<=`). This is a classic leakage edge. Neither Databricks' nor Feast's docs above settle tie-handling explicitly.
- Feast is a library plus registry file. It needs no resident server unless the feature server is used, so the cost is ~0 RAM beyond the existing Redis **[inference]**.

### Gaps
- Feast Iceberg PIT tie-breaking and late-row semantics were not confirmed from primary docs.
- Whether Feast's Redis online store works with an Iceberg source end-to-end was not shown in the blog (its examples use SQLite).

## 9. ML on the lakehouse: MLflow 3 registry + lineage to Iceberg snapshots

### Takeaway
MLflow 3 (latest seen 3.8.x) has `mlflow.log_input` dataset tracking and LoggedModel lineage. Metrics can be tied to a model_id and a dataset, and logged models can be searched by dataset name/digest. There is no native Iceberg loader. The standard pattern is to log the Iceberg table name plus snapshot id as a dataset source/tag, which recreates Databricks' UC table→model lineage by convention.

### Cited Findings
- `mlflow.log_input(dataset, context=...)` records source, schema, digest and profile in the UI — [MLflow dataset tracking docs](https://mlflow.org/docs/latest/ml/dataset/)
- LoggedModel (MLflow 3) links models, runs, traces and evaluation metrics. `log_metric` accepts `model_id` and `dataset`, and `search_logged_models` can filter on dataset name and digest — [Databricks: MLflow Logged Models](https://docs.databricks.com/aws/mlflow/logged-model); [MLflow 3 docs](https://mlflow.org/docs/3.0.1/mlflow-3)
- MLflow 3.8.0 and 3.8.1 are released (fixes incl. dataset filters in run search) — [MLflow 3.8.0](https://mlflow.org/releases/3.8.0/); [MLflow 3.8.1](https://mlflow.org/releases/3.8.1/)
- On Databricks, table→model lineage uses `mlflow.log_input` (≥2.11) and shows on the model version's Lineage tab. There is no built-in way to log output tables — [Databricks community](https://community.databricks.com/t5/machine-learning/table-model-lineage-for-models-without-online-feature-lookups/m-p/137259); [Databricks KB](https://backiee.wasmer.app/https_kb_databricks_com/en_US/machine-learning/lineage-for-the-output-table-with-predictions-is-not-tracked-in-mlflow-when-training-a-model)
- Pattern: log the Iceberg snapshot_id as a run param, then time-travel to it to reproduce the data (vendor blog). Cloudera shows logging snapshot and parent ids per run — [Dremio blog (vendor)](https://www.dremio.com/blog/apache-iceberg-machine-learning-solving-data-versioning-for-ai/); [Cloudera community](https://community.cloudera.com/t5/Community-Articles/Logging-Iceberg-Metrics-with-MLFlow-Tracking-in-CML/ta-p/385657)
- A 2026 blog's `load_from_iceberg` helper is not part of MLflow (illustrative only) — [datalakehousehub](https://datalakehousehub.com/blog/2026-05-mlflow-data-pipelines)
- Locally measured: GraphGuard's MLflow (2.19) idles at ~695MB, capped at 1200M, with Postgres capped at 512M **[measured locally]** — `/srv/graphguard/CLAUDE.md`

### Inferences
- Upgrading MLflow 2.19 → 3.x gives LoggedModel/dataset-scoped metrics, but it is a server upgrade with DB migrations. Measure idle RAM after upgrading, because 695MB is already the largest resident cost in the project.
- Training-set versioning = (silver snapshot id, gold snapshot id, frozen_split.json sha256, code git sha) logged on every run. This ties directly to the repo's existing determinism and split-integrity guards. It is the highest platform value per MB (zero RAM) in this whole list.

### Gaps
- What changed in MLflow 3.6/3.7 was not confirmed. Whether a 3.x dataset source type for Iceberg exists natively was not found.

## 10. Most platform value per MB on one box; what is overkill

### Takeaway
High value at ~0 resident RAM: medallion namespaces, snapshot-id lineage into MLflow, Pandera contracts per layer, the Feast PIT parity check, and marimo/DuckDB UI on demand. Worth a measured trial within ~1GB: the Lakekeeper catalog (Rust) and Dagster (assets = lakehouse tables), probably sharing the existing Postgres. Overkill: OpenMetadata (16GiB), DataHub (8GB), Superset (8GB eval), Airflow 3 (4GB recommended), and resident Marquez with OpenSearch.

### Cited Findings
- OpenMetadata 16GiB, DataHub 8GB+2GB swap, Superset 8GB eval, Airflow ≥4GB recommended, Metabase 1GB floor — see the sources in sections 4, 6 and 7: [OpenMetadata](https://docs.open-metadata.org/latest/deployment/minimum-requirements), [DataHub](https://datahubproject.io/docs/quickstart), [Superset/Canonical](https://canonical-data-mesh-documentation.readthedocs-hosted.com/en/latest/reference/superset/system-requirements/), [Airflow](https://airflow.apache.org/docs/apache-airflow/3.1.0/installation/prerequisites.html), [Metabase forum](https://discourse.metabase.com/t/what-are-metabase-minimum-resources/21470)
- Box context: swap ~99% full, project budget ~4GB, every container hard-capped **[local]** — `/srv/graphguard/CLAUDE.md`

### Inferences
Proposed mapping table (RAM: O = official, F = forum, M = measured, I = inference):

| Databricks / Snowflake capability | Open-source pick for one box | Maturity / licence (Nov 2026) | Resident RAM |
|---|---|---|---|
| Delta/Iceberg tables, medallion | Iceberg + PyIceberg/DuckDB/Polars, 3 namespaces | Iceberg mature; DuckDB writes MoR-only | 0 (libraries) [I] |
| Unity Catalog / Horizon / Polaris catalog | Lakekeeper (+OpenFGA) or Polaris | Lakekeeper 0.x; Polaris 1.6 (incubating→ASF) | unmeasured; Lakekeeper likely smallest [I] |
| Row/column masking, tag policies | Gold views + policy doc | no open cross-engine equivalent found | 0 |
| Lineage (UC lineage / Horizon) | OpenLineage events → table; MLflow snapshot tags; Marquez only on demand | OpenLineage 1.52 | 0 resident; Marquez+OpenSearch heavy [F] |
| Catalog/discovery UI | skip OpenMetadata/DataHub | mature but heavy | 16GiB [O] / 8GB [O] |
| DLT / Declarative Pipelines, dbt | Python assets; optional SQLMesh (LF) or dbt-core 1.x | licence nuance post-merger | 0 (CLI) [I] |
| Expectations / DQ | Pandera (existing) | GX 1.24.1 (Fivetran-stewarded); Soda 4 ELv2 | 0 |
| Workflows / Jobs | Dagster (assets) | 1.13.x, Prefect acquiring | ~0.5–1GB [I], measure first |
| Notebooks / worksheets | marimo, DuckDB UI (on demand) | active | 0 resident |
| AI/BI dashboards | Evidence static site or marimo app | — | ~0 [I] |
| Feature Engineering in UC + Lakebase online | Feast (DuckDB offline on Iceberg) → Redis | Feast 0.68; Iceberg since 0.64 | 0 + existing Redis |
| MLflow on Databricks / UC models | MLflow (existing) + snapshot-id lineage | 3.8.x available; repo on 2.19 | 695MB [M] |
| Lakehouse Monitoring | Evidently reports as Iceberg tables | not researched here | — |

- Ranking for "platform value per MB": (1) snapshot-id lineage + medallion + per-layer contracts; (2) Feast PIT parity test; (3) Lakekeeper catalog with OpenFGA grants (looks like Unity Catalog in a demo); (4) Dagster asset graph (the visual lineage UI people associate with a platform, and it doubles as the retraining DAG); (5) marimo worksheets. Everything with a search cluster (OpenSearch/Elasticsearch) is out.

### Gaps
- None of the candidate resident services (Lakekeeper, Polaris, Dagster, Marquez-no-search, MinIO/Garage) had a credible measured idle RAM figure in sources found. All need a local capped measurement, as was done for MLflow, before committing.
- Evidently and Kafka/Redpanda footprints are outside this note's scope and were not researched.
