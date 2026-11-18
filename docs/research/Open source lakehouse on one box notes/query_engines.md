# Query and compute engines for a one-box Iceberg lakehouse (as of 2026-11-18)

Context: GraphGuard-AI. One shared server (8 cores, ~19 GB free box-wide, project budget ~4 GB with ~1 GB spare). 5M AML transactions now (~500 MB CSV), 180M later. Feature pipeline is in Polars (`uv.lock` pins **polars 1.43.2**, checked locally 2026-11-18; DuckDB, PyIceberg, PySpark and Daft are **not** in the lockfile yet).

Labels used: **[measured]** = a number someone measured and published; **[documented]** = a default or limit from official docs; **[estimate]** = my inference, no source measured it; **[from knowledge]** = a well-known doc fact I did not re-fetch in this session (the report writer should spot-check these).

---

## Q1. Engine-by-engine: version, Iceberg read/write/merge, catalogs, RAM floor, maturity

### Takeaway
Three engines can do real Iceberg writes in-process with no JVM: **DuckDB 2.0** (INSERT/UPDATE/DELETE/MERGE INTO via REST catalog, merge-on-read only), **PyIceberg 0.12** (append/overwrite/upsert, expire snapshots, no compaction), and **Polars** (append/overwrite only, marked unstable, goes through PyIceberg). JVM engines (Trino, Spark) are the complete ones, especially for compaction, but they cost more than 1 GB to run comfortably.

### Cited Findings

