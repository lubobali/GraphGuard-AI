# Stack check: is the GraphGuard ML platform stack still sensible in November 2026?

Scope: Feast, Ray Serve + KubeRay, Redpanda, Evidently, Airflow, MLflow, plus LLM eval/observability and MCP for an investigator agent. Constraints: one shared 8-core Hetzner box, GraphGuard budget about 4GB RAM and 25GB disk, single-node k3s, XGBoost at p99 < 50ms, Redis online store, replayed stream, drift monitoring, retraining DAG with champion/challenger, MLflow already running, uv, React.

Method note: 15 tool calls (the research budget). Primary sources were used where the search surfaced them (PyPI, official blogs, vendor licence pages). Many version and date facts come from release mirrors or aggregators and are labelled. Local footprint numbers come from this repo's own CLAUDE.md (measured on the box), not from the web.

Measured local baselines (from `/srv/graphguard/CLAUDE.md`): k3s about 953MB at baseline; MLflow idles at about 695MB (capped at 1200M); MLflow Postgres capped at 512M; box swap about 99-100% full. That is already about 2GB of the 4GB budget before Ray, Redpanda, Airflow or the app.

## 1. Feast (feature store)

### Takeaway
Feast is alive and releases about monthly (0.68.0 on 10 Nov 2026). It is still pre-1.0 and had a run of critical 2026 CVEs. **Verdict: KEEP, but pin to 0.68.x, use only the offline-materialise-to-Redis path in-process, and do not expose the Feast feature server or registry server on any network.** Tecton is no longer an independent alternative, so Feast is the standard open-source name hiring managers recognise.

