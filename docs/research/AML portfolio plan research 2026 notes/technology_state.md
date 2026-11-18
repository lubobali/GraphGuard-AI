# State of ML Technology for AML and Transaction Fraud Detection (research and production, as of Nov 2026)

Source-type legend: **[PR]** peer-reviewed venue, **[PP]** arXiv preprint, **[CB]** company engineering blog or company announcement, **[VM]** vendor marketing or vendor-written explainer, **[2nd]** secondary press or aggregator. "From memory" means I am recalling it, not citing a page fetched in this session. Treat those items as leads to check, not as citations.

Research ran 2026-11-17 with about 15 search and fetch calls. Several sources were read only as search snippets or partial page fetches. Where that matters, the item says so.

---

## 1. Graph ML for AML on IBM AMLworld: reported results, metrics, splits, GBDT vs GNN, leakage critiques

### Takeaway
Published HI-Small results for GNNs and graph transformers are minority-class F1 of about 0.63-0.76 (Multi-PNA 0.68, MEGA-PNA 0.74-0.75, Multi-FraudGT 0.76). Tuned boosted trees on graph features reach 0.63. A Nov 2026 preprint re-examined the benchmark and found two problems. First, the standard Multi-GNN protocol builds the test graph from all transactions, including later ones, and samples neighbours without regard to time. Second, a simulator artifact lets a rule that only looks at the date reach F1 0.482. Under that preprint's protocol, a strictly point-in-time LightGBM (F1 0.666) matches the best published GNN numbers. "A properly built point-in-time GBDT is as good as or better than the GNN" is therefore a recognised finding, but a recent one. It sits beside a large literature that reports GNNs winning under looser protocols.

