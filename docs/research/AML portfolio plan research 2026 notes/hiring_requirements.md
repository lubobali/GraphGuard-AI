# Hiring requirements for fraud / AML / risk ML roles, late 2026 (sample of 58 live postings)

**How this was built.** Collected 2026-11-17. Full posting text came straight from each employer's public applicant-tracking system (ATS) API: Greenhouse, Ashby, Workday CXS and JPMorgan's Oracle HCM. Search-engine snippets were not used. That is 4,215 postings from about 45 fintech, bank and payments employers. From those I kept every ML / data-science / applied-scientist posting whose own text is about fraud, AML or financial crime, identity/KYC, or payments, dispute or credit risk. Exact duplicates posted in several cities were removed. The result is **58 distinct postings from 29 employers**: 56 have a fraud, AML or identity component and 2 are credit-risk only (Robinhood, Monzo). All 58 were live on the day of collection. "Posted" is the ATS's first-published date. 56 of the 58 are dated 2026 (40 of them Sept–Nov 2026), and 2 are late 2025.

Tagging was done with keyword regexes over the full text, then spot-checked by hand. The counts are reliable to roughly ±2 per tag. Main caveats: "Graph" includes product names like "Identity Graph"; "LLM" includes postings that only want AI coding tools (also counted separately); "Reg/MRM" includes the word "compliance" in a business sense. A tag counts as **preferred-only** when every match sits inside a "Preferred / Nice to have / Bonus" section or next to "a plus". Location: 54 US/UK/EU, 1 Toronto (Mastercard graph role), 1 Remote-Canada (Affirm) and 2 multi-region. The non-US/UK/EU ones are kept because they are on-topic. They are flagged in the table.

The per-posting tag data is saved next to this file as `hiring_postings_tagged.json`.

## Q1. Which ~50 real postings were collected (company, title, URL, date)?

### Takeaway
58 real 2026 postings with full text. The largest contributors are Socure (8), Stripe (6), Plaid (5), and Capital One, JPMorgan, Coinbase and Sardine (3 each), plus 22 other employers. Revolut, Monzo (fraud), Wise, Checkout.com, Feedzai, Unit21, Hawk AI, ComplyAdvantage, Nasdaq Verafin and Amex are **missing**. Either they had no ML-titled fraud role open on a public ATS, or their careers site could not be read by machine (see Gaps).

### Cited Findings
Legend: GBDT = gradient boosting / XGBoost / LightGBM / tree ensembles; DL = deep learning / PyTorch / TF / transformers; Graph = any graph method, graph features, entity resolution or graph DB; GNN = graph neural nets by name; FeatStore = feature store / feature platform / feature pipeline; RT = real-time / low latency; Stream = streaming / Kafka; K8s = Kubernetes / containers; Mon = model monitoring / drift; XAI = explainability; LLM = LLM / GenAI / agents (incl. AI-coding-tool asks); Reg/MRM = regulatory, model risk, governance or compliance. `*` = appears only as preferred / nice-to-have. Min yrs = headline minimum years in the posting ("-" = none stated).

