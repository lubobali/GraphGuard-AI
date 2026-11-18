# ADR 0002 — Lakehouse catalog: Lakekeeper

**Status:** accepted, 2026-11-18 (S5.6c)
**Decided by:** Lubo, on the research in `docs/research/Open source lakehouse on one box.md`
and the measurements below

## Context

S5.6a built Iceberg tables with PyIceberg's SQL catalog (rows in a Postgres database).
Only PyIceberg can use it: DuckDB could read tables only when handed a metadata file
path, and cannot write without a REST catalog. Permissions (S5.6d), Feast (S5.6e) and
Spark (Phase 10) all assume an Iceberg REST catalog — the interface Snowflake,
Databricks, AWS and Google now share.

## Options

| | Lakekeeper | Apache Polaris | Unity Catalog OSS | PyIceberg SQL catalog |
|---|---|---|---|---|
| Iceberg REST | yes | yes | yes (writes since 0.7) | no |
| Language / image | Rust, ~84 MB | Java, ~417 MB | Java, ~2.76 GB | library, no server |
| RAM on this box | **measured 24 MB idle, 32 MB peak** | not measured (JVM; est. hundreds of MB) | not measured | 0 |
| Permissions | OpenFGA / Cedar, credential vending, remote signing | RBAC, credential vending | yes | none |
| 2026 security record (research) | no advisories found | 4 critical CVEs, fixed 1.4.1 | critical auth bypass | — |
| Name recognition | lower | high (basis of Snowflake Horizon) | high (Databricks) | — |

## Decision

**Lakekeeper.** It is the only REST catalog that is both light enough for a shared box
with ~1 GB spare and complete enough to grow into S5.6d's identities and permissions.
Measured, it is far inside its 256 MB cap.

## Consequences

- The tables did not move: Lakekeeper **registered** their existing metadata. Snapshot
  ids, history and locations are unchanged; read through it, all four tracked tables
  are row-for-row identical to before, and 2,000 live scores stayed identical.
- DuckDB can now write (`MERGE INTO` proven by a live test, readable by PyIceberg).
  Its full `ATTACH` exposes every namespace, so `just sql` stays on tracked-table views
  until S5.6d makes `sealed` a denied permission.
- **No authentication until S5.6d.** Mitigated by binding to 127.0.0.1 only, verified
  unreachable from the public IP, k3s pods and the container's own IP from a pod.
- Credential vending and remote signing are off; clients use the IAM-limited S3 key.
- One more always-on service (~30 MB) with a healthcheck, `just lakekeeper-status` and
  a runbook.
- Lakekeeper is 0.x: pinned by digest. Switching later (Polaris, Unity, a managed
  catalog) is a re-registration of metadata files, not a data move.
- The old SQL catalog stays as a documented, stale rollback.