**DuckDB (iceberg core extension)**
- Latest: **DuckDB 2.0.0 LTS "Cinnamon Teal", announced 2026-10-21**, LTS until at least October 2027. Built from about 20,000 commits since 1.5. — [DuckDB 2.0.0 announcement](https://duckdb.org/2026/10/21/announcing-duckdb-200)
- Other active lines: 1.5.0 (2026-03-09), 1.5.4 (2026-06-17), 1.4.5 LTS (2026-06-17; 1.4 supported until late Nov 2026). — [DuckDB 1.5.0](https://duckdb.org/2026/03/09/announcing-duckdb-150.html), [DuckDB 1.4.5](https://duckdb.org/2026/06/17/announcing-duckdb-145.html), [DuckDB 1.5.4](https://duckdb.org/2026/06/17/announcing-duckdb-154.html)
- Write history: INSERT arrived in v1.4.0. DELETE and UPDATE on v2 tables arrived in v1.4.2 (blog post dated 2025-11-28). — [Writes in DuckDB-Iceberg](https://duckdb.org/2025/11/28/iceberg-writes-in-duckdb)
- In the 2.0 docs, with a **REST catalog ATTACHed**, these work: INSERT INTO, UPDATE, DELETE, **MERGE INTO** (recommended for upserts; `WHEN MATCHED THEN DELETE` supported), CREATE/DROP SCHEMA, CREATE/DROP TABLE, ALTER TABLE (rename, add/rename/drop/retype columns, defaults, format-version). Partitioning via `PARTITIONED BY` with identity, year/month/day/hour, bucket, truncate. UPDATE/DELETE work on partitioned and unpartitioned tables. — [DuckDB 2.0 docs: Writing to Iceberg](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- Conflict: the **LTS** REST-catalog doc page says UPDATE/DELETE only work on tables that are not partitioned and not sorted. That probably describes the 1.4 LTS line; the 2.0 page lifts it. — [DuckDB LTS docs: Iceberg REST Catalogs](https://duckdb.org/docs/lts/core_extensions/iceberg/iceberg_rest_catalogs) vs [2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- **Merge-on-read only.** It writes positional deletes (v2) or binary deletion vectors in Puffin files (v3). Copy-on-write is not supported. If `write.update.mode` / `write.delete.mode` is anything else, the operation fails. — [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- Writes need a catalog: you cannot write to a table opened with `iceberg_scan` (path-based), because "the catalog is required to commit the new table metadata." — [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- Iceberg v3 read+write: VARIANT, TIMESTAMP_NS, column defaults, deletion vectors, row lineage. GEOGRAPHY is not supported. — [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- 2.0 adds REST ATTACH options (derive table location from namespace, load metadata from the catalog's `metadata-location`, URL prefix, namespace separator). The release says the extension "strives to become a feature-complete implementation." 2.0 also ships a server mode (Quack protocol, `-serve`/`-connect`, listens on localhost by default). — [DuckDB 2.0.0 announcement](https://duckdb.org/2026/10/21/announcing-duckdb-200)
- **Maintenance:** an October 2026 write-up testing DuckDB 1.5.6 says the extension's function list "has no compaction or expiry call". The 2.0 writing docs don't mention maintenance either. — [Hikmah Technologies, Iceberg table maintenance](https://hikmahtechnologies.com/blog/iceberg-table-maintenance/); [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- Catalogs: the writing docs only list REST for writes. Glue, S3 Tables and Polaris all expose REST endpoints, so they are reached through REST ATTACH. — [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html) (no SQL/JDBC catalog support documented)
- RAM: DuckDB is in-process and honours `SET memory_limit`. Its default is 80% of system RAM, and it spills to disk above the limit **[from knowledge; DuckDB docs "Configuration" / "Memory management"]**. No published Iceberg-specific measured floor found.

**PyIceberg**
- Latest: **0.12.0, 2026-09-01** (0.11.1 March 2026, 0.11.0 Feb 2026, 0.10.0 Sep 2025, 0.9.0 Mar 2025). — [PyPI](https://pypi.org/project/pyiceberg/), [GitHub releases](https://github.com/apache/iceberg-python/releases)
- Upsert added in **0.9.0**. 0.9.1 fixed null handling. 0.10.0 stopped empty upsert snapshots. It uses PyArrow compute to match rows, with no query engine. — [GitHub releases](https://github.com/apache/iceberg-python/releases), [PR #1534](https://github.com/apache/iceberg-python/pull/1534)
- **Upsert RAM warning [measured, user report]:** a March 2026 discussion reports upserts rewrite files copy-on-write style, and a 34M-row upsert used ~80 GB RAM. — [Discussion #3118](https://github.com/apache/iceberg-python/discussions/3118)
- Maintenance: 0.12.0 has `table.maintenance.expire_snapshots()`. It has **no data-file compaction and no orphan-file removal**. The tester saw expiry drop snapshots from metadata but leave data files on disk, and swept orphans by hand. — [Hikmah Technologies](https://hikmahtechnologies.com/blog/iceberg-table-maintenance/). The compaction work (`table.maintenance.compact()`, `replace()` API) is in issue #1092 with March 2026 commits, still open. — [Issue #1092](https://github.com/apache/iceberg-python/issues/1092). Conflict: RisingWave claims a `rewrite_data_files()` API "since 0.7". That contradicts the sources above and is likely wrong. — [RisingWave](https://risingwave.com/blog/apache-iceberg-streaming-2026/)
- Catalogs: REST, Hive (Kerberos), SQL (SqlCatalog over SQLite/Postgres; InMemoryCatalog is a subclass), Glue (incl. S3 Tables federated DBs in 0.12). — [GitHub releases](https://github.com/apache/iceberg-python/releases)
- v3: read support from 0.9, deletion vectors read in 0.10, row lineage 0.11, geo types 0.12. — [GitHub releases](https://github.com/apache/iceberg-python/releases)
- A Jan 2026 Daft forum post says Daft and PyIceberg both don't support merge-on-read writes. — [Daft community](https://linen.getdaft.io/c/daft-dev)

**Polars**
- Repo pins 1.43.2. Polars 1.44 (Aug 2026) blog says the **native** `scan_iceberg` reader now handles a table layout that used to force a fallback to PyIceberg. — [Polars 1.44 post](https://pola.rs/posts/polars-1-44)
- `scan_iceberg(reader_override='native'|'pyiceberg')`: the docs say the override is for testing, and Polars picks the best reader automatically. — [Polars docs: scan_iceberg](https://docs.pola.rs/api/python/dev/reference/api/polars.scan_iceberg.html)
- `DataFrame.write_iceberg(target, mode)`: mode is `append` or `overwrite`, target is a table name or a `pyiceberg.table.Table`. It is **marked unstable**. Required fields can't hold nulls, and nested required fields aren't supported. **No merge/upsert.** — [Polars docs: write_iceberg](https://docs.pola.rs/api/python/dev/reference/api/polars.DataFrame.write_iceberg.html)
- Third-party blogs say Polars' streaming engine gained Iceberg sinks in 2026. Not confirmed in official docs. — [datalakehousehub, DuckDB+Polars on Iceberg (May 2026)](https://datalakehousehub.com/blog/2026-05-duckdb-polars-iceberg/)
- Catalogs: through PyIceberg (so REST/SQL/Glue/Hive). **[inference from the target type]**

**Trino**
- Latest confirmed on trino.io: **483 (2026-07-17)** (PIVOT clause, encrypted Parquet reads for Iceberg). 482 came 2026-06-25, 481 on 2026-05-11, 480 on 2026-03-24. One unofficial Japanese blog says 484 shipped 2026-10-15. Unverified. — [Trino 483](https://trino.io/docs/current/release/release-483.html), [Trino 480](https://trino.io/docs/current/release/release-480), [issoh.co.jp](https://www.issoh.co.jp/md/tech/5545)
- Iceberg: 480 added v3 create/write/delete, plus v3 support in `optimize`, `expire_snapshots`, `remove_orphan_files`. 479 added `retain_last` and `clean_expired_metadata` to expire_snapshots. — [Trino 480](https://trino.io/docs/current/release/release-480), [Trino 479](https://trino.io/docs/current/release/release-479)
- MERGE is documented for Trino, generally copy-on-write for matched rows (Dremio matrix, checked 2026-10-27; Dremio is a vendor). — [Dremio DML matrix](https://www.dremio.com/blog/apache-iceberg-dml-support-matrix-merge-update-delete-and-branch-writes-by-engine/)
- Catalogs: Hive metastore, JDBC, REST, Glue, Nessie, Snowflake **[from knowledge, Trino Iceberg connector docs]**. JDBC is confirmed in Starburst docs, so HMS is not mandatory. — [Starburst Iceberg connector](https://dell.starburst.io/413-e/connector/iceberg.html)
- RAM: **no official minimum found.** A "lightweight Trino" article caps query memory at 1000 MB as an example. — [DZone](https://dzone.com/articles/building-a-lightweight-trino-distribution). The default `query.max-memory-per-node` is 0.3 × JVM heap. — [Acceldata capacity planning](https://documentation.acceldata.io/p/11808/trino-capacity-planning). Production guides use 64 GB per node. — [Cloudera tuning](https://docs.cloudera.com/cdw-runtime/1.5.5/trino-performance-tuning/trino-performance-tuning.pdf). **[estimate]** A coordinator-as-worker on a 2 GB heap is the realistic floor for anything more than toy queries, which by itself blows the 1 GB spare.

**Apache Spark 4.x**
- Spark **4.1.0** (Dec 2025): Spark ML on Connect GA for Python, a JDBC driver for Spark Connect, Arrow UDTFs. 4.1.x patches continue (endoflife.ai lists 4.1.3), and a 4.2 line exists. — [Spark 4.1.0 release notes](https://spark.apache.org/releases/spark-release-4.1.0.html), [endoflife.ai](https://endoflife.ai/apache-spark/4.1)
- Iceberg runtime: **1.10.x supports Spark 4.0** (`iceberg-spark-runtime-4.0_2.13:1.10.1`, the quickstart's choice). For **Spark 4.1 use Iceberg 1.11.0 and `iceberg-spark-runtime-4.1_2.13`**. Mixing runtimes gives AbstractMethodError. — [Iceberg 1.10 (Snowflake eng blog)](https://www.snowflake.com/en/blog/engineering/apache-iceberg-1-10-new-features-fixes/), [Acceldata ODP Spark 4.1.1](https://docs.acceldata.io/odp/documentation/apache-spark-4-1-1)
- Spark is the reference implementation: MERGE/UPDATE/DELETE (copy-on-write by default) and all maintenance procedures (`rewrite_data_files`, `expire_snapshots`, `remove_orphan_files`, `rewrite_manifests`). — [Dremio DML matrix](https://www.dremio.com/blog/apache-iceberg-dml-support-matrix-merge-update-delete-and-branch-writes-by-engine/); procedures **[from knowledge, Iceberg Spark procedures docs]**
- RAM: `spark.driver.memory` defaults to 1g **[documented, from knowledge: spark.apache.org/docs/latest/configuration.html]**. Local mode runs everything in the driver JVM. **[estimate]** Realistic floor is ~1.5–2 GB RSS for the JVM plus Python worker processes, more with Spark Connect server + client. No measured figure found.

**Apache DataFusion / Comet**
- **Comet 1.0.0 released 2026-08-07**, on DataFusion 54.1 / Arrow 58.4. It reads Iceberg data files natively via iceberg-rust while Iceberg Java plans on the driver. It falls back to JVM for deletion vectors, v4 tables and non-Parquet. **Writes are not accelerated** ("Writes go through Spark"). Author works at Dremio (vendor-adjacent). — [datalakehousehub on Comet 1.0](https://datalakehousehub.com/blog/datafusion-comet-1-spark-iceberg)
- Comet is a Spark plugin, so it does not lower the Spark RAM floor; it speeds up scans. **[inference]**

**ClickHouse**
- Iceberg write timeline (third-party): INSERT in 25.7, CREATE TABLE + ALTER DELETE in 25.8, ALTER UPDATE + distributed writes in 25.9, on REST and Glue catalogs. — [BigData Boutique](https://bigdataboutique.com/blog/clickhouse-and-apache-iceberg-practical-guide-to-data-lakehouse-integration)
- March 2026: Iceberg database support still **beta**, needs `allow_database_iceberg=1`. — [ClickHouse: data lake ready](https://clickhouse.com/blog/clickhouse-is-data-lake-ready). Late 2026: writes to OneLake, S3, ADLS via DataLakeCatalog (vendor blog, dates inconsistent: Sep 28 / Nov 3 2026). — [ClickHouse writes to OneLake](https://clickhouse.com/blog/clickhouse-now-writes-to-microsoft-onelake)
- No GA confirmation for writes found. No MERGE. RAM floor not researched.

**Daft**
- `df.write_iceberg()` with idempotent `checkpoint=`. Uses merge_append or fast_append depending on table config. — [Daft Iceberg docs](https://docs.getdaft.io/en/stable/connectors/iceberg/). v0.7.6 came 2026-03-31. — [Daft blog](https://www.daft.ai/blog/daft-v076-o1-scalars-kafka-reads-and-a-full-observability-pipeline)
- No evidence of MERGE or merge-on-read writes (Jan 2026 forum post). — [Daft community](https://linen.getdaft.io/c/daft-dev)

**StarRocks / Doris**
- I found no usable 2026 sources on their Iceberg write/MERGE status or RAM floor in this session. See Gaps.

### Inferences
- For 5M rows (~500 MB CSV, likely ~100–200 MB Parquet), every in-process engine fits easily under a 1 GB cap with spill enabled. The JVM engines are the ones that don't fit.
- PyIceberg upsert's memory behaviour ([80 GB for 34M rows](https://github.com/apache/iceberg-python/discussions/3118)) makes it unfit for upserts at 180M rows on this box. Use DuckDB MERGE INTO or append-only design instead.

### Gaps
- No **measured** RAM floor for any engine doing Iceberg work on a single node was found. All JVM floors above are estimates.
- Trino 484 and Spark 4.2 release dates are unverified.
- StarRocks and Doris were not covered (search returned nothing relevant). From general knowledge, both are MPP servers (FE JVM + BE C++), recommended in GB-to-tens-of-GB per node, and support Iceberg read and INSERT via external catalogs. Unsourced, so the writer should verify or drop them.
- iceberg-rust / DataFusion standalone write status (outside Comet) not confirmed.

---

## Q2. Who can MERGE/upsert and do maintenance on Iceberg without Spark?

### Takeaway
**MERGE without Spark:** DuckDB 2.0 (MERGE INTO, merge-on-read), Trino (MERGE, copy-on-write), and PyIceberg (`upsert`, memory-hungry). **Full maintenance without Spark:** only **Trino** (`optimize`, `expire_snapshots`, `remove_orphan_files`). PyIceberg can only expire snapshots. DuckDB has none. So a small lakehouse without a JVM can write and merge, but it **cannot compact** except by rewriting the table.

### Cited Findings
- DuckDB: MERGE INTO / UPDATE / DELETE, merge-on-read only (creates delete files that need compacting later). — [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- DuckDB: no compaction or expiry function (as of 1.5.6, Oct 2026). — [Hikmah](https://hikmahtechnologies.com/blog/iceberg-table-maintenance/)
- PyIceberg: `upsert` (0.9+), `expire_snapshots` (0.12). No compaction or orphan removal; the workaround is overwriting the table with its own contents (all in memory). — [GitHub releases](https://github.com/apache/iceberg-python/releases), [Hikmah](https://hikmahtechnologies.com/blog/iceberg-table-maintenance/), [Issue #1092](https://github.com/apache/iceberg-python/issues/1092)
- One blog states compaction must run in Spark, Trino or DuckDB. The DuckDB part contradicts Hikmah and the DuckDB docs. — [Alex Merced blog (Aug 2026)](https://alexmerced.blog/blog/2026-08-25-serverless-iceberg-microbatch-pyiceberg-duckdb.html)
- Trino: `optimize`, `expire_snapshots` (with `retain_last`, `clean_expired_metadata`), `remove_orphan_files`, all v3-capable since 480. MERGE documented. — [Trino 480](https://trino.io/docs/current/release/release-480), [Trino 479](https://trino.io/docs/current/release/release-479), [Dremio matrix](https://www.dremio.com/blog/apache-iceberg-dml-support-matrix-merge-update-delete-and-branch-writes-by-engine/)
- ClickHouse: ALTER DELETE/UPDATE on Iceberg (beta). — [BigData Boutique](https://bigdataboutique.com/blog/clickhouse-and-apache-iceberg-practical-guide-to-data-lakehouse-integration)
- Polars and Daft: append/overwrite only. — [Polars docs](https://docs.pola.rs/api/python/dev/reference/api/polars.DataFrame.write_iceberg.html), [Daft docs](https://docs.getdaft.io/en/stable/connectors/iceberg/)
- Some REST catalogs run table maintenance server-side (e.g. Lakekeeper, Polaris, managed catalogs). **[from knowledge, unverified here; belongs to the catalog researcher's scope]**

### Inferences
- Practical one-box pattern: write **append-only** feature and transaction tables (no deletes means no delete files), run `expire_snapshots` from PyIceberg, and compact by occasional full overwrite. At 5M rows that is cheap. At 180M it is not, and that is where Spark or Trino run as a **batch job** (start, compact, stop) earns its place.

### Gaps
- Whether PyIceberg #1092 compaction merged after 0.12.0 (unreleased main) is unknown.

---

## Q3. Point-in-time / as-of joins for ML features

### Takeaway
DuckDB (`ASOF JOIN`) and Polars (`join_asof`) both have native as-of joins and fit the leakage contract ("feature as of decision time"). Spark has **no native SQL ASOF JOIN**: you use a window/range join or pandas-on-Spark `merge_asof`, which is slower and easier to get wrong. For GraphGuard, point-in-time features are mostly **rolling windows over the account's own past**, so window functions with strict `<` bounds matter as much as as-of joins.

### Cited Findings
- DuckDB `ASOF JOIN ... ON a.key = b.key AND a.ts >= b.ts` picks the latest matching row at or before the timestamp; supports inequality `>=, >, <=, <` and `USING` **[from knowledge: duckdb.org/docs/stable/guides/sql_features/asof_join]**
- Polars `DataFrame.join_asof(other, on=, by=, strategy='backward'|'forward'|'nearest', tolerance=, allow_exact_matches=)`. Both frames must be sorted on the key. `allow_exact_matches=False` gives strict "before" semantics **[from knowledge: docs.pola.rs polars.DataFrame.join_asof]**
- Spark: pandas API on Spark offers `merge_asof`; Spark SQL has no ASOF JOIN keyword **[from knowledge; verify]**. Databricks/Feature Store does point-in-time lookups via its own feature-table API **[from knowledge]**

### Inferences
- `allow_exact_matches=False` (Polars) and strict `>` (DuckDB) are the leakage-safe settings for contract rule 3. A same-timestamp transaction must not see itself. This is worth a unit test.
- The current Polars pipeline can stay as is. DuckDB as-of is the SQL-side equivalent for exploration and for checking train/serve parity.

### Gaps
- No 2026 benchmark comparing DuckDB vs Polars as-of join throughput was searched.

---

## Q4. What Databricks and Snowflake map to in open source; most realistic one-box "lakehouse"

### Takeaway
Databricks = Spark (+ Photon, a closed C++ vectorized engine) + Delta/Iceberg + Unity Catalog + Databricks SQL warehouses. The open-source stand-ins are **Spark 4.x (+ Comet/Gluten as the "Photon" analogue) + Iceberg + a REST catalog (Unity Catalog OSS, Polaris, Lakekeeper)**. Snowflake's engine is closed. Its open analogues are SQL-warehouse engines over Iceberg (Trino, or DuckDB at small scale), and its open catalog is Apache Polaris. On one box, **DuckDB + Polars/PyIceberg + a REST catalog** gives the real lakehouse shape (open tables, catalog, SQL + DataFrame engines, time travel) at a few hundred MB.

### Cited Findings
- Comet is explicitly compared to Photon, Gluten and RAPIDS as native accelerators under Spark. — [datalakehousehub on Comet 1.0](https://datalakehousehub.com/blog/datafusion-comet-1-spark-iceberg)
- Databricks Free Edition: serverless only, one SQL warehouse capped at **2X-Small**, max 5 concurrent job tasks, restricted outbound internet, **no commercial use**. Over-quota compute shuts down for the rest of the day (community-reported). — [Databricks Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations), [community thread](https://community.databricks.com/t5/get-started-discussions/resource-exhausted-i-cannot-work-with-a-serverless-in-my-free/td-p/154770)
- Snowflake supports managing Iceberg tables (catalog-linked / Horizon bidirectional writes). — [Snowflake docs](https://docs.snowflake.com/en/user-guide/tables-iceberg-manage.html), [Horizon bidirectional writes](https://datalakehousehub.com/blog/snowflake-horizon-catalog-bidirectional-iceberg-writes/)

### Inferences
- Interview-relevant mapping: "Delta Live Tables / notebooks" ≈ Polars/DuckDB pipelines, "Unity Catalog" ≈ REST catalog, "Photon" ≈ DuckDB-class vectorized C++ engine, "Databricks SQL" ≈ DuckDB server mode / Trino.
- DuckDB 2.0's server mode (Quack protocol) lets several clients share one DuckDB, which is closer to a "SQL warehouse" experience than embedded-only use. — [DuckDB 2.0.0](https://duckdb.org/2026/10/21/announcing-duckdb-200)

### Gaps
- No primary source compared Photon to open engines in benchmarks.

---

## Q5. Recommendation: 1–3 engines within ~1 GB now; how Spark enters later

### Takeaway
**Now (fits ~1 GB):** (1) **Polars** stays the feature-pipeline engine (reads with `scan_iceberg`, writes with `write_iceberg` append/overwrite). (2) **DuckDB 2.0** for SQL exploration, MERGE INTO and ASOF joins, capped with `memory_limit`. (3) **PyIceberg** as the catalog/maintenance library (create tables, expire snapshots, the SQL catalog if no REST server). Skip Trino, ClickHouse and StarRocks/Doris for now: they are long-running servers with JVM or MPP footprints and add nothing at 5M rows. **Spark later:** as an on-demand job, not a resident service. Either local mode on a rented box (or this box, briefly) for 180M-row builds and compaction, or Databricks Free Edition for a learning demo only (no commercial use, 2X-Small warehouse).

### Cited Findings
- DuckDB is the only non-JVM engine with MERGE INTO + partitioned UPDATE/DELETE on Iceberg (REST catalog required). — [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- PyIceberg supports a SQL catalog (SQLite/Postgres) with no extra server. — [GitHub releases](https://github.com/apache/iceberg-python/releases). Caveat: DuckDB writes need a REST catalog, so a **SQL-catalog-only setup blocks DuckDB writes**. DuckDB can still read via `iceberg_scan` on metadata paths. — [DuckDB 2.0 docs](https://duckdb.org/docs/2.0/core_extensions/iceberg/writing_to_iceberg.html)
- Compaction at scale needs Spark or Trino. — [Hikmah](https://hikmahtechnologies.com/blog/iceberg-table-maintenance/), [Trino 480](https://trino.io/docs/current/release/release-480)
- Spark 4.1 needs the Iceberg 1.11 `4.1_2.13` runtime; Spark 4.0 uses Iceberg 1.10.x. — [Acceldata ODP](https://docs.acceldata.io/odp/documentation/apache-spark-4-1-1), [Iceberg 1.10 blog](https://www.snowflake.com/en/blog/engineering/apache-iceberg-1-10-new-features-fixes/)
- Databricks Free Edition limits (above). — [Databricks docs](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)

### Inferences
- **Catalog choice drives engine choice:** if DuckDB writes are wanted, a lightweight REST catalog is needed (scope of the catalog researcher; Lakekeeper is Rust and small). If only Polars/PyIceberg write, PyIceberg's SQL catalog on GraphGuard's own Postgres is enough.
- Leakage-contract fit: Iceberg snapshot time travel (`snapshot_id` / `as of`) lets a frozen split pin the exact table version a model trained on. That is a reproducibility win worth recording in MLflow.
- Spark entry plan: write the 180M feature build in PySpark against the same Iceberg tables and REST catalog. Run it either in local mode with `spark.driver.memory` set explicitly inside a capped container, started and stopped per job (doing so needs Lubo's approval under the box rules), or on a rented box. Use Databricks Free Edition only as a résumé or learning demo. Its non-commercial clause and quotas make it unsuitable as the real pipeline.
- Keep the memory cap rule: DuckDB `SET memory_limit='768MB'` plus a temp directory for spill, and Polars streaming engine for 180M-row scans. **[estimate]**

### Gaps
- No measured footprint for DuckDB or Polars on this exact dataset. Recommend measuring peak RSS on the 5M-row build (e.g. `/usr/bin/time -v`) before committing caps.
- No source confirmed Polars `sink_iceberg` (streaming write) in official docs. That matters for 180M rows.
