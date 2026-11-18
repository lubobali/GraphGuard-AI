# Public AML / transaction-fraud benchmark datasets (state as of 2026-11-17)

Method note: repos were opened through the GitHub API and raw files on 2026-11-17. TransXion's `data/tx.csv` was actually downloaded (245 MB over Git LFS) and profiled with awk. Kaggle pages render only through JavaScript and the Kaggle API refused unauthenticated calls from this box, so Kaggle file sizes and download counts could **not** be read live. AMLworld HI-Small sizes come from the copy already on disk at `/srv/graphguard/data/raw/`. Citation counts come from the Semantic Scholar API; several lookups hit rate limits (429).

## Q1. Per-dataset facts: size, span, labels, generator, license, availability, critiques, usage

### Takeaway
IBM AMLworld is still the most-cited and most-used graph AML benchmark: 184 citations, the standard temporal 60/20/20 split, and every new paper including TransXion (KDD '26) reports on it. The 2025-26 entrants are TransXion (a released dataset, same CSV schema as AMLworld) and AMLGentex (a generator only, with no released dataset). They mainly argue that AMLworld's template-based patterns are too easy. None of them has displaced it yet.

### Cited Findings

**IBM AMLworld (Altman et al., NeurIPS 2023 Datasets & Benchmarks)**
- Six datasets. HI-Small: 10 days, 515K accounts, 5M transactions, 3.6K laundering, 1 laundering transaction per 981. LI-Small: 10 days, 705K accounts, 7M transactions, 1/1,942. HI-Medium: 16 days, 2,077K accounts, 32M transactions, 1/905. LI-Medium: 16 days, 31M transactions, 1/1,948. HI-Large: 97 days, 2,116K accounts, 180M transactions, 223K laundering, 1/807. LI-Large: 97 days, 176M transactions, 1/1,750 — [AMLworld paper, Table 4](https://ar5iv.labs.arxiv.org/html/2306.16424)
- Labels are per transaction ("Is Laundering"). Separate pattern files tag laundering attempts as one of 8 typologies: fan-out, fan-in, gather-scatter, scatter-gather, cycle, random, bipartite, stack — [AMLworld paper](https://ar5iv.labs.arxiv.org/html/2306.16424)
- Generator: an agent-based virtual world of banks, individuals and companies, "governed by statistical distributions," with no real seed data. The authors calibrated it to US Federal Reserve payment-mix figures and IRS income data. They report that the LI-Large pattern laundering rate (about 1/21,440) is "very similar" to a real Italian bank (about 1/21,000) — [AMLworld paper](https://ar5iv.labs.arxiv.org/html/2306.16424)
- The generator code is **not released**, on purpose: the authors give "to prevent launderers from tuning against it" as the reason. Only the data is released — [AMLworld paper §7](https://ar5iv.labs.arxiv.org/html/2306.16424)
- License: data under CDLA-Sharing-1.0, GitHub repo under Apache-2.0. The data is on Kaggle (described as "new and improved"), and the original copy is on IBM Box — [IBM/AML-Data README](https://github.com/IBM/AML-Data)
- On-disk check (local copy, downloaded 2025-07-08): `HI-Small_Trans.csv` 475,664,283 bytes, `HI-Small_accounts.csv` 34,053,187 bytes, `HI-Small_Patterns.txt` 323,844 bytes — local file listing, `/srv/graphguard/data/raw/`
- Repo activity: IBM/AML-Data has 108 stars and was last pushed 2025-09-17. IBM/Multi-GNN, the baseline code, has 129 stars and was last pushed 2025-09-18 — [GitHub API, IBM/AML-Data](https://github.com/IBM/AML-Data); [IBM/Multi-GNN](https://github.com/IBM/Multi-GNN)
- Citations: 184 on Semantic Scholar as of 2026-11-17 — [Semantic Scholar](https://api.semanticscholar.org/graph/v1/paper/arXiv:2306.16424)
- Critiques:
  - TransXion says AMLworld relies on "template-driven injection... replicating an enumerated set of static graph motifs," so good scores may reflect motif recognition rather than generalization.
  - TransXion also measures AMLworld's graph as fragmented (giant-component ratio 0.3824, about 24,100 components) and finds over-regularized degree tails (fitted exponent at the 3.0 boundary) — [TransXion paper](https://arxiv.org/html/2604.17420v2)
  - AMLworld's own authors warn that results "may not translate one-to-one to real data" — [AMLworld paper App. B](https://ar5iv.labs.arxiv.org/html/2306.16424)
  - A 2026 preprint (SALT-GNN) reports that a plain GAT collapses in dense neighborhoods on HI-Small (F1 about 0.008) — [SALT-GNN, alphaxiv](https://www.alphaxiv.org/abs/2607.10131). This is a secondary snippet, not verified in full.

**TransXion (Chen et al., KDD '26 Datasets & Benchmarks, arXiv 2604.17420)**
- 47,526 accounts, 3,029,170 transactions, 4,641 laundering (0.153%), 365 simulated days. Released files: `data/tx.csv`, `data/person.csv`, `data/merchant.csv` — [TransXion README](https://github.com/chaos-max/TransXion)
- Verified by download on 2026-11-17:
  - `tx.csv` is 245,159,741 bytes and can be fetched over Git LFS (HTTP 200 from media.githubusercontent.com).
  - 3,029,170 data rows, 4,641 with `Is Laundering=1`, timestamps from 2025-01-01 00:00:29 to 2025-12-31 22:59:18.
  - The header is **identical to AMLworld's**: `Timestamp,From Bank,From Account,To Bank,To Account,Amount Received,Receiving Currency,Amount Paid,Payment Currency,Payment Format,Is Laundering`.
  - Currencies: CNY 2,897,013 (95.6%). CAD, USD, EUR, JPY, GBP, CHF and AUD have about 19K each.
  - Payment formats: Mobile 901,404, Card 792,619, Transfer 669,559, Cash 665,588.

  — [tx.csv via LFS](https://media.githubusercontent.com/media/chaos-max/TransXion/main/data/tx.csv)
- `person.csv` (3.2 MB) holds person_id, bank_account_number, bank, age, education, gender, marital_status and occupation. `merchant.csv` (198 KB) holds merchant_id, account, bank, description, type, registered_capital, industry, operating_status, establishment_date and legal_representative_id — [person.csv](https://raw.githubusercontent.com/chaos-max/TransXion/main/data/person.csv); [merchant.csv](https://raw.githubusercontent.com/chaos-max/TransXion/main/data/merchant.csv)
- Labels are **transaction-level only**. The four edit families used to build the illicit subgraphs (Intermediary Injection, Account Merging, Account Splitting, Transaction Adjustment) are not released as labels. There is **no pattern or ring file and no typology ID** — [TransXion paper](https://arxiv.org/html/2604.17420v2)
- Generator, three stages:
  1. `txsim` runs LLM-agent ("agentscope", LLMGraph) simulation of profile-aware normal activity.
  2. `aml-terraformer` does LLM-guided, graph-edit illicit subgraph synthesis with optional GRPO/LoRA RL. Per the paper, the edits are seeded from "real laundering subgraphs".
  3. The illicit subgraphs are embedded into the network, conditioned on entity profiles.

  — [TransXion README](https://github.com/chaos-max/TransXion); [paper](https://arxiv.org/html/2604.17420v2)
- License: the repo has no top-level LICENSE (the GitHub API reports `license: null`). `txsim/LICENSE` and `aml-terraformer/LICENSE` are both MIT ("Copyright (c) 2024 TransXion Contributors" and "AML Research Team"). The arXiv paper is CC BY 4.0. **No explicit license covers the `data/` files** — [GitHub API](https://api.github.com/repos/chaos-max/TransXion); [txsim/LICENSE](https://raw.githubusercontent.com/chaos-max/TransXion/main/txsim/LICENSE); [arXiv](https://arxiv.org/abs/2604.17420)
- Repo state: 135 files, 12 stars, 2 forks, 1 open issue, created 2026-04-18, last push 2026-11-03 (README image edits). Evaluation helpers include `aml-terraformer/scripts/evaluate_detection_rate.py`, `tools/split.py` and `monitor/gnn_monitor.py` — [GitHub API tree](https://github.com/chaos-max/TransXion)
- Citations: the Semantic Scholar lookup was rate-limited, so no count is available (see Gaps).

**AMLGentex (Östman et al., AI Sweden with Handelsbanken and Swedbank, arXiv 2506.13989, v2 2025-09-25)**
- An open-source **generator and benchmarking suite**, loosely modelled on Sweden's SWISH mobile payments. It runs spatial graph generation, then temporal simulation, then two-level Bayesian optimization (data plus model). It covers centralized, federated and isolated training, and ships 8 models: DT, RF, GBM, LR, MLP, GCN, GAT, GraphSAGE — [AMLGentex README](https://github.com/aidotse/AMLGentex)
- Label `is_sar` is account-level (node classification). Alert patterns: cycle, bipartite, stack, random, gather-scatter, scatter-gather. It models label noise, feature drift and partial observability across banks — [AMLGentex README](https://github.com/aidotse/AMLGentex)
- Its critique of existing datasets: they omit partial observability, temporal dynamics, strategic behavior, uncertain labels and network-level dependencies — [arXiv abstract](https://arxiv.org/abs/2506.13989)
- Availability: Apache-2.0, 28 stars, last push 2026-02-22. The repo (195 files) holds only config CSVs and **no pre-generated dataset**; output is `tx_log.parquet` produced locally — [GitHub API](https://github.com/aidotse/AMLGentex). A Hugging Face repo "thecoldice/AMLGENTEX-DATA" exists with an empty README and is not verified as official — [HF](https://huggingface.co/datasets/thecoldice/AMLGENTEX-DATA/blob/main/README.md)

**AMLSim (IBM)**
- An earlier IBM multi-agent generator. Per IBM it is "focus[ed] on models," and its data generation "does not use [the] detailed virtual world approach" of AMLworld — [IBM/AML-Data README](https://github.com/IBM/AML-Data). TransXion reports baselines on an AMLSim dataset (XGBoost AP 0.92), which suggests it is very easy — [TransXion paper](https://arxiv.org/html/2604.17420v2)

**SAML-D (Oztas et al., 2023)**
- 9,504,852 transactions, 0.1039% suspicious, 12 features, labelled with 11 normal and 17 suspicious typologies, 15 network structures — [secondary: arXiv 2404.14746](https://arxiv.org/pdf/2404.14746). Hosted on Kaggle; not opened in this session.
- TransXion's baselines show SAML-D is near-saturated for GNNs: Multi-PNA+EU AP 0.9948 — [TransXion paper](https://arxiv.org/html/2604.17420v2)

**Elliptic (2019) and Elliptic2 (Bellei et al., 2024)**
- Elliptic1: 204K Bitcoin transaction nodes, 166 features, 234K edges, on Kaggle (`ellipticco/elliptic-data-set`) — [Elliptic2 paper refs](https://arxiv.org/abs/2404.19109)
- Elliptic2: 122K labelled subgraphs (suspicious or licit, labelled by Elliptic) inside a background graph of 49M node clusters and 196M edges. The task is subgraph classification — [arXiv 2404.19109](https://arxiv.org/abs/2404.19109). Citations: 37 on Semantic Scholar — [S2](https://api.semanticscholar.org/graph/v1/paper/arXiv:2404.19109)
- Availability: the official repo (Apache-2.0, 30 stars, last push 2025-01-23) points to `http://elliptic.co/elliptic2` for files. On 2026-11-17 that URL resolved to a generic Elliptic page with **no Elliptic2 download**. A guessed Kaggle URL `ellipticco/elliptic2-data-set` returned 404 — [elliptic2 README](https://github.com/mitibmxgraph/elliptic2); [elliptic.co/elliptic2](https://www.elliptic.co/elliptic2)

**Feedzai BAF (Bank Account Fraud, NeurIPS 2022)**
- A **tabular** (not graph) suite of variants with controlled bias, generated from anonymized real account-opening data with tabular generative models. Hosted on Kaggle as `sgpjesus/bank-account-fraud-dataset-neurips-2022` — [feedzai/bank-account-fraud](https://github.com/feedzai/bank-account-fraud). Citations: 79 — [S2](https://api.semanticscholar.org/graph/v1/paper/arXiv:2211.13358)

**Other**
- J.P. Morgan AI Research has an AML synthetic-data page listing "Sample AML Trace Data". No download host or license was confirmed — [JPM AML page](https://jpmorgan.com/technology/artificial-intelligence/initiatives/synthetic-data/anti-money-laundering)
- AMLNet (arXiv 2509.11595) is a 2025 knowledge-based multi-agent AML generator, seen only as a search hit — [arXiv](https://arxiv.org/pdf/2509.11595)

### Inferences
- AMLworld is still the benchmark of reference. Every new benchmark paper defines itself against it, and its split and metric conventions (temporal 60/20/20, minority F1) are reused, including by TransXion.
- The newer critique, "templates are too easy," cuts against GNN headline numbers more than against tree models. TransXion's tables show GNN AP dropping from about 0.63-0.67 on AMLworld to about 0.27-0.35 on TransXion.

### Gaps
- No live Kaggle metadata (download counts, current file sizes, last-updated date) for AMLworld, SAML-D, BAF or PaySim, because Kaggle needs JS or authentication.
- No citation counts for TransXion, AMLGentex or SAML-D, because of the Semantic Scholar 429 rate limit.
- Not researched this session (no verified source): PaySim, the Czech bank (Berka/PKDD'99) dataset, IBM TabFormer details.
- Elliptic2's actual current download route is unconfirmed.

## Q2. Which datasets have published baselines on standard splits?

### Takeaway
AMLworld (Altman et al., 2023; Multi-GNN, Egressy et al.) and TransXion (KDD '26, cross-benchmark table) have published baselines on temporal splits. AMLGentex ships its own model suite but no fixed released dataset. Elliptic2 ships baselines on a seeded random split.

### Cited Findings
- AMLworld uses a 60/20/20 temporal split with three graph snapshots (train, train+val, all) so that only past edges are visible. Metric is minority-class F1. Results on HI-Small: GIN 28.70, GIN+EU 47.73, PNA 56.77, GFP+LightGBM 62.86, GFP+XGBoost 63.23. Large datasets have only GFP+tree results — [AMLworld paper Table 2](https://ar5iv.labs.arxiv.org/html/2306.16424)
- TransXion splits every dataset chronologically 6:2:2 and reports AP / F1 per model:

  | Model | AMLSim | AMLWorld | SAML-D | TransXion |
  |---|---|---|---|---|
  | XGBoost | 0.9206 / 0.9171 | 0.3761 / 0.4046 | 0.2436 / 0.1872 | 0.1716 / 0.2375 |
  | LightGBM | 0.2035 / 0.3598 | 0.1369 / 0.2569 | 0.1361 / 0.2654 | 0.0313 / 0.1383 |
  | Multi-GIN | 0.6933 / 0.7750 | 0.6380 / 0.6366 | 0.9919 / 0.9127 | 0.2878 / 0.4340 |
  | Multi-PNA | 0.6376 / 0.6973 | 0.6309 / 0.6279 | 0.9888 / 0.9681 | 0.3508 / 0.4865 |
  | Multi-GIN+EU | 0.7286 / 0.8029 | 0.5048 / 0.6520 | 0.9913 / 0.9372 | 0.2690 / 0.4247 |
  | Multi-PNA+EU | 0.5967 / 0.7005 | 0.6723 / 0.7095 | 0.9948 / 0.9770 | 0.3460 / 0.4674 |
  | Multi-GAT | 0.4583 / 0.4862 | 0.3951 / 0.4515 | 0.9718 / 0.9395 | 0.2779 / 0.4336 |

  — [TransXion paper](https://arxiv.org/html/2604.17420v2)
- Later HI-Small results (secondary, mixed protocols): MEGA-GNN is reported at about +9 points minority F1 over Multi-GNN. A leaderboard lists FraudGT at about 76.4 and ExSTraQt at 80.9 minority F1, with split protocols that differ between entries — [search snippets incl. wizwand leaderboard](https://www.wizwand.com/sota/money-laundering-detection-on-ibm-aml-hi-small)
- Elliptic2 reports GLASS, GNN-Seg and Sub2Vec baselines. The train/val split is "fixed given the random seeds," so it is random rather than temporal — [elliptic2 README](https://github.com/mitibmxgraph/elliptic2)

### Inferences
- TransXion's AMLWorld numbers do not say which of the six variants was used, so they cannot be compared directly to the HI-Small figures in Altman et al.
- TransXion's XGBoost/LightGBM are "edge-only." That is a weak tabular baseline next to Altman's GFP+XGBoost (graph-feature preprocessing), so the "GNN beats trees" gap on TransXion may be inflated. This is the same unfair-baseline trap the GraphGuard rules forbid.

### Gaps
- The exact AMLworld variant behind TransXion's table, and whether TransXion published fixed split timestamps, were not confirmed.

## Q3. TransXion specifics: repo contents, license, formats, labels, size, fit on an 8-core / ~4GB box

### Takeaway
TransXion is real, downloadable and small: a 245 MB transaction CSV in AMLworld's exact schema plus two small profile tables. It fits the box easily. Its weaknesses for this project are transaction-level labels only (no pattern or ring file), no explicit data license, a 95.6% single-currency (CNY) mix, and a young repo (12 stars).

### Cited Findings
- Contents: `txsim/` (LLM-agent simulator; needs an LLM provider config to regenerate), `aml-terraformer/` (illicit synthesis, GRPO, evaluation scripts, split tool, GNN monitor), and `data/` (3 CSVs) — [GitHub tree](https://github.com/chaos-max/TransXion)
- Formats and size: CSV. `tx.csv` is 245 MB (LFS), `person.csv` 3.2 MB, `merchant.csv` 0.2 MB — [GitHub API](https://api.github.com/repos/chaos-max/TransXion/git/trees/main?recursive=1)
- Labels: transaction `Is Laundering` only; no account-level label file, no ring or pattern IDs — [paper](https://arxiv.org/html/2604.17420v2)
- License: MIT on the two code subfolders, none at repo root, nothing stated for the data — [GitHub API](https://api.github.com/repos/chaos-max/TransXion)

### Inferences
- **Resource fit:** 3.0M rows and 47.5K accounts, against HI-Small's 5.08M rows, 476 MB and 515K accounts that the pipeline already handles on this box. TransXion is about 60% of HI-Small's rows and half its bytes. Its 365-day span will make rolling-window features cheaper per day but longer in calendar time. It should fit within the ~4GB budget, though this was not run.
- Account-level labels can be **derived**: an account is illicit if it touches a laundering edge. Ring labels cannot be derived, so the "rings caught at k" metric does not transfer.
- Regenerating the data needs an LLM service and RL training. It is not practical on this box, and it is not needed because the released CSVs are enough.

### Gaps
- Not measured: peak RAM of the actual feature pipeline on TransXion.

## Q4. Best second-dataset robustness check for an AMLworld HI-Small pipeline, and porting effort

### Takeaway
TransXion is the strongest candidate. It uses an identical CSV schema, comes from a different generator family (LLM-agent with non-template anomalies rather than statistical agents with 8 templates), is peer-reviewed at KDD '26, has published temporal-split baselines including on AMLworld, and is small. A within-family alternative is AMLworld LI-Small (same schema plus pattern files, lower illicit ratio), but it only tests a shift in prevalence, not a different generator. SAML-D is near-saturated and uses a different schema. Elliptic2 is a different task (subgraph classification on Bitcoin) with an unclear download route. AMLGentex has no released dataset and labels accounts, so using it would mean generating and freezing your own data.

### Cited Findings
- Schema match: TransXion's header equals AMLworld's 11 columns exactly — [tx.csv](https://media.githubusercontent.com/media/chaos-max/TransXion/main/data/tx.csv)
- Category mismatch: TransXion payment formats are Cash/Mobile/Transfer/Card — [tx.csv profile](https://media.githubusercontent.com/media/chaos-max/TransXion/main/data/tx.csv). AMLworld's mix is cheque, credit card, ACH and wire, calibrated to Federal Reserve data (plus others) — [AMLworld paper](https://ar5iv.labs.arxiv.org/html/2306.16424)
- Prevalence is close: TransXion 0.153%, HI-Small about 0.102% (1/981) — [TransXion README](https://github.com/chaos-max/TransXion); [AMLworld Table 4](https://ar5iv.labs.arxiv.org/html/2306.16424)
- XGBoost AP falls from 0.376 (AMLWorld) to 0.172 (TransXion) in the authors' own table — [TransXion paper](https://arxiv.org/html/2604.17420v2)

### Inferences
- **Porting effort (low to moderate):**
  1. The loader works as-is; header rename is unnecessary.
  2. Update categorical vocabularies for payment format and currency in any one-hot or Pandera schema, since the AMLworld categories will fail validation.
  3. Drop or replace HI-Small's accounts file. TransXion's equivalent is the person/merchant tables, joined on `bank_account_number`. These are optional extra features; to keep the comparison fair, run first without them.
  4. Re-derive the frozen temporal split. Use 60/20/20 to match the TransXion paper, or reuse the project's own split ratios.
  5. Drop ring-recall metrics and keep precision@k and PR-AUC.
  6. Re-audit the three excluded "generator artifact" features from FINDING-006. They may not exist in TransXion, or TransXion may have its own artifacts. The 95.6% CNY concentration means currency features will carry little signal.
  7. Tune on TransXion validation only.
- The honest framing: "the same pipeline, retuned on a second, independently generated synthetic benchmark." It is still not real data.
- The missing data license is a real blocker to redistribution, though not to use. The project should not re-host the CSV. It could open a GitHub issue asking for a data license.

### Gaps
- No public third-party results on TransXion yet (paper is about 7 months old), so there is no outside baseline to compare against other than the authors'.

## Q5. Is there any real (non-synthetic) public AML transaction data?

### Takeaway
Not for bank transfers. Every public bank-style AML dataset found is synthetic: AMLworld, AMLSim, SAML-D, TransXion, AMLGentex. The only real labelled laundering data is on public blockchains: Elliptic1 and Elliptic2 (Bitcoin). BAF is derived from real data but is synthetic, tabular, and about account-opening fraud, not AML.

### Cited Findings
- AMLworld: "Everything is synthetic" — [IBM/AML-Data](https://github.com/IBM/AML-Data)
- The AMLworld authors justify synthetic data because real data has incomplete labels: many laundering transactions are never detected — [arXiv 2306.16424](https://arxiv.org/abs/2306.16424)
- Elliptic2 is real Bitcoin data with labels from Elliptic — [arXiv 2404.19109](https://arxiv.org/abs/2404.19109)
- BAF is generated from anonymized real account-opening data — [feedzai/bank-account-fraud](https://github.com/feedzai/bank-account-fraud)

### Inferences
- A "real data" check for this project would have to be crypto (Elliptic). That changes the task (node or subgraph classification, anonymized features, no amounts or currencies in the AMLworld sense), so it is a separate study, not a robustness check.

### Gaps
- The Czech bank (PKDD'99) dataset is real but has no AML labels. Not verified this session.