| # | Company | Title | Location | Posted | Domain | Min yrs | Signals tagged |
|---|---|---|---|---|---|---|---|
| 1 | Gemini | [Senior Fraud Data Scientist (Credit Card)](https://boards.greenhouse.io/embed/job_app?for=gemini&token=7905301&gh_jid=7905301) | New York, New York | 2026-05-11 | Fraud/Identity/KYC | 5 | Mon, Reg/MRM |
| 2 | Socure | [Data Scientist ll - RiskOS](https://jobs.ashbyhq.com/socure/5337e747-bc84-4c2d-8f5e-042cf64bc80e) | New York - Remote | 2026-09-17 | Fraud/Identity/KYC | 3 | GBDT, RT, XAI, LLM, Spark |
| 3 | Socure | [Head of Data Science, Compliance Products](https://jobs.ashbyhq.com/socure/ab418664-d561-4939-b490-f54886b4dc04) | Hub - San Francisco | 2026-11-06 | AML/FinCrime/Fraud/Identity/KYC | 10 | DL, RT, Mon, XAI, Spark, Reg/MRM |
| 4 | Socure | [Staff Data Scientist - Digital Intelligence](https://jobs.ashbyhq.com/socure/37ee4c0c-2b5b-4fc0-a485-f921c40a7861) | Hybrid - San Francisco, CA | 2026-07-27 | Fraud/Identity/KYC | 12 | GBDT*, DL*, Graph*, RT, Stream*, Mon, XAI, Spark, Reg/MRM |
| 5 | Socure | [Head of Data Science, Identity Graph](https://jobs.ashbyhq.com/socure/b381b846-64df-48ac-9b37-c939255f1e90) | Hybrid - San Francisco, CA | 2026-07-27 | AML/FinCrime/Fraud/Identity/KYC | 10 | DL, Graph, GNN, RT, XAI, Spark, Reg/MRM |
| 6 | Socure | [Staff Data Scientist, Watchlist](https://jobs.ashbyhq.com/socure/188b635a-5534-4e1b-bdaf-1e6dfea86aad) | California - Remote | 2026-09-23 | AML/FinCrime/Fraud/Identity/KYC | 7 | DL*, Graph, RT, Mon, LLM, Reg/MRM |
| 7 | Socure | [Staff Data Scientist - Fraud & Risk](https://jobs.ashbyhq.com/socure/2d652fb5-55b0-42d0-a75d-dd7511721441) | Hub - New York | 2026-09-14 | Fraud/Identity/KYC | 8 | DL, Graph, RT, Mon*, LLM* |
| 8 | Socure | [Data Scientist II, Fraud & Risk](https://jobs.ashbyhq.com/socure/05533c4e-1c59-4ae8-b12c-6acad3757a77) | Hub - San Francisco | 2026-10-09 | Fraud/Identity/KYC | 2 | DL, RT, Mon*, LLM* |
| 9 | Socure | [Senior Data Scientist - Digital Intelligence, Device Signals](https://jobs.ashbyhq.com/socure/819e4f69-3262-4a51-9237-ce93af394840) | Hybrid - San Francisco, CA | 2026-04-01 | Fraud/Identity/KYC | 6 | GBDT, DL, RT, Stream, XAI, Spark |
| 10 | Stripe | [Staff Machine Learning Engineer, Radar](https://stripe.com/jobs/search?gh_jid=8243615) | N/A | 2026-10-07 | Fraud/Identity/KYC | 10 | DL*, Graph, FeatStore, RT, XAI, LLM |
| 11 | Stripe | [Machine Learning Engineer, Transaction Risk](https://stripe.com/jobs/search?gh_jid=8187574) | Seattle, New York City | 2026-11-10 | Fraud/Identity/KYC | 5 | DL, Graph, FeatStore*, RT, Mon*, LLM |
| 12 | Stripe | [Machine Learning Engineer, Radar](https://stripe.com/jobs/search?gh_jid=7983456) | Seattle, South San Francisco  | 2026-06-23 | Fraud/Identity/KYC | 5 | DL, Graph, FeatStore*, RT, Mon*, LLM |
| 13 | Stripe | [Machine Learning Engineer, Link](https://stripe.com/jobs/search?gh_jid=8197886) | New York City  | 2026-09-21 | Fraud/Identity/KYC | 6 | GBDT, RT, Mon, LLM, Spark* |
| 14 | Stripe | [Engineering Manager, Machine Learning - Fraud Detection](https://stripe.com/jobs/search?gh_jid=8069506) | N/A | 2026-07-16 | Fraud | 3 (mgmt) |  |
| 15 | Stripe | [Engineering Manager, Machine Learning - Credit Risk](https://stripe.com/jobs/search?gh_jid=8205280) | N/A | 2026-09-15 | Fraud/Credit | 3 (mgmt) |  |
| 16 | Oscilar | [Staff Data Scientist](https://jobs.ashbyhq.com/oscilar/a83cfe5b-5a34-4aa7-9e4d-52ca6428efc6) | Remote | 2026-09-01 | AML/FinCrime/Fraud | 5 | LLM*, Spark, Reg/MRM |
| 17 | Block | [Senior Data Scientist, First Line Risk](http://block.xyz/careers/jobs/5025529008?gh_jid=5025529008) | Bay Area, CA, United States of America | 2025-12-16 | Identity/KYC | 7 BS / 5 MS / 3 PhD | Mon, LLM, Reg/MRM |
| 18 | Block | [Senior ML/AI Modeler, Risk Automation Machine Learning](http://block.xyz/careers/jobs/5394441008?gh_jid=5394441008) | Bay Area, CA, United States of America | 2026-08-19 | Fraud/Identity/KYC | 8 | DL, RT, Mon, LLM, Reg/MRM |
| 19 | Dave | [Lead Machine Learning Scientist](https://jobs.ashbyhq.com/dave/c85a73ba-ed1c-4def-9aed-161ba7779c6b) | United States | 2026-10-14 | Fraud/Identity/KYC/Credit | 7 | DL, Graph*, LLM, Spark, Reg/MRM |
| 20 | Dave | [Staff Machine Learning Scientist](https://jobs.ashbyhq.com/dave/b68f96aa-b7bc-4bbc-9b29-4fd87cca84a2) | United States | 2026-10-27 | Fraud/Credit | 8 | GBDT, DL, Mon*, LLM*, Spark, Reg/MRM |
| 21 | Chime | [Data Scientist, Dispute Risk](https://boards.greenhouse.io/chime/jobs/8904126002?gh_jid=8904126002) | Chicago, IL, USA | 2026-11-09 | Fraud | 2 | Mon, Reg/MRM |
| 22 | Chime | [Lead Data Scientist, Credit Risk](https://boards.greenhouse.io/chime/jobs/8788322002?gh_jid=8788322002) | Chicago, IL, USA | 2026-10-13 | Fraud/Credit | 7 | GBDT, XAI, Reg/MRM |
| 23 | Plaid | [Staff Data Scientist - Fraud](https://jobs.ashbyhq.com/plaid/361c4725-ab72-4895-a3aa-9b642f4927a9) | New York City Office | 2026-11-17 | Fraud | 10 | Graph* |
| 24 | Plaid | [Senior Machine Learning Engineer - Fraud](https://jobs.ashbyhq.com/plaid/e9a9aeab-be90-43f3-b898-63a846cb5777) | New York City Office | 2026-11-17 | Fraud | 7 | GBDT, DL, Graph*, RT, LLM |
| 25 | Plaid | [Staff Machine Learning Engineer - Fraud](https://jobs.ashbyhq.com/plaid/85cd5d07-9920-45fa-931a-daf8c3558e5b) | San Francisco HQ | 2026-11-17 | Fraud | 10 | DL*, Graph*, GNN*, Mon, XAI*, LLM |
| 26 | Plaid | [Staff Machine Learning Engineer (Research Scientist) - Fraud](https://jobs.ashbyhq.com/plaid/5e56c0a6-3caa-4255-8c63-95c29cbc2a32) | New York City Office | 2026-11-17 | Fraud | 5 post-PhD | DL, Graph, RT, XAI*, LLM |
| 27 | Plaid | [Data Science Manager - Fraud](https://jobs.ashbyhq.com/plaid/55eacfa6-71e0-42ac-8788-04dc1e5fd694) | New York City Office | 2026-09-12 | Fraud | - | Graph*, XAI* |
| 28 | Sardine | [Senior Data Scientist](https://jobs.ashbyhq.com/sardine/e6764411-1740-4ce1-8a9a-79ad459082ea) | North America | 2026-08-11 | AML/FinCrime/Fraud | 7 | Graph, RT, Mon, Spark* |
| 29 | Sardine | [Senior Applied AI Research Scientist](https://jobs.ashbyhq.com/sardine/44cf5225-547a-4584-a271-c0c6ddc7b0b6) | North America | 2026-09-04 | AML/FinCrime/Fraud | 4 | DL, RT, Mon, XAI, LLM, Reg/MRM |
| 30 | Sardine | [Machine Learning Engineer](https://jobs.ashbyhq.com/sardine/2c8f0342-b8af-4cc2-85cd-67bc48275568) | North America | 2025-09-09 | AML/FinCrime/Fraud | - | FeatStore, RT, K8s, Mon, LLM*, Reg/MRM |
| 31 | Middesk | [Lead Data Scientist](https://jobs.ashbyhq.com/middesk/7fd5aeb2-c33c-4f0a-ad3d-2161201bc174) | San Francisco | 2026-05-27 | AML/FinCrime/Fraud/Identity/KYC | 7 | Graph*, FeatStore*, LLM*, Reg/MRM* |
| 32 | Alloy | [Senior Machine Learning Engineer](https://jobs.ashbyhq.com/5c335d0c-0c96-4b85-a913-db4ce4f02651/3ce8dae1-9bd4-4b0c-b19d-721be8f057c6) | Alloy New York | 2026-04-07 | Fraud/Identity/KYC | 8 | GBDT, Graph*, RT, Mon, Reg/MRM |
| 33 | Coinbase | [Staff Machine Learning Engineer(Platform - Identity)](https://www.coinbase.com/careers/positions/7891045?gh_jid=7891045) | Remote - USA | 2026-06-10 | AML/FinCrime/Fraud/Identity/KYC | 8 | DL, Graph, GNN, FeatStore, RT, LLM, Reg/MRM |
| 34 | Coinbase | [Staff Machine Learning Engineer, Compliance Automation (Platform)](https://www.coinbase.com/careers/positions/8333165?gh_jid=8333165) | Remote - USA | 2026-10-29 | AML/FinCrime | 8 | Mon, XAI, LLM, Spark, Reg/MRM |
| 35 | Coinbase | [Senior Machine Learning Platform Engineer - Identity](https://www.coinbase.com/careers/positions/8211490?gh_jid=8211490) | Remote - USA | 2026-09-17 | Fraud/Identity/KYC | 5 | FeatStore, RT, Stream, Mon, LLM |
| 36 | Persona | [Senior Research Scientist](https://jobs.ashbyhq.com/persona/7c498972-86f4-4513-b796-46f8854a3690) | San Francisco | 2026-10-14 | Fraud/Identity/KYC | - (pubs/PhD) | Reg/MRM |
| 37 | Mercury | [Senior Data Scientist - Risk ML](https://job-boards.greenhouse.io/mercury/jobs/6179231004) | San Francisco, CA, New York, NY, Portlan | 2026-09-02 | AML/FinCrime/Fraud | 5 (3 ML) | RT, Mon, LLM*, Reg/MRM* |
| 38 | Elliptic | [Data Science Lead](https://jobs.ashbyhq.com/elliptic/4e5149ef-0e8f-462f-985e-ddc50e68a489) | London, United Kingdom | 2026-10-08 | AML/FinCrime/Fraud | - (PhD or pubs) | Mon, LLM*, Spark, Reg/MRM |
| 39 | Adyen | [Senior Machine Learning Engineer - AML Tech](https://job-boards.greenhouse.io/adyen/jobs/8288674) | Amsterdam | 2026-10-16 | AML/FinCrime | 7 | GBDT, DL, RT, K8s, LLM*, Spark, Reg/MRM |
| 40 | Sift | [Machine Learning Engineer](https://jobs.ashbyhq.com/sift/45b22605-1abb-483e-8ef7-5ceaf04f5868) | San Francisco, California | 2026-10-28 | Fraud/Identity/KYC | 4 | GBDT, DL, Graph, RT, Stream, K8s*, Mon, LLM*, Spark |
| 41 | Ramp | [Machine Learning Engineer](https://jobs.ashbyhq.com/ramp/2888b101-b1da-4e53-a02e-1bb9b1b5a951) | New York, NY (HQ) | 2026-09-23 | Fraud/Identity/KYC | 5 | DL, LLM |
| 42 | Brex | [Data Scientist II, Applied ML](https://www.brex.com/careers/8783482002?gh_jid=8783482002) | San Francisco, California, United States | 2026-10-01 | AML/FinCrime/Fraud | 3 | RT, Reg/MRM |
| 43 | TRM Labs | [Senior Data Scientist, Full Stack](https://jobs.ashbyhq.com/trm-labs/23df8728-7b04-4340-a767-07e8ce3c23dc) | North America | 2026-05-25 | AML/FinCrime/Fraud | 6 | RT, LLM, Spark, Reg/MRM |
| 44 | Robinhood | [Staff Data Scientist,  ML (Credit Risk)](https://boards.greenhouse.io/robinhood/jobs/7997218?t=gh_src=&gh_jid=7997218) | Menlo Park, CA | 2026-06-10 | Credit | 7 | Mon, Spark |
| 45 | Monzo | [Credit Model Validation Manager (Machine Learning & NPV Models)](https://job-boards.greenhouse.io/monzo/jobs/8023162) | Cardiff, London or Remote (UK) | 2026-06-23 | Credit | - | RT*, Mon, XAI, Reg/MRM |
| 46 | SoFi | [Senior Staff AI Engineer](https://sofi.com/careers/job/7593403003?gh_jid=7593403003) | CA - San Francisco | 2026-01-22 | Fraud | 8 | Graph, RT, K8s, Mon, XAI*, LLM, Reg/MRM |
| 47 | PayPal | [Staff Machine Learning Engineer](https://wd1.myworkdaysite.com/recruiting/paypal/jobs/job/San-Jose-California-United-States-of-America/Staff-Machine-Learning-Engineer_R0139065) | San Jose, California, United States of A | 2026-11-10 | Fraud/Identity/KYC/Credit | - | DL*, Graph, Mon |
| 48 | Capital One | [Principal Associate, Data Scientist - SBB Fraud](https://capitalone.wd12.myworkdayjobs.com/Capital_One/job/McLean-VA/Principal-Associate--Data-Scientist---SBB-Fraud_R1004467) | McLean, VA | 2026-10-28 | Fraud | 5 (BS) | DL, Spark, Reg/MRM |
| 49 | Capital One | [Associate, Data Scientist - US Card](https://capitalone.wd12.myworkdayjobs.com/Capital_One/job/McLean-VA/Associate--Data-Scientist---US-Card_R1005289-1) | McLean, VA | 2026-11-12 | Fraud/Credit | 0 (new BS grad) | DL, Spark, Reg/MRM |
| 50 | Capital One | [Manager, Data Science - Emerging ML](https://capitalone.wd12.myworkdayjobs.com/Capital_One/job/McLean-VA/Manager--Data-Science---Emerging-ML_R1005111-1) | McLean, VA | 2026-11-03 | Fraud | 6 (BS) | DL, LLM, Spark, Reg/MRM |
| 51 | Visa | [Data Scientist, Featurespace](https://visa.wd5.myworkdayjobs.com/Visa/job/GB---Cambridge-United-Kingdom/Data-Scientist--Featurespace_REF089210W-1) | GB - Cambridge, United Kingdom | 2026-10-26 | AML/FinCrime/Fraud | - | Mon, Reg/MRM |
| 52 | Visa | [Staff Data Scientist](https://visa.wd5.myworkdayjobs.com/Visa/job/US---Bellevue-WA/Staff-Data-Scientist_REF082941W) | US - Bellevue, WA | 2026-11-13 | Fraud | 5 | Mon, XAI, LLM, Spark* |
| 53 | Mastercard | [Senior Data Scientist](https://mastercard.wd1.myworkdayjobs.com/CorporateCareers/job/London-England-Devonshire-Square/Senior-Data-Scientist_R-290631) | London, England (Devonshire Square) | 2026-11-12 | AML/FinCrime/Fraud | - | Spark* |
| 54 | Mastercard | [Lead Data Scientist (Graph Analytics)](https://mastercard.wd1.myworkdayjobs.com/CorporateCareers/job/Toronto-Canada/Lead-Data-Scientist_R-293166) | Toronto, Canada | 2026-10-29 | Fraud | - | DL, Graph, GNN, Mon, Spark |
| 55 | JPMorgan Chase | [Applied AI Machine Learning Vice President (Fraud Modelling)](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210790266) | LONDON, United Kingdom | 2026-11-03 | Fraud/Identity/KYC | - | Mon, XAI*, LLM, Reg/MRM |
| 56 | JPMorgan Chase | [CCB Risk Modeling Senior Associate - Fraud Prevention](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210782163) | Wilmington, DE, United States | 2026-10-12 | Fraud | 3 | GBDT*, DL, Graph, Mon, LLM, Spark |
| 57 | JPMorgan Chase | [Data Scientist-Fraud Strategy-Vice President](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210790621) | Plano, TX, United States | 2026-09-23 | Fraud/Credit | 5 | Mon |
| 58 | Affirm | [Senior Machine Learning Engineer (Fraud)](https://job-boards.greenhouse.io/affirm/jobs/7806920003) | Remote Canada | 2026-07-21 | Fraud/Identity/KYC | 6 | GBDT*, DL*, Graph, FeatStore, RT, Mon, LLM, Spark* |
Source for every row: the URL in the table. Each is the employer's own ATS page, fetched 2026-11-17.

### Inferences
- The sample leans toward fintech and RegTech (Socure, Stripe, Plaid and Sardine together are 22 of 58). Banks and networks (Capital One, JPMorgan, Visa, Mastercard, PayPal) are 10 of 58. Bank postings stress SQL, Spark and model governance more, and they almost never name a serving stack.
- Two-thirds of postings are titled Data Scientist / Scientist (37) and one-third Engineer (21). In fraud, "data scientist" often means someone who builds and ships models, not only analytics. Socure DS II wants "developing and deploying deep learning models" ([Socure DS II](https://jobs.ashbyhq.com/socure/05533c4e-1c59-4ae8-b12c-6acad3757a77)). But a few DS roles really are analytics or strategy jobs: Chime Dispute Risk, Gemini Fraud DS, JPM Fraud Strategy VP.

### Gaps
- No postings from **Revolut, Monzo (fraud), Wise, Checkout.com, Feedzai, Unit21, Hawk AI, ComplyAdvantage, Nasdaq Verafin, Amex, Block/Cash App fraud ML**. Monzo, Wise, Feedzai and ComplyAdvantage public Greenhouse boards had no fraud-ML-titled roles open on 2026-11-17. Unit21, Hawk AI, Checkout.com, Featurespace and Amex returned no public Greenhouse/Ashby/Lever/Workday board under the obvious slug. Revolut's site is JavaScript-only. A web search found only closed Revolut fincrime DS listings on aggregators ([Wellfound, closed](https://wellfound.com/jobs/599929-data-science-product-owner-financial-crime)). LinkedIn and Indeed were not used (login walls).
- Featurespace appears only through its parent, Visa (row 51).
- The sample covers roles open on one day (a snapshot). Roles that already closed in 2026 are not in it.

## Q2. How often does each skill or tool appear? (counts and %)

### Takeaway
What fraud-ML postings ask for most is **production ownership** (93%), **model monitoring/drift** (59%), **real-time/low-latency decisioning** (50%; 71% of engineer roles), **deep learning** (48%), **graph methods** (40%) and **Python** (84%). Gradient boosting is named in only 21%, because it is mostly assumed. **Named infrastructure tools are rare.** Feast/Tecton/Chalk: 0/58. Ray Serve / KServe / BentoML / SageMaker by name: 0/58. Kafka: 1/58. Flink/Redpanda: 0. MLflow: 2/58. Kubernetes: 4/58. SHAP by name: 0/58. LLM/GenAI shows up in 59%, but about a third of those mentions are "use AI coding tools," not "build LLM systems."

### Cited Findings
Counts over N = 58 (engineer-titled n = 21, scientist-titled n = 37). "Pref-only" = postings where the tag appears only as nice-to-have. Every count comes from the per-posting tags in the Q1 table, which lists each source URL.

| Skill / tool | All (n=58) | % | Engineer roles (21) | Scientist roles (37) | Pref-only |
|---|---|---|---|---|---|
| Production / deployment language | 54 | 93% | – | – | 1 |
| Python | 49 | 84% | 15 | 34 | 10 |
| Domain experience phrase (fraud/AML/risk/identity/T&S) | 43 | 74% | – | – | **21** |
| Business impact / ownership language | 42 / 41 | 72% / 71% | – | – | – |
| SQL | 36 | 62% | 6 | 30 | 8 |
| Experimentation / backtest / A-B (broad) | 38 | 66% | – | – | 1 |
| — explicit A/B, controlled ramp, holdout | 8 | 14% | – | – | 0 |
| — champion/challenger or shadow | 2 | 3% | – | – | 0 |
| Model monitoring / drift / decay / recalibration | 34 | 59% | 13 | 21 | 5 |
| LLM / GenAI / agents (any mention) | 34 | 59% | 17 | 17 | 10 |
| — of which "use AI coding tools" (Claude Code, Cursor etc.) | 11 | 19% | 6 | 5 | 2 |
| Regulatory / governance / compliance / model-risk language | 31 | 53% | 7 | 24 | 2 |
| — explicit model risk management / MRM | 5 | 9% | – | – | 2 |
| Real-time / low-latency / online inference | 29 | 50% | 15 | 14 | 1 |
| Deep learning (any) | 28 | 48% | 13 | 15 | 6 |
| — PyTorch / TensorFlow named | 18 | 31% | – | – | 6 |
| End-to-end / full-lifecycle language | 27 | 47% | 12 | 15 | 2 |
| Spark / PySpark / Databricks | 24 | 41% | 5 | 19 | 5 |
| Graph (any: graph features, entity resolution, link analysis, graph DB, GNN) | 23 | 40% | 12 | 11 | 8 |
| — GNN named | 4 | 7% | – | – | 1 |
| Class imbalance / adversarial / delayed labels / precision-recall | 20 | 34% | – | – | 3 |
| PhD mentioned | 19 | 33% | 5 | 14 | 8 |
| Explainability / interpretability / reason codes | 16 | 28% | – | – | 5 |
| — SHAP named | 0 | 0% | – | – | – |
| Gradient boosting / tree ensembles | 12 | 21% | 6 | 6 | 3 |
| — XGBoost/LightGBM/CatBoost named | 10 | 17% | – | – | 4 |
| AWS | 9 | 16% | – | – | 3 |
| Feature store / feature platform / feature pipeline | 8 | 14% | 7 | 1 | 3 |
| — Feast / Tecton / Chalk named | **0** | 0% | – | – | – |
| GCP | 8 | 14% | – | – | 3 |
| Airflow / Kubeflow / Argo (orchestration) | 6 | 10% | – | – | 1 |
| dbt | 5 | 9% | – | – | 4 |
| Streaming / near-real-time data (any) | 4 | 7% | – | – | 1 |
| — Kafka named | 1 | 2% | – | – | – |
| Kubernetes / containers | 4 | 7% | 4 | 0 | 1 |
| Named serving framework (Ray, Triton, etc.) | 4 | 7% | – | – | 3 |
| Snowflake | 4 | 7% | – | – | 1 |
| Scala / Java / Go | 3 / 2 / 0* | – | – | – | – |
| MLflow / experiment tracking | 2 | 3% | – | – | 0 |
| Azure | 2 | 3% | – | – | 2 |

(*Go: Sardine's MLE says "our Go backend", which is a mention, not a requirement. The regex missed it.)

Specific examples behind the low-frequency infrastructure tags:
- **Feature stores**: "Hands-on ML infrastructure experience: feature stores, model management, ML training/serving pipelines" — [Middesk Lead DS](https://jobs.ashbyhq.com/middesk/7fd5aeb2-c33c-4f0a-ad3d-2161201bc174). "Familiarity with ML platform components (feature stores, model serving frameworks, training orchestration…)" — [Coinbase Sr ML Platform Eng, Identity](https://www.coinbase.com/careers/positions/8211490?gh_jid=8211490). Stripe Radar describes "large-scale data and feature pipelines, distributed model training, low-latency inference, model deployment, or production monitoring" as "several of" — [Stripe MLE Radar](https://stripe.com/jobs/search?gh_jid=7983456). None of the 58 names Feast, Tecton or Chalk.
- **Serving / K8s**: Sardine's MLE: "Build and own the model serving infrastructure, real-time inference, feature retrieval, and the latency budget… Comfort with Kubernetes, containers and a major cloud (we're mostly GCP)" — [Sardine MLE](https://jobs.ashbyhq.com/sardine/2c8f0342-b8af-4cc2-85cd-67bc48275568). Adyen AML: "k8s, docker, airflow, argo-workflows, prometheus, grafana" plus "MLFlow or similar MLOps frameworks" — [Adyen Sr MLE AML Tech](https://job-boards.greenhouse.io/adyen/jobs/8288674). **Ray** appears only twice: as "LangChain/LangGraph/Ray… is a plus" ([Socure DS II](https://jobs.ashbyhq.com/socure/05533c4e-1c59-4ae8-b12c-6acad3757a77)) and "Spark preferred; Ray/Dask or similar" for distributed compute ([Affirm Sr MLE Fraud](https://job-boards.greenhouse.io/affirm/jobs/7806920003)). Ray Serve itself is never named. Triton appears only in an LLM-inference context ([SoFi Sr Staff AI Eng](https://sofi.com/careers/job/7593403003?gh_jid=7593403003)).
- **Streaming**: the only named streaming tech is "Apache Kafka" at [Sift MLE](https://jobs.ashbyhq.com/sift/45b22605-1abb-483e-8ef7-5ceaf04f5868). Sift also describes a system that "dynamically recalibrates models based on streaming global telemetry data". Coinbase wants "low-latency streaming pipelines that deliver fresh, high-quality features" ([Coinbase](https://www.coinbase.com/careers/positions/8211490?gh_jid=8211490)).
- **GNN by name (4)**: "graph learning (including GNNs and link prediction)" — [Socure Head of DS, Identity Graph](https://jobs.ashbyhq.com/socure/b381b846-64df-48ac-9b37-c939255f1e90). "Build identity-graph systems using GNNs that cluster accounts sharing biometric, device…" plus required "at least two of: computer vision/biometrics, GNNs, sequence models, or NLP/LLMs" — [Coinbase Staff MLE Identity](https://www.coinbase.com/careers/positions/7891045?gh_jid=7891045). "graph algorithms, graph neural networks, or representation learning to detect fraud patterns" (preferred) — [Plaid Staff MLE Fraud](https://jobs.ashbyhq.com/plaid/85cd5d07-9920-45fa-931a-daf8c3558e5b). "community detection, link analysis, graph embeddings, and graph neural networks" — [Mastercard Lead DS Graph Analytics](https://mastercard.wd1.myworkdayjobs.com/CorporateCareers/job/Toronto-Canada/Lead-Data-Scientist_R-293166).
- **Graph broadly**: Stripe Radar: "Use graph, sequence, and LLM-based approaches over payment, account, and product data" — [Stripe Staff MLE Radar](https://stripe.com/jobs/search?gh_jid=8243615). JPMorgan: "novel architectures, including Graph Networks, Agentic AI, and Large Language Models" — [JPM CCB Risk Modeling Sr Assoc, Fraud](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210782163). Alloy lists "modeling on graph structures" as a nice-to-have — [Alloy Sr MLE](https://jobs.ashbyhq.com/5c335d0c-0c96-4b85-a913-db4ce4f02651/3ce8dae1-9bd4-4b0c-b19d-721be8f057c6).
- **Gradient boosting**: "tabular classification problems (preferably gradient-boosted decision trees like LightGBM/XGBoost/CatBoost)" — [Affirm](https://job-boards.greenhouse.io/affirm/jobs/7806920003). "highly imbalanced datasets… specific interest in tree-based models" — [Alloy](https://jobs.ashbyhq.com/5c335d0c-0c96-4b85-a913-db4ce4f02651/3ce8dae1-9bd4-4b0c-b19d-721be8f057c6). "both traditional and modern ML methods, including gradient-boosted trees and neural networks" — [Plaid Sr MLE Fraud](https://jobs.ashbyhq.com/plaid/e9a9aeab-be90-43f3-b898-63a846cb5777).
- **Leakage / time generalization by name**: "Experience constructing training datasets and addressing label quality, data leakage, class imbalance, and generalization across time periods or populations" (required) and "delayed feedback" (preferred) — [Plaid Sr MLE Fraud](https://jobs.ashbyhq.com/plaid/e9a9aeab-be90-43f3-b898-63a846cb5777). Adyen AML says "extremely unbalanced data" (nice-to-have) and "incomplete ground truth" — [Adyen](https://job-boards.greenhouse.io/adyen/jobs/8288674).
- **LLM / agents as product work**: Coinbase "designs and ships Agentic AI solutions that automate compliance processes" and requires "shipping LLM-based or Agentic AI applications to production" — [Coinbase Staff MLE Compliance Automation](https://www.coinbase.com/careers/positions/8333165?gh_jid=8333165). Block: risk "investigations and decision making… through the application of agentic and generative AI" — [Block Sr ML/AI Modeler](http://block.xyz/careers/jobs/5394441008?gh_jid=5394441008). Visa: "GenAI/LLM-based solutions for explainability, workflow…" — [Visa Staff DS](https://visa.wd5.myworkdayjobs.com/Visa/job/US---Bellevue-WA/Staff-Data-Scientist_REF082941W). Elliptic bonus: "agentic systems, LLM agents" — [Elliptic DS Lead](https://jobs.ashbyhq.com/elliptic/4e5149ef-0e8f-462f-985e-ddc50e68a489).
- **LLM as a tooling expectation**: "Proficient in using AI-powered developer tools (e.g., Claude Code, Cursor…)" — [Affirm](https://job-boards.greenhouse.io/affirm/jobs/7806920003); "AI coding assistants (e.g., Claude Code)" — [Sift](https://jobs.ashbyhq.com/sift/45b22605-1abb-483e-8ef7-5ceaf04f5868); "AI-assisted coding tools (Cursor, Claude Code)" — [TRM Labs](https://jobs.ashbyhq.com/trm-labs/23df8728-7b04-4340-a767-07e8ce3c23dc).
- **Model risk**: "Prepare complete governance and Model Risk Management packages, including development documentation…" — [JPM Applied AI ML VP, Fraud Modelling (London)](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210790266). "model risk management and documentation in a regulated financial environment" — [Sardine Sr Applied AI Research Scientist](https://jobs.ashbyhq.com/sardine/44cf5225-547a-4584-a271-c0c6ddc7b0b6). Chime credit: "adverse action reasons… Fair Lending, Model Risk Management" — [Chime Lead DS Credit Risk](https://boards.greenhouse.io/chime/jobs/8788322002?gh_jid=8788322002).
- **Champion/challenger** appears only in credit roles: "design and read out champion/challenger tests and controlled ramps" ([Chime Lead DS Credit Risk](https://boards.greenhouse.io/chime/jobs/8788322002?gh_jid=8788322002)) and "developing challenger models" ([Monzo Credit Model Validation](https://job-boards.greenhouse.io/monzo/jobs/8023162)).

### Inferences
- These postings describe **capabilities, not tool brands**. "Low-latency inference", "feature pipelines", "monitoring, drift detection, retraining, incident response" are common. "Feast", "Ray Serve", "Kafka" and "MLflow" almost never appear. So the project's specific tools (Feast, Ray Serve, k3s, Redpanda) will not match keywords in postings. What will match is the capability each one demonstrates: train/serve feature consistency, a p99 latency budget, streaming replay, drift monitoring and retraining.
- Engineer-titled roles are where real-time (15/21), feature pipelines (7/21) and Kubernetes (4/21) show up. Scientist-titled roles push SQL (30/37), Spark (19/37) and governance (24/37). The project spans both, which matches "full-stack ML" phrasing (TRM, Sardine, Block "full stack ML experience is strongly preferred").
- Graph appears in 40% of postings, but a GNN by name in only 7%, and one of those four lists it as preferred. A GraphSAGE-loses-to-XGBoost result written up honestly is relevant to what these teams do: Plaid, Stripe and Mastercard all frame graph as one tool among several to evaluate.
- An LLM investigator component matches a real and growing ask (Coinbase compliance automation, Block risk investigations, Visa GenAI for explainability, Elliptic, Sardine's "agentic risk platform"). But the most common LLM line is "use AI coding tools", which says nothing about LLM product skill.

### Gaps
- Keyword tagging cannot tell how central a skill is to the job. A single mention counts the same as a core duty.
- Cloud is rarely named (AWS 16%, GCP 14%), so this sample cannot say which cloud fraud teams prefer.
- No posting mentions Neo4j/TigerGraph or any graph database by name. Whether fraud teams use graph DBs could not be judged from these postings.

## Q3. What is "required" vs "nice to have"?

### Takeaway
Across postings the **hard requirements** are: years of production ML, Python (plus SQL for scientist roles), strong ML/statistics fundamentals, experiment/evaluation design, and shipping and monitoring models in production. **Fraud/AML domain experience is in 74% of postings, but in half of those (21/43) only as preferred.** GNNs, LLM product work, PhDs, real-time experience and specific MLOps tools are mostly **preferred**.

### Cited Findings
- Stripe states outright: "The preferred qualifications are a bonus, not a requirement." The Radar MLE minimums are 5+ years deploying production ML, "a track record of leading ML projects from problem definition to production, with measurable impact", "deep foundations in machine learning, statistics, model evaluation, and experiment design", "tested, maintainable code", and "several of" feature pipelines / distributed training / low-latency inference / deployment / monitoring. Preferred: fraud or adversarial-domain experience; "deep learning, graph-learning, or LLM-based approaches"; "real-time, low-latency ML systems" — [Stripe MLE Radar](https://stripe.com/jobs/search?gh_jid=7983456).
- Plaid Sr MLE Fraud requires leakage, class-imbalance and time-generalization skills plus "PyTorch, scikit-learn, XGBoost". It marks "Fraud or risk modeling experience, including familiarity with fraud patterns, delayed feedback…" as "Strongly preferred" — [Plaid](https://jobs.ashbyhq.com/plaid/e9a9aeab-be90-43f3-b898-63a846cb5777).
- Brex DS II: required "own end-to-end model development, including productionization", Python/SQL, A/B testing, "API development and integrating ML systems into production services". Nice to have: "real-time models", "advanced degree… or published research", "risk domain (fraud, AML, and/or credit)" — [Brex](https://www.brex.com/careers/8783482002?gh_jid=8783482002).
- Alloy: domain ("Previous experience in financial fraud detection") and graph modelling are **nice-to-haves**. Imbalanced data and tree models are required — [Alloy](https://jobs.ashbyhq.com/5c335d0c-0c96-4b85-a913-db4ce4f02651/3ce8dae1-9bd4-4b0c-b19d-721be8f057c6).
- Adyen AML: the full ML lifecycle, MLOps tools (MLflow, Airflow, k8s) and XGBoost/LightGBM are required. "Finance domain experience", "extremely unbalanced data" and "Production LLM experience" are nice-to-have — [Adyen](https://job-boards.greenhouse.io/adyen/jobs/8288674).
- Socure DS II: "Experience in fraud prevention, risk modeling, or identity verification is a plus"; "real-time model inferencing is a plus"; LLM/agentic frameworks "a plus" — [Socure DS II](https://jobs.ashbyhq.com/socure/05533c4e-1c59-4ae8-b12c-6acad3757a77).
- Domain is a **hard requirement** where the role is about fraud strategy or is a senior specialist role: Oscilar ("5+ years… with a focus on fraud prevention and/or anti-money laundering" — [Oscilar](https://jobs.ashbyhq.com/oscilar/a83cfe5b-5a34-4aa7-9e4d-52ca6428efc6)); Gemini ("5+ years in fraud strategy…" — [Gemini](https://boards.greenhouse.io/embed/job_app?for=gemini&token=7905301&gh_jid=7905301)); Coinbase Identity ("Domain experience in identity verification, biometrics, or account integrity", "translating KYC/AML requirements… into ML roadmaps" — [Coinbase](https://www.coinbase.com/careers/positions/7891045?gh_jid=7891045)); Middesk ("7+ years of production ML experience in… risk, fraud, credit, or trust & safety" — [Middesk](https://jobs.ashbyhq.com/middesk/7fd5aeb2-c33c-4f0a-ad3d-2161201bc174)); JPM fraud strategy VP ("minimum 5 years of experience in Fraud Strategy" — [JPM](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210790621)).
- PhD: mentioned in 19 of 58, only-preferred in 8. Effectively required for research-scientist titles: Persona wants "a demonstrated record of peer-reviewed publications" ([Persona](https://jobs.ashbyhq.com/persona/7c498972-86f4-4513-b796-46f8854a3690)); Elliptic wants "A PhD or equivalent research training, or a record of published applied research" ([Elliptic](https://jobs.ashbyhq.com/elliptic/4e5149ef-0e8f-462f-985e-ddc50e68a489)). Affirm: "Relevant PhD can count for up to 2 years of experience" ([Affirm](https://job-boards.greenhouse.io/affirm/jobs/7806920003)).

### Inferences
- For a career-switcher, the gate is "production ML with measurable impact" and not "fraud experience". Fintechs (Stripe, Plaid, Brex, Alloy, Adyen, Socure) treat domain as a bonus. Specialist vendors and bank strategy roles treat it as required.
- Skills that are required **and** directly shown by this project: leakage-safe dataset construction, imbalance handling, time-based generalization, evaluation/experiment design, tested production code, monitoring. These line up word-for-word with Plaid's and Stripe's minimums.

### Gaps
- The required-vs-preferred split is a heuristic based on section headings. Some postings have no headings (e.g. Mercury's "You should have / you also have" format), which can misplace items.

## Q4. What do postings say about portfolio-type evidence (end-to-end ownership, production impact)?

### Takeaway
Postings ask for **proof of ownership in production**: "track record", "from problem definition to production", "measurable impact", "you've been paged". 93% use production/deployment language, 71% ownership language, 72% impact language and 47% explicitly say end-to-end or full lifecycle. Outside research roles, almost none mention GitHub, Kaggle or personal portfolios. Evidence is framed as *shipped and measured*, not *built and shown*.

### Cited Findings
- "A track record of leading ML projects from problem definition to production, with measurable impact" — [Stripe MLE Radar](https://stripe.com/jobs/search?gh_jid=7983456) and [Stripe MLE Transaction Risk](https://stripe.com/jobs/search?gh_jid=8187574).
- "Production ownership of ML systems: you've been paged when something broke, you found out why, and you changed something so it didn't happen again… Own models in production: monitoring, drift detection, retraining, incident response, and the on-call rotation" — [Sardine MLE](https://jobs.ashbyhq.com/sardine/2c8f0342-b8af-4cc2-85cd-67bc48275568).
- "Hands-on experience designing, training, tuning, and deploying models, and measuring improvements in production performance or business metrics" — [Plaid Sr MLE Fraud](https://jobs.ashbyhq.com/plaid/e9a9aeab-be90-43f3-b898-63a846cb5777).
- "Demonstrated ability to own end-to-end model development, including productionization" — [Brex](https://www.brex.com/careers/8783482002?gh_jid=8783482002). "Track record of delivering high impact machine learning models in a low latency live setting" — [Affirm](https://job-boards.greenhouse.io/affirm/jobs/7806920003).
- "7+ years of hands-on machine learning experience, with a demonstrated track record of personally developing, deploying, and optimizing predictive models" — [Dave Lead ML Scientist](https://jobs.ashbyhq.com/dave/c85a73ba-ed1c-4def-9aed-161ba7779c6b).
- Featurespace/Visa describes the job as the full loop: "Take models from discovery and experimentation through to production. Monitor deployed models… Retrain, enhance and safely release models… Measure and communicate the impact… Contribute to model governance, documentation" — [Visa DS, Featurespace](https://visa.wd5.myworkdayjobs.com/Visa/job/GB---Cambridge-United-Kingdom/Data-Scientist--Featurespace_REF089210W-1).
- Mastercard financial-crime DS: "Conduct Proof-of-Value exercises with customers to demonstrate model performance and business impact" — [Mastercard Sr DS London](https://mastercard.wd1.myworkdayjobs.com/CorporateCareers/job/London-England-Devonshire-Square/Senior-Data-Scientist_R-290631).
- Public artifacts are named only in research roles: "publications, patents, open-source work, or internal research adopted in…" — [Plaid Staff MLE (Research Scientist)](https://jobs.ashbyhq.com/plaid/5e56c0a6-3caa-4255-8c63-95c29cbc2a32); "Publications, released models, or open source contributions" — [Sardine](https://jobs.ashbyhq.com/sardine/44cf5225-547a-4584-a271-c0c6ddc7b0b6). SoFi's AI-engineer role is the one non-research posting that says "a portfolio demonstrating" (agentic LLM work) — [SoFi](https://sofi.com/careers/job/7593403003?gh_jid=7593403003).

### Inferences
- A portfolio project cannot claim real production impact. The closest stand-in for what these postings measure is to *simulate the production loop and report numbers from it*: p99 latency under load, alerts per analyst-hour at a fixed precision@k, drift detected and retrain triggered on the time-ordered replay, a model card / governance package. The Featurespace and Sardine descriptions read almost like a checklist for such a project.
- "Measurable impact" in fraud means business metrics (fraud caught vs good users blocked, approval rate, dollars). Precision@k and a capacity slider translate directly into that language.

### Gaps
- Postings do not say how they weigh a self-built project against employment history. No posting in the sample addresses non-employment evidence explicitly.

## Q5. Is there any signal for entry/mid-level hiring of people switching from software / AI-app engineering into ML?

### Takeaway
The market in this niche is **senior-heavy**. 41 of 58 titles are Senior, Staff, Lead, Principal or Head, and another 5 are managers. Among the 46 IC postings that state years, the median minimum is **6 years**, and only 6 ask for 3 or fewer. Paths that do exist for a software engineer: (a) **ML platform / serving-focused MLE roles** that count software-engineering years and openly downplay model training; (b) postings that count "software engineering for ML" toward the years; (c) the "or equivalent practical experience" clause in 15 postings.

### Cited Findings
- Distribution of headline minimum years (46 IC postings with a number): ≤3 yrs: 6; 4–6: 18; 7–9: 16; ≥10: 6; median 6. Title levels: Senior 16, Staff 15, Lead/VP 7, Manager 5, Head 2, Principal 1, mid/II/unspecified 11, Associate 1. Source: the "Min yrs" column of the Q1 table.
- The few roles open at ≤3 years: [Capital One Associate DS, US Card](https://capitalone.wd12.myworkdayjobs.com/Capital_One/job/McLean-VA/Associate--Data-Scientist---US-Card_R1005289-1) (bachelor's degree only; "At least 1 year experience with machine learning" is *preferred*; no visa sponsorship); [Socure DS II Fraud & Risk](https://jobs.ashbyhq.com/socure/05533c4e-1c59-4ae8-b12c-6acad3757a77) ("2-4 years… developing and deploying deep learning models"); [Chime DS Dispute Risk](https://boards.greenhouse.io/chime/jobs/8904126002?gh_jid=8904126002) (2+ yrs, analytics-leaning, SQL first); [Brex DS II Applied ML](https://www.brex.com/careers/8783482002?gh_jid=8783482002) (3+ yrs, "Strong software engineering fundamentals, including experience with API development"); [Socure DS II RiskOS](https://jobs.ashbyhq.com/socure/5337e747-bc84-4c2d-8f5e-042cf64bc80e) (3–6 yrs); [JPM CCB Risk Modeling Sr Assoc](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210782163) (3 yrs in predictive risk models at financial institutions).
- The strongest switcher signal: Sardine's MLE says "Experience building, not just using, model serving infrastructure… Strong Python, and solid software engineering fundamentals, testing, code review, CI/CD… Enough understanding of models to debug them. **You don't need to have trained one recently**, but when precision drops you should know the difference between a data problem, a feature pipeline problem, and a model problem" — [Sardine MLE](https://jobs.ashbyhq.com/sardine/2c8f0342-b8af-4cc2-85cd-67bc48275568) (first published 2025-09-09, still live).
- Coinbase's ML Platform Engineer (Identity) asks for "5+ years of industry experience as a software engineer, with demonstrated ownership of distributed systems in production" plus familiarity with "feature stores, model serving frameworks, training orchestration" — [Coinbase](https://www.coinbase.com/careers/positions/8211490?gh_jid=8211490).
- Plaid counts "7+ years of professional experience in machine learning, applied science, **or software engineering for ML**" — [Plaid Sr MLE](https://jobs.ashbyhq.com/plaid/e9a9aeab-be90-43f3-b898-63a846cb5777). Coinbase Compliance Automation counts "8+ years in machine learning and software engineering, with demonstrated experience shipping LLM-based or Agentic AI applications to production" — [Coinbase](https://www.coinbase.com/careers/positions/8333165?gh_jid=8333165). That is a fraud/AML-adjacent role that values LLM-application shipping directly.
- "Or equivalent practical/professional experience" appears in 15 of 58 postings, e.g. [Socure Staff DS Fraud & Risk](https://jobs.ashbyhq.com/socure/2d652fb5-55b0-42d0-a75d-dd7511721441), [Dave](https://jobs.ashbyhq.com/dave/c85a73ba-ed1c-4def-9aed-161ba7779c6b), [Visa/Featurespace](https://visa.wd5.myworkdayjobs.com/Visa/job/GB---Cambridge-United-Kingdom/Data-Scientist--Featurespace_REF089210W-1), [JPM](https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210782163).
- Stripe encourages applicants who miss the preferred list: "The preferred qualifications are a bonus, not a requirement" — [Stripe](https://stripe.com/jobs/search?gh_jid=7983456).

### Inferences
- For someone with years of AI-app / software engineering but no trained-and-deployed model, the realistic targets in this sample are: ML-platform / serving MLE roles (Sardine MLE, Coinbase ML Platform); LLM/agentic compliance roles (Coinbase Compliance Automation, Block Risk Automation, Socure backend/agentic); and mid-level applied roles that weigh software fundamentals (Brex DS II, Socure DS II). Pure research-scientist and staff fraud-modeling roles (Persona, Plaid RS, Socure Staff/Head) are out of reach without modeling history.
- That argues for a portfolio that leads with the **serving and operations half** (latency budget, train/serve parity, monitoring, retraining) *plus* a rigorous model-evaluation story (leakage contract, precision@k, honest GNN loss). Those are the two things these postings ask a switcher to prove.

### Gaps
- Postings do not reveal how many hires are career-switchers. The sample has no explicit "career changer welcome" language and no apprenticeship-style fraud-ML roles.
- Capital One's Associate role is new-grad-oriented and excludes visa sponsorship. It is a weak signal for experienced switchers.