### Cited Findings
**Benchmark lineage and headline numbers**
- The AMLworld dataset paper (Altman et al., IBM; arXiv 2306.16424, later at NeurIPS 2023 Datasets & Benchmarks, venue from memory) presents GNNs and gradient-boosted trees as both viable. It notes that GBTs need feature engineering while GNNs often do well without it. — [arXiv 2306.16424](https://arxiv.org/html/2306.16424v2) [PP/PR]
- Egressy et al., "Provably Powerful GNNs for Directed Multigraphs" (IBM; AAAI 2024, venue from memory). Reverse message passing, port numbering and ego IDs ("Multi-GNN") lift GIN minority F1 on AML Small-HI from about 28.7% to about 57%. Multi-PNA+EU beat all baselines on all AML datasets. Figures come from a search snippet. — [arXiv 2306.11586](https://arxiv.org/pdf/2306.11586) [PR]
- The published table, as reproduced by 2611.18914 (HI-Small / LI-Small minority F1): LightGBM+GFs 0.629 / 0.208; **XGBoost+GFs 0.632 / 0.273**; Multi-GIN+EU 0.648 / 0.269; **Multi-PNA+EU 0.682 / 0.331**. — [arXiv 2611.18914 §7.6.2](https://arxiv.org/html/2611.18914) [PP]
- Graph Feature Preprocessor (GFP, IBM; ICAIF 2024, DOI 10.1145/3677052.3698674). It extracts subgraph features (fan-in/out, cycles, scatter-gather and so on) in real time and feeds them to LightGBM or XGBoost, with a chronological train/val/test split. The MEGA appendix lists GFP+XGBoost at 63.23 ± 0.17 minority F1 on Small-HI. The ACM page returned 403, so I could not fetch the full text. — [ACM](https://dl.acm.org/doi/fullHtml/10.1145/3677052.3698674), [arXiv 2402.08593](https://arxiv.org/pdf/2402.08593), number via search snippet of [MEGA](https://arxiv.org/pdf/2412.00241) [PR]
- FraudGT (Lin, Guo, Zhu, Mitchell, Altman, Shun; MIT and IBM; **ICAIF 2024**, pp. 292-300). A graph transformer with edge-based message-passing gates and an edge-attribute attention bias, aimed at smurfing (scatter-gather) and round-tripping (cycles). It claims 7.8-17.8% higher F1 than baselines and about 2.4× throughput on synthetic AML datasets. Code: github.com/junhongmit/FraudGT. — [MIT DSpace](https://dspace.mit.edu/handle/1721.1/157762), [PDF](https://jshun.csail.mit.edu/FraudGT.pdf) [PR]
- MEGA-GNN (Bilgi & Atasu; arXiv 2412.00241, **accepted TMLR 2026**, v3 Aug 2026). Two-stage aggregation over multi-edges, permutation-equivariant (no port numbers). It uses "the same temporal splits as Multi-GNN". Small-HI minority F1: base GIN 46.50±4.11, base PNA 62.96±1.43, Multi-PNA 67.35±2.89, **MEGA-PNA (ego IDs + bi-dir MP) 74.01±1.55**, MEGA-PNA (bi-dir MP) 74.98±1.59, **Multi-FraudGT 75.81±0.75**. Medium-HI: MEGA-PNA 78.26±0.11, Multi-FraudGT 75.97. Large-HI: MEGA-PNA 76.95, Multi-FraudGT 73.04, Multi-PNA 72.35. LI variants: 35-49. — [arXiv 2412.00241v3](https://arxiv.org/html/2412.00241v3) [PR, TMLR]
- A Sept 2026 preprint (Shahbazi et al., arXiv 2609.37155) claims a temporal, "leakage-safe" split on HI-Small with identical features for all models. It reports an improved GATv2 at **AUPRC 64.85%** and best-F1 68.42%, against **XGBoost AUPRC 38.46%**. I saw only the abstract page and could not check the split mechanics or how the test graph was built. — [arXiv 2609.37155](https://arxiv.org/abs/2609.37155) [PP]
- Temporal and graph-transformer families also appear in the literature: TGN/TGAT-style temporal GNNs, dense-neighbourhood GNNs, and the "TeMP-TraG" and PNA variants named in the brief. I found **no fetched source** with their AMLworld numbers in this session (see Gaps).

**Reproducibility and leakage critiques**
- **arXiv 2611.18914** (Relvas & di Bernardo, WeCogno, Nov 2026, preprint; the authors disclose a commercial interest in their TBS method). Section 7.6.2 re-examines IBM AML:
  - The rule "flag every transfer dated day 10 or later" scores **F1 0.482 on HI-Small** and 0.261 on LI-Small. From day 10 onwards normal activity stops and only laundering chains continue. In HI-Small the 1,108 transfers in that tail are 59% laundering and hold 41% of the test set's laundering.
  - A point-in-time LightGBM (sender and receiver history over 6h, 24h, 72h and all prior time; pair history; amount relative to the account mean; threshold picked on validation) scores **F1 0.666 ± 0.045 on HI-Small** (0.373 on LI-Small). On the "active days" 8-9 only, AUPRC is 0.519 on HI-Small.
  - Mechanism: in the Multi-GNN code (commit 252b025, data_loading.py lines 32 and 102; train_util.py lines 86-93), "the test graph is built with all transactions, including those after the transfer being classified". Neighbour sampling ignores time, and the absolute timestamp is used as an edge attribute. The paper does not quantify how much this inflates scores.
  - The F1-optimal Multi-GIN threshold was 0.84, not the argmax of 0.5.
  - Recommendations: start from a history-aware baseline; report active-days results separately; pick thresholds on validation; check what each side saw (training cut-off, history features, test-graph contents); use several seeds with paired intervals.
  — [arXiv 2611.18914](https://arxiv.org/html/2611.18914) [PP]
- One GitHub reproduction got Multi-GNN F1 of about 0.71 under IBM's protocol (test plus tail, threshold 0.5), but **0.58 on its own time-based test split**. That is a protocol effect of more than 0.1 F1. This comes from a search snippet of the repo README and is unreviewed. — [trietle145/anti-money-laundering](https://github.com/trietle145/anti-money-laundering) [CB/hobby]
- Related signals (snippet-level only): a 2026 Bitcoin study (TWIN-GNN, MDPI) found GBTs on engineered features best for transaction-level classification, and that graph structure can become a liability under temporal shift. — [MDPI](https://www.mdpi.com/2624-800X/6/6/186). A 2026 adaptive temporal GNN paper reports that a graph-aware GBDT baseline slightly beat its proposed model on F1, and that graph gains swing with the evaluation protocol. — [ResearchGate](https://www.researchgate.net/publication/414197783_Adaptive_Temporal_Graph_Neural_Networks_for_Real-Time_Financial_Fraud_Detection_under_Concept_Drift) [PR/unclear]
- New synthetic AML generators are appearing, for example "Tide: A Customisable Dataset Generator for AML Research" (arXiv 2603.01863, 2026), which shows the field is aware of AMLworld's limits. — [arXiv 2603.01863](https://arxiv.org/pdf/2603.01863) [PP]
- AMLworld is also being reused as an LLM evaluation substrate: "AMLworld-Compact: Importance-Weighted Downsampling for Cost-Effective LLM Evaluation" (arXiv 2610.13627). — [arXiv 2610.13627](https://arxiv.org/pdf/2610.13627) [PP]

### Inferences
- **Metric mismatch.** The literature's headline metric is **minority-class F1 at a threshold**. The project uses **PR-AUC and precision@k**. The project's XGBoost PR-AUC of 0.28 cannot be compared directly with published F1 figures of 0.63-0.76. To be comparable, the write-up should also report minority F1 with the threshold picked on validation, ideally on the Multi-GNN split as well.
- **The project's result is in line with 2611.18914.** Strict point-in-time features with a time-respecting graph favour the tree. The project's GraphSAGE gap (0.045 vs 0.28) is much larger than any published gap. Positioning it as "under a strict protocol, the GNN advantage reported in the literature disappears, consistent with 2611.18914" is defensible. Claiming "GNNs don't work for AML" is not, because MEGA and FraudGT are much stronger architectures than vanilla GraphSAGE and handle multi-edges, direction and edge attributes. A senior reviewer would ask why the comparison used GraphSAGE rather than Multi-PNA or MEGA-PNA.
- **The day-10 tail artifact needs checking now.** If the project's validation or test windows include HI-Small days ≥10, part of any score may come from the simulator tail. Report active-days metrics separately. This may already be covered by FINDING-006 ("generator artifacts"), which should be checked against the 2611.18914 description.
- 2609.37155 (XGBoost 0.38 AUPRC, GATv2 0.65) contradicts 2611.18914 and the project's own result. It is the strongest recent counter-claim and should be cited and engaged with, with its test-graph construction scrutinised.

### Gaps
- I could not fetch FraudGT's standalone AMLworld minority-F1 table, the full GFP results, or the full Egressy table, so those numbers are from snippets.
- I found no fetched AMLworld results for TGN/TGAT, TeMP-TraG, or graph transformers other than FraudGT.
- 2611.18914 does not quantify how much the full-history test graph inflates the GNN scores.
- I found no peer-reviewed critique of AMLworld leakage. 2611.18914 is a preprint with a disclosed commercial interest.

---

## 2. Foundation models for transactions and fraud (graph FMs, transaction FMs)

### Takeaway
"Payments or transaction foundation models" (self-supervised transformers over event sequences, used as embedding providers that feed downstream classifiers) are the main 2025-26 production trend at large networks and processors: Stripe, Nubank, Visa, Mastercard, Featurespace/Visa. Nearly all the headline numbers are company-reported, and none have been independently audited. The one rigorous independent-ish comparison (2611.18914) found that frozen FM embeddings rarely beat a strong point-in-time GBDT, and gains were small (+0.7 to +0.8 AUC) on proprietary data. I found no graph foundation model in production AML.

### Cited Findings
- **Stripe Payments Foundation Model (May 2025, Stripe Sessions).** A transformer trained on "tens of billions" of transactions that produces per-payment embeddings. Sequence classifiers built on those embeddings detect card-testing attacks in real time. Stripe says detection on large users went from **59% to 97% overnight**, with no rise in false declines. The model works alongside Radar's purpose-built models; it does not replace them. These are company claims with no independent audit. — [TechCrunch](https://techcrunch.com/2025/05/07/stripe-unveils-ai-foundation-model-for-payments-reveals-deeper-partnership-with-nvidia) [2nd], [Stripe Sessions talk](https://stripe.com/it-ch/sessions/2025/auth-fraud-and-costs) [CB], [Analytics India Mag](https://analyticsindiamag.com/global-tech/how-stripe-used-ai-to-boost-fraud-detection-from-59-97-overnight/) [2nd]
- Stripe's earlier "ML flywheel" post describes continual retraining for card testing and claims an 80% reduction in card-testing attacks over two years. — [Stripe blog](https://stripe.com/en-gr/blog/the-ml-flywheel-how-we-continually-improve-our-models-to-reduce-card-testing) [CB]
- **Nubank nuFormer** (arXiv 2507.23267, "Your Spending Needs Attention", July 2025). A transformer over transaction sequences, fused with tabular features, intended as a reusable foundation for fraud, recommendation and risk. The production deployment in the paper is mainly **credit default**; fraud is a stated application, not the evaluated one. A third-party summary cites a 1.25% relative AUC lift in production. — [Building Nubank](https://building.nu.com/how-nubank-uses-transformers-to-model-financial-habits-at-scale/) [CB], [arXiv 2507.23267](https://arxiv.org/pdf/2507.23267) [PP]
- **Featurespace TallierLTM** (Oct 2023). A self-supervised "Large Transaction Model" whose embedding API turns transaction history into feature vectors for existing fraud models. It claims "up to 71%" more fraud value detected at a 5:1 false-positive ratio, a vendor-reported pilot figure. Featurespace was acquired by Visa (acquisition from memory; not verified this session). — [Financial IT](https://financialit.net/news/security/featurespace-launches-tallierltmtm-first-large-transaction-model-using-generative-ai) [VM]
- **Visa Large Transaction Model.** Visa's own PDF frames LTMs as a layer that speeds up existing fraud models rather than replacing them. Secondary sources date a launch to the Visa Payments Forum on 10 June 2026 and claim a proof of concept caught more than 5× the fraud value of a production GBDT. I could not find Visa's press release. Some blogs appear to misread "large transaction" as "large-dollar payments". — [Visa PDF](https://usa.visa.com/content/dam/VCOM/regional/na/us/Solutions/documents/large-transaction-models.pdf) [CB], [bankingnewsai](https://www.bankingnewsai.com/fintech/visa/fraud-and-risk-ai) [2nd]
- **Mastercard Decision Intelligence Pro** (Feb 2024). Transformer-based. Mastercard claims detection improves by 20% on average and "up to 300%" in some cases. A 2026 report says Mastercard is building its own transaction foundation model. — [CNBC](https://www.cnbc.com/2024/02/01/mastercard-launches-gpt-like-ai-model-to-help-banks-detect-fraud.html) [2nd], [VentureBeat](https://venturebeat.com/security/mastercard-spent-decades-training-its-fraud-system-to-see-bots-as-thieves-now-bots-are-the-ones-doing-the-buying) [2nd]
- **Independent check, 2611.18914 (Nov 2026).** The authors pretrained small (~0.4M parameter) sequence models with TabBERT-style masking, nuFormer-style next-event prediction and CoLES, and compared them with point-in-time aggregates plus LightGBM. "Frozen self-supervised embeddings rarely improve the baseline." Gains shrink with more labels and richer tabular data: +0.7 and +0.8 AUC on two proprietary datasets, and the +0.8 interval includes zero. The best results came from rank-averaging a GBDT with a fine-tuned sequence net (19 of 21 cells, median +2.1 AUC). On IBM TabFormer, the test period follows a shift in the fraud pattern. — [arXiv 2611.18914](https://arxiv.org/html/2611.18914) [PP]

### Inferences
- In production, the FM is used as a **feature provider into existing models**, not as an end-to-end replacement. That fits a GBDT-centred project: "GBDT + learned sequence embeddings" is the current pattern.
- The publicly evidenced wins are at **huge scale** (tens of billions of events). At 5M synthetic rows, a project cannot credibly claim FM benefits. Mentioning the trend and explaining why it is out of scope (data scale) reads as informed.

### Gaps
- I found no public architecture or evaluation detail for Stripe's PFM beyond talks and press.
- I found nothing on graph foundation models deployed for AML. The graph-FM literature exists, but I did not find a fraud-specific production case.
- Visa LTM primary announcement not located.

---

## 3. LLM agents in AML/fraud investigations: research, production, grounding, evaluation

### Takeaway
The research is thin and mostly un-evaluated. The best-known paper, Co-Investigator AI (arXiv 2509.08380), describes a multi-agent SAR-drafting system with an Agent-as-a-Judge validator but reports **no quantitative metrics** in its abstract. Production is vendor-led: FIS with Anthropic (May 2026, BMO and Amalgamated as early users), Hawk, Unit21. The pattern is "AI drafts, investigator decides and files". No published hallucination rates or completeness metrics for bank SAR tools turned up.

### Cited Findings
- **Co-Investigator AI** (Naik, Dintakurthi, Hu, Wang, Qiu; arXiv 2509.08380, Sept 2025, preprint). Specialised agents handle planning, crime-type detection, external intelligence and compliance validation, modelled on "AI Co-Scientist". It adds dynamic memory, an "AI-Privacy Guard" layer, and a real-time **Agent-as-a-Judge** validation agent that checks semantic coherence and rule-based regulatory accuracy. Agents assign confidence scores. Investigators review drafts in the loop. The abstract claims SARs are faster and more accurate but gives no metrics, dataset or expert-review protocol. — [arXiv 2509.08380](https://arxiv.org/abs/2509.08380) [PP]
- General agent-hallucination benchmarks, not AML-specific: MIRAGE-Bench (arXiv 2507.21017; "all evaluated models exhibit relatively low utility scores and substantial hallucination rates"), AgentHallu (2601.06818, attributing which agent step caused a hallucination), and a survey (2509.18970). — [MIRAGE-Bench](https://arxiv.org/html/2507.21017v1), [AgentHallu](https://arxiv.org/pdf/2601.06818), [Survey](https://arxiv.org/pdf/2509.18970) [PP]
- **FIS Financial Crimes AI Agent, built with Anthropic** (announced 4 May 2026). It drafts SAR narratives and surfaces high-risk cases for investigator review. BMO and Amalgamated Bank are early users, with general availability planned for later in 2026. Detail via an aggregator. — [bankingnewsai](https://www.bankingnewsai.com/ai-aml) [2nd]
- Vendors Hawk and Unit21 sell SAR-drafting agents; The Bancorp and FNBO are reported to use AI-assisted narratives and evidence-gathering agents. I could not verify these against the banks' own statements. — [mightybot comparison](https://mightybot.ai/compare/best-aml-investigation-software/) [VM], [bankingnewsai](https://www.bankingnewsai.com/ai-aml) [2nd]
- Governance as reported secondhand: FinCEN has not objected to AI-drafted narratives, but the filing decision and the accuracy of the narrative stay with the BSA officer, and filing must go through validated channels. Suggested QA checks are completeness, clarity, chronology and evidence alignment. — [bankingnewsai](https://www.bankingnewsai.com/ai-aml) [2nd], [myabt](https://www.myabt.com/blog/microsoft-copilot-financial-institutions-deployment-guide) [VM]

### Inferences
- Recommended practice, synthesised from the above and standard LLM-eval practice; not from a single cited source:
  - Agents pull facts only through tool calls over structured data.
  - Every claim in the narrative cites transaction or account IDs.
  - A **deterministic verifier** checks that each cited ID exists and that amounts, dates and counts match the database.
  - An LLM-as-judge is used only for style and completeness, and is calibrated against expert labels.
  - Metrics: unsupported-claim rate, citation precision and recall, coverage of the required SAR elements (who, what, when, where, why, how), and investigator edit distance or time saved.
- Because the public bar is so low (Co-Investigator has no numbers), a portfolio project that **measures** narrative faithfulness against ground-truth AMLworld laundering patterns would stand out. AMLworld labels the typology (fan-out, cycle and so on), which gives a ground truth that real SAR data never offers.

### Gaps
- I found no published hallucination rates, expert-review studies or productivity metrics for any production SAR-drafting tool.
- I did not find the Co-Investigator full-text evaluation section; only the abstract was fetched.
- I found no regulator document specifically on LLM-drafted SARs (FinCEN statements were secondhand).

---

## 4. Explainability in production AML; regulator expectations

### Takeaway
SHAP on tree models remains the standard production explainer, and regulators expect explanations scaled to the use. GNN explainers (GNNExplainer and others) are research tools with little production evidence. US model-risk guidance was reportedly replaced in April 2026 (SR 26-2). The EU AI Act's treatment of fraud and AML is contested in secondary sources.

### Cited Findings
- **US:** Several secondary sources say the Fed, OCC and FDIC replaced SR 11-7 on **17 April 2026 with SR 26-2 / OCC Bulletin 2026-13**: lighter and principles-based, still covering ML, reportedly leaving generative and agentic AI out of explicit scope, and aimed mainly at banks above $30B in assets. The primary document was not fetched. — [impetora](https://impetora.com/answers/model-risk-management-ai-banking), [bankingnewsai SR 11-7](https://www.bankingnewsai.com/ai-regulation/documents/fed-sr-11-7) [2nd/VM]
- **UK:** PRA **SS1/23** (model risk management) applies to all models that inform business decisions regardless of technique, with tiering that covers explainability. The FCA's DP22/4 discussion says firms must be able to explain decisions to customers and to the regulator. — [aisgrc](https://aisgrc.com/reference/governance/ai-risk-financial-services) [2nd]
- **EU AI Act:** credit scoring of natural persons is high-risk, with an explicit **exception for fraud detection** (Annex III 5(b), recalled from memory; secondary sources agree). Sources **disagree** on AML: one says many fraud and AML systems are high-risk, another that profiling-based fraud AI may be caught under Art. 6(3). The Digital Omnibus reportedly moves high-risk obligations to Dec 2027. — [fluxforce](https://www.fluxforce.ai/blog/explainable-ai-in-finance), [impetora](https://impetora.com/answers/model-risk-management-ai-banking) [VM]; conflicting
- **Singapore:** MAS AI risk-management guidelines reportedly cover "all forms of AI technology, including generative AI and AI agents", with board oversight and an inventory of AI use cases. The date of 7 Oct 2026 is unconfirmed. — [aisgrc](https://aisgrc.com/reference/governance/ai-risk-financial-services) [2nd]
- 2609.37155 frames itself as "Explainable and Trustworthy AI for AML", showing that explainability is a standard framing for graph AML papers. — [arXiv 2609.37155](https://arxiv.org/abs/2609.37155) [PP]

### Inferences
- For a project with XGBoost in production, the best fit is TreeSHAP per alert plus "reason codes" that map SHAP features to typology language, with the ring subgraph drawn for context. GNNExplainer remains optional research work. That matches regulatory weight: explanations go to investigators and examiners, not to end customers, since AML alerts are not adverse-action decisions.

### Gaps
- Primary regulator texts (SR 26-2, SS1/23, MAS guidelines, the EU AI Act annex) were not fetched; all statements here are secondhand.
- I found no FATF 2024-26 document in this session.
- I found no source evaluating GNNExplainer alternatives (PGExplainer, SubgraphX and others) for AML in production.

---

## 5. Production practice: hybrid rules + ML + graph, entity resolution, real-time vs batch, drift, champion/challenger, HITL

### Takeaway
Public production write-ups describe **hybrids**: rules plus ML models plus graph features plus human investigators. Graph signals are mostly delivered as **features into a tabular model**, computed in real time from a graph store. Continuous retraining ("flywheel") and FM embeddings are the 2025-26 additions. The engineering blogs I could fetch said little about entity resolution and champion/challenger.

### Cited Findings
- Booking.com runs a real-time graph service (JanusGraph on Cassandra) whose graph features feed a synchronous fraud service, combined with "machine learning models, manual investigations by fraud domain experts, and heuristic rules". — [Booking.com engineering](https://medium.com/booking-com-development/leverage-graph-technology-for-real-time-fraud-detection-and-prevention-438336076ea5) [CB]
- Intel's reference workflow uses a GNN to **generate features for XGBoost** (GNN embeddings into a GBDT). — [Intel](https://community.intel.com/t5/Blogs/Tech-Innovation/Artificial-Intelligence-AI/Enhanced-Fraud-Detection-Using-Graph-Neural-Networks-with-Intel/post/1524316) [VM]
- AWS (June 2025): graph ML with Neptune Analytics and GraphStorm on IEEE-CIS. — [aws-news](https://aws-news.com/article/2025-06-23-use-graph-machine-learning-to-detect-fraud-with-amazon-neptune-analytics-and-graphstorm) [VM]
- IBM's GFP is explicitly built for real-time subgraph feature extraction feeding GBDTs, which makes it the industrial-research reference for "graph features into a tree, online". — [arXiv 2402.08593](https://arxiv.org/pdf/2402.08593) [PR]
- Stripe's card-testing flywheel shows continual retraining against adversarial drift, with purpose-built models sitting beside the FM. — [Stripe blog](https://stripe.com/en-gr/blog/the-ml-flywheel-how-we-continually-improve-our-models-to-reduce-card-testing) [CB]
- Neo4j and TigerGraph promote graph analytics (community detection, ring detection) feeding ML features; this is marketing. — [Neo4j](https://neo4j.com/blog/fraud-detection/financial-fraud-detection-graph-data-science-analytics-feature-engineering/) [VM]
- Governance trend: a 2026 piece claims 72% of banks cannot shut down a malfunctioning AI model, and that examiners are asking about kill switches. The figure is from a vendor and unverified. — [risktemplate](https://risktemplate.com/blog/2026-08-01-ai-kill-switch-bank-exam-governance-vendor-risk/) [VM]

### Inferences
- The project's planned stack (point-in-time graph features feeding XGBoost, an online feature store, a streaming replay, an alert queue, champion/challenger, Airflow retraining) matches the industry pattern. Things a senior engineer would expect that are missing or underplayed:
  - **entity resolution**: AMLworld account IDs are already clean, so say so explicitly
  - a **rules layer** alongside ML, as a baseline and a safety net
  - an investigator **feedback loop**, with label delay modelled
  - a **drift** monitor on feature distributions and on alert volume at fixed capacity

### Gaps
- Searches returned no Revolut, Monzo, PayPal, Adyen, Capital One or Feedzai engineering posts. Coverage of big-fintech practice is weak, and a dedicated per-company search would fix that.
- I found no public source on champion/challenger mechanics in AML specifically.

---

## 6. What looks current vs dated to a senior ML engineer (late 2026)

### Takeaway
"Current" means: strict point-in-time evaluation that is explicitly contrasted with the leaky Multi-GNN protocol, comparison against strong graph baselines (Multi-PNA, MEGA, FraudGT, GFP+XGBoost) using the literature's metric, honest synthetic-data caveats, embeddings or FMs discussed as a feature layer, and LLM investigator tooling with **measured** grounding. "Dated" means: a vanilla GNN beating an untuned tree, random splits, AUC as the headline, and an un-evaluated "GenAI SAR writer".

### Cited Findings
- Point-in-time evaluation and the protocol critique are the newest methodological signal in the AMLworld literature (Nov 2026). — [arXiv 2611.18914](https://arxiv.org/html/2611.18914) [PP]
- SOTA graph baselines that use the literature's metric: MEGA-PNA and Multi-FraudGT at 74-76 minority F1 on Small-HI. — [MEGA, TMLR 2026](https://arxiv.org/html/2412.00241v3) [PR]
- Production uses FMs as an embedding layer. — [Visa PDF](https://usa.visa.com/content/dam/VCOM/regional/na/us/Solutions/documents/large-transaction-models.pdf), [TechCrunch on Stripe](https://techcrunch.com/2025/05/07/stripe-unveils-ai-foundation-model-for-payments-reveals-deeper-partnership-with-nvidia) [CB/2nd]
- The LLM-for-SAR space lacks published evaluation. — [arXiv 2509.08380](https://arxiv.org/abs/2509.08380) [PP]

### Inferences (positioning recommendations for GraphGuard-AI)
1. **Report in the literature's currency as well:** minority F1 with the threshold picked on validation, alongside PR-AUC and precision@k. Also run the Multi-GNN split once, so numbers can be placed next to the 0.63-0.76 table.
2. **Make the leakage argument the headline finding,** citing 2611.18914 as independent corroboration. Show the gap directly by running the GNN with a full-history test graph and then a point-in-time one.
3. **Upgrade the research-arm GNN** to Multi-PNA (IBM code is public) or MEGA-PNA (code accompanies the TMLR paper; availability inferred, not checked). Losing with GraphSAGE invites "you picked a weak GNN"; losing or tying with Multi-PNA under a strict protocol is a real result.
4. **Check the day ≥10 tail artifact** and report active-days metrics separately.
5. **Engage with 2609.37155,** which claims GATv2 beats XGBoost 65 to 38 AUPRC under a "leakage-safe" split.
6. **LLM layer (if added):** a tool-grounded case-narrative agent that cites transaction IDs, has a deterministic ID and amount verifier, and is evaluated for unsupported-claim rate and typology recall against AMLworld's labelled patterns. That would be ahead of the published state of the art, which has no numbers.
7. Say explicitly why foundation models are out of scope (scale), and present GBDT + graph features + optional embeddings as the industry pattern.

### Gaps
- There is no direct survey of hiring-manager expectations. These recommendations are inferred from the literature and production sources above.