### Cited Findings
- Latest release Feast 0.68.0, uploaded to PyPI on 10 Nov 2026 — [PyPI feast](https://pypi.org/project/feast/)
- 2026 cadence (release mirrors): 0.64.0 on 13 Jun 2026 (registry REST API endpoints), 0.65.0 on 20 Jul 2026 (zoned timestamp type), 0.66.0 on 21 Aug 2026 (opt-in `filter_by_created_timestamp` cutoff in `get_historical_features`) — [newreleases v0.64.0](https://newreleases.io/project/github/feast-dev/feast/release/v0.64.0); [v0.65.0](https://newreleases.io/project/github/feast-dev/feast/release/v0.65.0); [v0.66.0](https://newreleases.io/project/github/feast-dev/feast/release/v0.66.0)
- 0.67.0 on 13 Oct 2026, which allows serving while a feature view is MATERIALIZING (aggregator) — [Stackscape Feast](https://stackscape.org/en/p/feast/)
- No 1.0 release found. Version numbers are still 0.x in Nov 2026 — [PyPI feast](https://pypi.org/project/feast/)
- CVE-2026-18948, CVSS 9.9: unsafe `dill` deserialisation of registry-stored UDFs gives unauthenticated RCE on the feature server and registry server in default configurations — [SentinelOne](https://www.sentinelone.com/vulnerability-database/cve-2026-18948/); [Averlon](https://research.averlon.ai/vulnerability-intelligence/cve/CVE-2026-18948)
- CVE-2026-56121: unauthenticated RCE through a crafted ApplyFeatureView gRPC request to the registry server, fixed in 0.63.0 — [VulnCheck](https://www.vulncheck.com/advisories/feast-unauthenticated-rce-via-applyfeatureview-grpc-deserialization); [kkm-mako write-up](https://kkm-mako.com/en/blog/articles/feast-cve/)
- CVE-2026-23537 (CVSS 9.1) unauthenticated arbitrary file write on the feature server; CVE-2026-23536 arbitrary file read in feature server <= 0.58.0 — [kkm-mako](https://kkm-mako.com/en/blog/articles/feast-cve/); [pentest-tools](https://pentest-tools.com/vulnerabilities-exploits/feast-feature-server-0580-arbitrary-file-read_29649)
- Auth bypass in Feast through 0.66.0: server accepts unverified JWTs — [VulnCheck](https://www.vulncheck.com/advisories/feast-through-0.66.0-authentication-bypass-via-unverified-token)
- CVE-2026-18941 (missing auth in SDK/operator) and CVE-2026-18942 (operator code injection, tenant privilege escalation) — [SentinelOne 18941](https://www.sentinelone.com/vulnerability-database/cve-2026-18941/); [SentinelOne 18942](https://www.sentinelone.com/vulnerability-database/cve-2026-18942/); [OpenCVE list](https://app.opencve.io/cve/?product=feast&vendor=feast-dev)
- Databricks announced it would acquire Tecton in Aug 2025, to fold Tecton's online serving into Agent Bricks. Price not disclosed — [Perficient](https://blogs.perficient.com/2025/09/26/databricks-acquires-tecton/); [MIT Sloan ME](https://www.mitsloanme.com/article/databricks-to-buy-enterprise-feature-store-tecton/)
- One 2026 source says tecton.ai redirects to Databricks as of 21 Aug 2026 and names Databricks/Tecton, Feast and Hopsworks as the remaining feature stores. Single, low-authority source — [Refonte Learning](https://www.refontelearning.com/blog/tecton-feature-store-consolidation)

### Inferences
- The CVEs all hit Feast's *network servers* (feature server, registry server, operator). GraphGuard's pattern (batch point-in-time join offline, `materialize` into Redis, scoring service reads Redis) can avoid running those servers entirely. Then the CVE exposure is mostly the SDK running locally. Pin >= 0.68.0 anyway, since 0.66.0 and earlier have the JWT bypass.
- Tecton (now Databricks), Chalk and Hopsworks are managed or heavy platforms. None of them fits a 4GB box. "Plain Redis" is the honest fallback. Feast adds a recognised name and point-in-time correctness on top of Redis for roughly zero extra RAM if used as a library.
- A strong portfolio line: "Feast used as a library for point-in-time-correct materialisation; feature server deliberately not deployed because of CVE-2026-18948 / 56121." That shows security judgement, which fintech reviewers value.

### Gaps
- Could not confirm the exact NVD dates/scores for every Feast CVE. Some pages carry future-dated metadata. Check NVD/GHSA before quoting numbers.
- No 2026 information found on Chalk or Featureform (searched; nothing came back). Featureform's status is unverified.
- No Hopsworks 2026 version/footprint found.

## 2. Ray Serve + KubeRay on k3s

### Takeaway
Ray is very active (2.60.0 on 4 Nov 2026) and KubeRay is on 1.7.x. But Ray is the heaviest piece on this box, and Ray has an actively exploited CVE (CISA KEV, 2026). **Verdict: KEEP only if it fits the measured RAM budget and the dashboard is never exposed. Otherwise REPLACE with plain FastAPI (or BentoML) as a k3s Deployment.** For one XGBoost model at p99 < 50ms, Ray adds no capability; its value here is recognition. The repo already deployed Ray Serve via KubeRay (commit 9caa67a), so the question is footprint, not feasibility.

### Cited Findings
- Ray 2.60.0 uploaded to PyPI on 4 Nov 2026; 2.59.0 dated 2 Oct 2026 by a secondary source, i.e. roughly monthly releases — [PyPI ray](https://pypi.org/project/ray/); [blockchain.news](https://blockchain.news/news/kuberay-ray-on-kubernetes-explainer)
- Anyscale announced KubeRay v1.6 and v1.7 — [Anyscale blog](https://www.anyscale.com/blog/kuberay-v1-7)
- KubeRay v1.7.0 on 20 Aug 2026 and v1.7.1 on 21 Sep 2026 (aggregator); another source still calls 1.6.2 the stable line. Sources conflict — [hysenlabs](https://hysenlabs.com/projects/ray-project-kuberay); [ai-infrastructure.net](https://ai-infrastructure.net/kuberay-integration/)
- A Sept 2026 guide verified Ray 2.58.0 with KubeRay operator 1.7.0 — [markaicode](https://markaicode.com/stack/rq-docker-stack/)
- CVE-2025-62593: DNS-rebinding RCE in Ray, patched in Ray 2.52.0, added to CISA KEV (Aug 2026) with a federal patch deadline of 20 Aug 2026 due to active exploitation — [sota.io](https://sota.io/blog/ray-cve-2025-62593-cisa-kev-shadowray-cra-article-14-2026); [decryptiondigest](https://www.decryptiondigest.com/blog/ray-cve-2025-62593-dns-rebinding-rce-patch); [kkm-mako](https://kkm-mako.com/en/blog/articles/ray-cve/)
- "ShadowRay 2.0" is a separate campaign against unpatched Ray clusters (built on CVE-2023-48022, the unauthenticated Jobs API, originally disputed by Anyscale) that turns them into crypto-mining botnets — [Penligent](https://www.penligent.ai/hackinglabs/the-zombie-vulnerability-a-2026-autopsy-of-cve-2023-48022-and-the-shadowray-2-0-resurgence/); [CISA KEV coverage](https://www.itcpeacademy.org/blog/news-cisa-adds-critical-ray-vulnerability-to-kev-catalog-amid-active-exploitation)
- KServe is Apache 2.0 and a CNCF project; latest reported v0.20.0 (6 Aug 2026), though another source says v0.18. Conflict — [hackernoon](https://hackernoon.com/top-kubernetes-native-inference-servers-ranked-2026); [mlai.qa](https://mlai.qa/blog/bentoml-vs-kserve/)
- BentoML Apache 2.0, latest 1.4.40 on PyPI (aggregator) — [modern-datatools](https://www.modern-datatools.com/compare/seldon-vs-bentoml)
- Seldon Core 2 is under Business Source License 1.1: production use needs a commercial licence; each version turns Apache 2.0 four years after release. Latest Seldon Core 2 reported as v2.10.2 (18 Dec 2025), Core 1 v1.19.0 (23 Jan 2026), no tags since Jan 2026 (aggregator) — [hivebook](https://hivebook.wiki/wiki/seldon-core-kubernetes-ml-serving-and-pipelines); [mlopslab](https://mlopslab.org/tools/seldon-exit-desk.html)

### Inferences
- Drop Seldon: BSL plus apparent stalled releases.
- KServe needs Knative/Istio (serverless mode) or at least its controller plus cert-manager; on a 4GB budget beside k3s, it is likely heavier than Ray. Not a good swap here.
- Triton is overkill for one XGBoost model on CPU (FIL backend exists, but it is a GPU-first tool).
- Ray Serve head pod + GCS + dashboard + a replica typically needs well over 1GB (unverified from web; measure with `kubectl top`/cgroup stats on the box). If Ray head + worker push GraphGuard above 4GB with k3s and MLflow, the honest choice is FastAPI in a k3s Deployment and a line in the write-up explaining why.
- Security requirement either way: Ray version >= 2.52.0 (CVE-2025-62593), dashboard/Jobs API on ClusterIP only, no NodePort, no public ingress.

### Gaps
- No authoritative Ray/KubeRay memory footprint figure found. Measure locally.
- Could not open the KubeRay GitHub releases page within budget; KubeRay 1.7.1 is aggregator-sourced.

## 3. Redpanda (stream)

### Takeaway
Redpanda changed licence this month. Starting with 26.3.1 (available 20 Nov 2026) Redpanda Streaming is no longer source-available, moving from BSL to a proprietary Community Edition free up to 50 cores per organisation. **Verdict: REPLACE with Apache Kafka 4.x (KRaft, Apache 2.0) as the default; Redpanda Community remains legally usable (8 cores << 50) but is now a closed binary.** For fintech hiring managers, "Kafka" is the recognised word, and Kafka 4.x no longer needs ZooKeeper, which removes the old footprint argument for Redpanda.

### Cited Findings
- R2 announcement (12 Nov 2026, Alexander Gallego): R2 is Redpanda's new engine (C++23 coroutines, one reactor per core). Starting with 26.3.1, Redpanda Streaming/Operator is no longer source-available; 26.3.1 ships 20 Nov; nothing changes until you upgrade; R1 code stays on GitHub — [Redpanda blog R2](https://www.redpanda.com/blog/r2-the-engine-of-engines)
- Community Edition: free up to 50 cores total per organisation (not per cluster); over the limit, clusters keep running but upgrades are blocked — [Redpanda blog R2](https://www.redpanda.com/blog/r2-the-engine-of-engines); [redpanda-data/community README](https://github.com/redpanda-data/community/blob/main/README.md)
- Older Redpanda docs still describe Community Edition as BSL; these predate 26.3.1 — [Redpanda licensing docs 26.1](https://docs.redpanda.com/streaming/26.1/get-started/licensing/overview.md)
- The R2 post gives no single-node/dev memory figures — [Redpanda blog R2](https://www.redpanda.com/blog/r2-the-engine-of-engines)
- Kafka 4.0 removed ZooKeeper; 4.x runs only in KRaft mode. 4.2.0 (17 Feb 2026) made Queues for Kafka (KIP-932) GA. Latest 4.4.0, dated 13 Oct 2026 (Wikipedia) or 22 Oct 2026 (other source) — [Wikipedia Apache Kafka](https://en.wikipedia.org/wiki/Apache_Kafka); [mungomash version list](https://mungomash.com/software/kafka/versions/); [acemq](https://acemq.com/blogs/kafka-end-of-life/)
- NATS JetStream: Apache 2.0, NATS Server v2.15.0 on 17 Sep 2026; not Kafka-protocol compatible (rewrite producers/consumers); one single source claims CNCF graduation 2 Nov 2026 (unverified) — [encore.dev](https://encore.dev/articles/kafka-alternatives); [shattered.io](https://shattered.io/kafka-vs-rabbitmq-redpanda-nats-msk-confluent-2026/)
- WarpStream: Kafka-compatible, stores data in object storage, proprietary licence (single comparison table) — [devtoollab](https://devtoollab.com/blog/kafka-alternatives)

### Inferences
- A single-node Kafka 4.x KRaft broker on the JVM can run with a small heap (e.g. `-Xmx512m`); with a 768M-1G container cap it should fit for a replay workload. Unverified on this box — measure.
- Redpanda (pre-26.3.1, BSL source-available) can also run in `--mode dev-container` with `--memory` limits and is lighter on RAM, but pinning to an old version to stay source-available is an awkward story.
- WarpStream needs object storage and a vendor control plane: wrong fit. NATS is lightest but not "Kafka", so it weakens the fintech signal.

### Gaps
- No measured 2026 RAM figure found for either Kafka 4.x single-node or Redpanda R2 single-node.
- Whether the Redpanda 26.3.1 Community binary needs licence activation/telemetry was not found.

## 4. Evidently (drift monitoring)

### Takeaway
Evidently's open-source library is still Apache 2.0 and on the 0.7 line (0.7.23, 11 Sep 2026), but releases slowed in 2026 and the pre-0.7 API is quarantined under `evidently.legacy`. **Verdict: KEEP (new 0.7 API only), with Prometheus/Grafana for live metrics.** It is still the most recognised open-source drift tool and runs as a batch job, so its idle footprint is zero.

### Cited Findings
- Latest evidently 0.7.23, released 11 Sep 2026 — [PyPI evidently](https://pypi.org/project/evidently/)
- Core library Apache 2.0, 100+ metrics — [PyPI evidently](https://pypi.org/project/evidently/); [api-evangelist profile](https://github.com/api-evangelist/evidently)
- 0.7 line is built around a Dataset/Descriptor API; the old API lives in `evidently.legacy` (e.g. Spark engine only there) — [Stackscape Evidently](https://stackscape.org/en/p/evidently/)
- Release intervals lengthened: 0.7.21 in March 2026, then 0.7.23 in September — [Stackscape Evidently](https://stackscape.org/en/p/evidently/)
- Conflict on the cloud product: one source says Evidently Cloud SaaS is no longer offered and commercial deployments are self-hosted; another describes Cloud features — [Stackscape](https://stackscape.org/en/p/evidently/); contradicted by [therundown](https://www.therundown.ai/tools/evidently-ai)

### Inferences
- Most tutorials online use the legacy `Report(metrics=[DataDriftPreset()])` import paths. Writing against the new API avoids looking dated and avoids a future removal.
- Slower releases are a mild risk but irrelevant for a batch drift job. NannyML (performance estimation without labels, CBPE) is the most interesting alternative for fraud, where labels arrive late; whylogs is lighter but less recognised. These are not verified for 2026 status here.

### Gaps
- No 2026 status found for NannyML or whylogs (not searched within budget).
- Exact version where `evidently.legacy` was introduced, and whether it is scheduled for removal, not confirmed.

## 5. Airflow (retraining DAG)

### Takeaway
Airflow 3.x is the current major line (3.4.0 announced 6 Nov 2026) with regular releases and active security fixes. **Verdict: KEEP only as a minimal LocalExecutor deployment with a hard cap; otherwise REPLACE with Dagster.** Airflow is the name most fintech data teams run, but its scheduler + API server + DAG processor + metadata DB is heavy for a 4GB budget that already holds k3s and MLflow.

### Cited Findings
- Airflow 3.4.0 listed on the official announcements page, 6 Nov 2026; adds bounded Task Loops, DAG authoring beyond Python, and a maturing Common AI provider — [Airflow announcements](https://airflow.apache.org/announcements/); [Airflow release blog](https://airflow.apache.org/blog/tags/release/)
- Airflow 3.0 GA blog (the 3.x line) — [Airflow 3 GA](https://airflow.apache.org/blog/airflow-three-point-oh-is-here/)
- 3.3.0 on PyPI 6 Jul 2026; 3.3.2 on 17 Sep 2026 (aggregator) — [PyPI 3.3.0](https://pypi.org/project/apache-airflow/3.3.0/); [VersionLog](https://versionlog.com/apache-airflow/3/)
- 3.3.1 fixed CVE-2026-68968, CVSS 7.5, an authorization flaw in the Backfill API — [VersionLog](https://versionlog.com/apache-airflow/)

### Inferences
- Airflow 3 splits into several processes (API server, scheduler, DAG processor, triggerer) plus Postgres. It can reuse the existing MLflow Postgres container (separate database) to save RAM.
- Dagster (asset-based, lineage of features -> model -> champion) is lighter as a single `dagster dev`-style deployment and maps nicely to "asset = feature table / model version". Prefect is lighter still. Argo Workflows is natural on k3s but less recognised in fintech ML. Flyte is heavy. None of these versions/footprints were verified in this pass.
- Champion/challenger logic lives in MLflow model aliases either way; the orchestrator choice does not affect it.

### Gaps
- No published 2026 minimum RAM figure for Airflow 3.x found. Measure.
- Dagster, Prefect, Flyte, Argo 2026 versions not searched within budget.

## 6. MLflow

### Takeaway
MLflow 3.x is very active (3.18.0, about 4 Nov 2026) and has moved heavily into GenAI: traces, LLM judges, multi-turn eval, an MCP registry. **Verdict: KEEP.** It is already running and its GenAI eval/tracing can cover the investigator agent too, so one tool does both jobs on this box.

### Cited Findings
- 3.18.0 marked Latest on GitHub; mirror dates it 4 Nov 2026: automatic issue detection, redesigned eval and trace comparison UI, experimental Skill Registry, experimental online code-based evaluation (needs self-hosted server with job containers); requires `mlflow db upgrade` on a stopped server before upgrading — [GitHub releases](https://github.com/mlflow/mlflow/releases); [brickster mirror 3.18.0](https://www.brickster.ai/releases/mlflow/mlflow/v3.18.0)
- 3.17.0 (Oct 2026): typed judge decisions, resource permissions, faster trace analytics — [MLflow 3.17.0 highlights](https://mlflow.org/releases/3.17.0/)
- 3.16.0: redesigned trace explorer default, session grouping for multi-turn conversations; 3.15.0: MCP Registry, multimodal attachments in LLM judges — [MLflow 3.15.0](https://mlflow.org/releases/3.15.0/)
- 3.10.0 (20 Feb 2026): multi-turn evaluation, LLM cost tracking, AI Gateway usage analytics — [brickster mirror 3.10.0](https://www.brickster.ai/releases/mlflow/mlflow/v3.10.0)
- MLflow 3 launch release notes (3.1.0) — [GitHub v3.1.0](https://github.com/mlflow/mlflow/releases/tag/v3.1.0)

### Inferences
- Upgrading needs a DB migration; back up the `graphguard-mlflow-db-data` volume first.
- Model registry aliases (`@champion`, `@challenger`) are the modern pattern (stages were deprecated in late 2.x); use them for the champion/challenger DAG. (Deprecation of stages is from prior knowledge, not re-verified in this pass.)

### Gaps
- Did not check which MLflow version is currently running on the box against 3.18.

## 7. LLM eval/observability and agent tool protocols for an investigator agent

### Takeaway
The 2026 standard is OpenTelemetry tracing with the GenAI semantic conventions (`gen_ai.*`), read by a backend such as Langfuse (MIT core) or Arize Phoenix (Elastic License 2.0), plus an LLM-judge eval harness. MCP is the agent tool protocol, now governed by the Linux Foundation's Agentic AI Foundation. **Verdict: use MLflow GenAI tracing/eval (already running, zero extra RAM) with OTel GenAI conventions, and expose the agent's tools (case lookup, subgraph fetch, score explanation) as an MCP server.** Add Langfuse only if a separate trace UI is wanted; it needs ClickHouse and is too heavy for this box.

### Cited Findings
- Langfuse, Phoenix and others map OTel GenAI semantic conventions (`gen_ai.*`), which give a shared span/attribute vocabulary across backends — [reactify-solutions](https://www.reactify-solutions.com/articles/agent-evaluation-observability-2026); [morphllm](https://www.morphllm.com/agent-tracing)
- Phoenix converts OTel GenAI attributes at ingest since 15 May 2026; also uses its own OpenInference conventions; licensed Elastic License 2.0 (source-available, not OSI) — [qaskills](https://qaskills.sh/blog/langfuse-vs-arize-phoenix); [myengineeringpath](https://myengineeringpath.dev/tools/langfuse-vs-phoenix-arize/)
- Langfuse ingests OTel spans, but some features assume its own SDK — [qaskills](https://qaskills.sh/blog/langfuse-vs-arize-phoenix)
- Vendor (competitor) page claims OpenInference instrumentation was donated to OpenTelemetry in June 2026 and that Dynatrace acquired Arize; unverified, competitor source — [Langfuse comparison page (vendor)](https://langfuse.com/resources/engineering/best-phoenix-arize-alternatives)
- One source says ClickHouse acquired Langfuse; unverified — (reported in search summary of [MarkTechPost Aug 2026](https://www.marktechpost.com/2026/08/09/top-llm-observability-and-evaluation-platforms-in-2026-langfuse-langsmith-braintrust-arize-and-more-compared/), not confirmed)
- MLflow 3.x ships LLM judges, multi-turn eval, trace explorer, MCP Registry — [MLflow 3.15.0](https://mlflow.org/releases/3.15.0/); [MLflow 3.17.0](https://mlflow.org/releases/3.17.0/)
- MCP was donated by Anthropic to the Agentic AI Foundation (a Linux Foundation directed fund co-founded by Anthropic, Block and OpenAI; founding projects MCP, goose, AGENTS.md), announced Dec 2025; LF cites 10,000+ published MCP servers; MCP integrated in Claude, Copilot, Gemini, ChatGPT — [Anthropic announcement](https://www.anthropic.com/news/donating%2Dthe%2Dmodel%2Dcontext%2Dprotocol%2Dand%2Destablishing%2Dof%2Dthe%2Dagentic%2Dai%2Dfoundation); [RCP Mag 9 Dec 2025](https://rcpmag.com/Articles/2025/12/09/Linux-Foundation-Unites-Major-Tech-Firms.aspx); [IT Brief](https://itbrief.co.uk/story/anthropic-donates-mcp-to-new-agentic-ai-foundation). One source dates the donation 19 May 2026, conflicting — [Business Tech Navigator](https://businesstechnavigator.com/news/agentic-ai-foundation-mcp-linux-foundation-open-standard)

### Inferences
- For a fraud investigator agent, the eval that matters to a hiring manager is grounded faithfulness: does the narrative cite only real transactions/features from the subgraph? Build a small labelled set of cases and an LLM-judge plus deterministic checks (every cited txn ID exists) in MLflow eval.
- Phoenix's ELv2 is fine for a portfolio but worth noting; Langfuse self-host (Postgres + ClickHouse + Redis + worker) is several GB and does not fit.

### Gaps
- DeepEval and UK AISI Inspect 2026 status not searched within budget.
- Current MCP spec revision (2026) not confirmed from the spec site.
- OTel GenAI semantic conventions stability status (experimental vs stable) in Nov 2026 not confirmed from opentelemetry.io.

## Summary verdict table (for the report writer)

| Tool | Nov 2026 version | Verdict | One-line reason |
|---|---|---|---|
| Feast | 0.68.0 (10 Nov 2026), still 0.x | KEEP (library only, >= 0.68) | Recognised OSS feature store; Tecton absorbed into Databricks; servers have critical 2026 CVEs, so don't run them |
| Ray Serve + KubeRay | Ray 2.60.0 (4 Nov 2026), KubeRay 1.7.x | KEEP if it fits measured RAM, else REPLACE with FastAPI/BentoML on k3s | Overkill for one XGBoost model; KEV-listed CVE-2025-62593 (needs >= 2.52) |
| Redpanda | 26.3.1 on 20 Nov 2026, now closed-source CE | REPLACE with Kafka 4.x KRaft | Licence went proprietary; Kafka no longer needs ZooKeeper; "Kafka" reads better to fintech |
| Evidently | 0.7.23 (11 Sep 2026) | KEEP (0.7 API, not `legacy`) | Apache 2.0, batch-only, zero idle RAM; slower cadence |
| Airflow | 3.4.0 (6 Nov 2026) | KEEP minimal + capped, or REPLACE with Dagster if RAM is short | Industry default but heavy beside k3s + MLflow |
| MLflow | 3.18.0 (~4 Nov 2026) | KEEP | Already running; also covers GenAI eval/tracing |
| LLM obs/eval | OTel GenAI conventions + MLflow GenAI | ADD via MLflow, not Langfuse | No extra RAM; Langfuse needs ClickHouse |
| Agent tools | MCP under LF Agentic AI Foundation | ADD | De facto standard |
