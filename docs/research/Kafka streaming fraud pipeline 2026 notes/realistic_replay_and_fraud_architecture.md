# Realistic replay of a transaction stream, and how real fraud/AML systems sit around the stream (as of Nov 2026)

Scope note: about 22 tool calls. Primary sources are preferred. Vendor claims are marked **[vendor claim]**. Items older than 2024 are marked **[older: year]**. Where something comes from my background knowledge rather than a fetched source, it sits under *Inferences* or *Gaps*, never under *Cited Findings*.

---

## 1. Event time vs processing time, replay pacing, deterministic order under timestamp ties

### Takeaway
Real systems keep two clocks on every event: when it happened (event time) and when the system saw it (processing time). A good replay keeps event time fixed and copied from the source data, uses one deterministic tie-break key, and lets processing time be whatever the replay pacing produces. Correctness must depend only on event time plus that tie-break, so true-time, accelerated and as-fast-as-possible replays all give the same decisions.

### Cited Findings
- Akidau's "Streaming 101/102" set the standard split between event time (when an event happened) and processing time (when the system observes it), and argue that correct results need analysis by event time **[older: 2015-2016]** — [Streaming 102, O'Reilly](https://oreilly.com/ideas/the-world-beyond-batch-streaming-102); [Streaming 101, O'Reilly](https://oreilly.com/radar/the-world-beyond-batch-streaming-101)
- Watermarks are propagated from event sources through processors so that order-dependent processing can run on out-of-order streams. The VLDB 2021 paper (Begoli, Akidau et al.) compares their semantics in Flink and Google Dataflow **[older: 2021]** — [VLDB 2021, "Watermarks in Stream Processing Systems"](https://vldb.org/pvldb/vol14/p3135-begoli.pdf)
- Flink docs: watermarks track event-time progress and can advance independently of wall-clock time. That is exactly what makes accelerated replay possible: event time moves as fast as the data arrives — [Apache Flink docs, Time](https://ci.apache.org/projects/flink/flink-docs-master/docs/concepts/time/)
- Feedzai's Railgun paper argues that fraud detection needs *exact* sliding windows, not hopping windows. A hopping window with a 1-minute hop can miss events that a true sliding window counts, which "jeopardiz[es] metric accuracy (violating regulatory rules)". Railgun reports p99.9 < 250 ms at 1M events/s **[older: VLDB 2021]** — [Railgun arXiv 2009.00361](https://arxiv.org/pdf/2009.00361); [Railgun VLDB version, arXiv 2106.12626](https://arxiv.org/pdf/2106.12626)
- A Feedzai blog says Railgun handles "thousands of events per second". That is far below the paper's 1M/s, so the marketing and the paper describe different setups **[vendor claim, 2023]** — [Feedzai blog](https://www.feedzai.com/blog/feedzai_reinvents_fraud-detection-with-near-limitless-real-time-data-processing/)

### Inferences
- **Pacing modes.** (a) *True-time*: sleep so that wall-clock gaps match event-time gaps. 18 days of data takes 18 days. Useful only for a long-running live demo. (b) *Accelerated by factor N*: gap/N. The common choice for demos; for example ×60 replays a day in 24 minutes. (c) *As-fast-as-possible*: no sleeping. Used for backtests and throughput tests. Make the mode one config value. All three must produce byte-identical decisions. That is a strong test to put in CI: replay one slice at ×∞ and at ×600, then assert that the decision tables match.
- **Ties at minute resolution.** The sort key should be `(event_time, source_row)`. This is the same total order the project already uses (FINDING-010). Write it into the Kafka message as an explicit `seq` field, and also set the Kafka record timestamp to `event_time` (CreateTime). The consumer then never needs wall-clock time to decide order.
- **Partitioning and order.** Kafka orders records only within a partition. If the topic is keyed by sender account, two transactions for the same account stay in order, but cross-account order is lost between partitions. Features that read both sender *and* receiver state (fan-in/fan-out) can then see the receiver's state "from the future" when the other partition runs ahead. Options: 1 partition (simplest, and fine for about 5M events); or partitions plus a consumer that buffers until a low watermark passes; or score on arrival but read the feature store only *as of* the event's `(event_time, seq)`. For a single-box portfolio project, one partition (or keying that matches how state is read) plus an explicit `seq` is the defensible choice. Write that reason down.
- **Spreading events within a minute.** For true-time or accelerated pacing, the producer can spread a minute's ties evenly over that minute of processing time (by seq). This gives arrival times that look smooth. Event time stays the minute value. Do not invent sub-minute event times as if they were real data.

### Gaps
- I did not fetch Kleppmann's DDIA 2nd edition text, so I cannot quote its chapter on stream processing or its publication status in Nov 2026.
- I found no primary source on how a specific payments company paces its internal replays.

---

## 2. Realistic imperfections and how to inject them without breaking point-in-time correctness

### Takeaway
Inject faults at the *transport* layer (duplicates, delays, reordering, restarts, malformed payloads). Never inject them into the *event-time* fields used for features and labels. The consumer must be idempotent: dedupe on a transaction id, and commit offsets only after the decision is written. Late events are scored on arrival using state as of their event time, with the lateness recorded. They are not dropped by a window. Ready tools exist for network faults (Toxiproxy) and Kafka-level duplicates (Conduktor Gateway). Reordering is usually produced by your own producer logic.

### Cited Findings
- Flink: late elements are those that arrive after the watermark has passed their timestamp. Holding the watermark back to catch all late data delays results. Allowed lateness is an event-time timeout after which window state can be cleared — [Flink docs](https://ci.apache.org/projects/flink/flink-docs-master/docs/concepts/time/); [Packt, Flink windows](https://subscription.packtpub.com/book/data/9781800564930/2/ch02lvl1sec09/assigning-data-to-windows)
- *Streaming Systems* (Akidau, Chernyak, Lax) frames allowed lateness as garbage collection: "When: Allowed Lateness" **[older: 2018]** — [O'Reilly ebook](https://assets.contentstack.io/v3/assets/bltac01ee6daa3a1e14/blt87da7c3c9141c8df/679781f7e8de9f43b4c7ce40/ebook-oreilly-streaming-systems.pdf)
- Toxiproxy injects latency, timeouts, bandwidth limits and connection cuts between client and broker. It does not duplicate or reorder messages — [Conduktor glossary, chaos engineering for Kafka](https://conduktor.io/glossary/chaos-engineering-for-kafka)
- Conduktor Gateway has a `DuplicateMessagesPlugin` interceptor, set per topic with a rate percentage, meant for testing idempotency (for example "double-charged" payments) **[vendor tool docs]** — [Conduktor chaos-testing docs](https://docs.conduktor.io/guide/use-cases/chaos-testing)
- Out-of-order delivery relative to source time can be caused by network partitions between brokers. A suggested test for consumers is to complete offsets out of order and prove the commit frontier never passes a hole — [Conduktor glossary](https://conduktor.io/glossary/chaos-engineering-for-streaming-systems); [OneUptime, testing at-least-once consumers, 2026](https://oneuptime.com/blog/post/2026-07-22-test-at-least-once-consumers/view)
- Gremlin and LitmusChaos publish Kafka experiments: broker kill, network latency, and so on — [Gremlin, first 4 chaos experiments on Kafka](https://www.gremlin.com/community/tutorials/the-first-4-chaos-experiments-to-run-on-apache-kafka); [dev.to, Kafka chaos with Litmus](https://dev.to/kondareddy103/kafka-chaos-engineering-with-litmus-fng)
- Kafka 4.0 (March 2025): the KIP-848 consumer rebalance protocol is GA. It is enabled on the server by default but is opt-in on the client (`group.protocol=consumer`). Client-side assignors are unsupported and `session.timeout.ms`/`heartbeat.interval.ms` no longer apply on the client. A dev-list post plans to make it the default in 5.0 — [Kafka 4.0 release announcement](https://kafka.apache.org/blog/2025/03/18/apache-kafka-4.0.0-release-announcement/); [Kafka docs, consumer rebalance protocol](https://kafka.apache.org/40/operations/consumer-rebalance-protocol/); [dev@kafka mail archive](https://go.mail-archive.com/dev@kafka.apache.org/msg146291.html)
- The Flink StateFun fraud example uses exactly-once Kafka egress, so re-running from a checkpoint produces the same alerts with "no duplicate alerts during JM failover" — [Flink StateFun fraud example](https://kzmlabs.github.io/flink-statefun/examples/fraud-detection/)

### Inferences
Catalogue of imperfections, each with a point-in-time-safe way to simulate it:

| Imperfection | How to simulate (seeded, logged) | What the consumer must do |
|---|---|---|
| **Late / out-of-order arrival** | Producer holds back a seeded fraction (e.g. 1-2%) and emits them X seconds of *processing time* later. `event_time` and `seq` are unchanged | Score on arrival. Features read state as of `(event_time, seq)`, not "latest". Record `arrival_time`, `lateness = arrival − event_time`, and a `late` flag. Since there is no windowed aggregate to close, a watermark is needed only for *aggregate reports* (alerts/hour), not for scoring |
| **Duplicate delivery** | Producer re-sends a seeded fraction with the same `txn_id`. Or Conduktor Gateway's duplicate interceptor. Or the natural duplicate: kill the consumer between write and commit | Dedupe by `txn_id` (unique key / `ON CONFLICT DO NOTHING` in Postgres). The decision is written in the same DB transaction as the stored offset, or offsets are committed after the DB commit (at-least-once + idempotent sink) |
| **Bursts / diurnal pattern** | AMLworld already has its own time distribution, so do not alter event times. Bursts come from pacing. In accelerated mode, add a seeded "burst" multiplier for chosen windows to test backpressure and lag | Watch consumer lag (records and seconds). Latency SLO measured as `decision_time − arrival_time` |
| **Malformed records** | Seeded fraction of corrupted payloads (missing field, wrong type, negative amount, unknown currency) | Validate against the schema (Pandera / JSON Schema / Avro). Send to a dead-letter topic with the reason. Never score. Count it |
| **Schema evolution mid-stream** | At a chosen offset, switch the producer to schema v2 (add an optional field, e.g. `channel`). Use a schema registry (Apicurio / Karapace / Confluent SR) with BACKWARD compatibility | Consumer reads v1 and v2. A test proves that a non-compatible change (removing a required field) is rejected by the registry |
| **Broker restart** | `docker restart` the broker (single node) during replay | Producer `enable.idempotence=true` (the default since Kafka 3.0), `acks=all`. Consumer resumes from its committed offset. Assert zero lost and zero double-written decisions |
| **Consumer crash / restart** | Kill -9 the consumer at seeded points, including between DB write and offset commit | Same idempotent-sink assertion. Rebuild in-memory feature state from the store, or replay from a snapshot offset |
| **Network partition / latency** | Toxiproxy between consumer and broker, or between consumer and Redis/Postgres | Timeouts, retries with backoff, and a clear fail mode (queue for manual review vs fail-open). That ties to the existing 503 behaviour |
| **Clock skew** | Add a seeded skew to *producer-stamped* `ingest_time` only. Event time stays from the source | Never use the consumer's wall clock in features. Show skew as a monitoring metric |

- Rule of thumb: **every injected fault is seeded and written to a fault log**. A replay with faults then gives the *same* decisions as a clean replay, apart from rows that are explicitly allowed to differ (the DLQ). That "decision parity under chaos" test is the strongest evidence of correctness for a reviewer.
- Kafka transactions (`read_committed` + transactional producer) give exactly-once only for Kafka→Kafka. When the sink is Postgres, at-least-once plus an idempotent write is the standard, honest pattern (common Kafka practice; see the StateFun example above for the Kafka-egress case).

### Gaps
- I did not fetch the Kafka docs section on idempotence/transactions in this session. Treat "idempotence default since 3.0" as background knowledge to confirm in the Kafka docs (`kafka.apache.org/documentation/#semantics`).
- I found no single open-source tool that injects duplicates, reordering *and* network faults together.

---

## 3. Label delay / verification latency

### Takeaway
In reality, most labels arrive weeks to months after the transaction. Only the small set of alerts that investigators check gets a fast label, and that set is biased. The academic standard (Dal Pozzolo et al.) models two label streams: fast investigator *feedbacks* on the k alerted cases, and *delayed supervised samples* for everything else after δ days. A replay should emit labels as a **separate Kafka topic** with a `label_known_at` timestamp. Evaluation should be prequential with delay, not instant test-then-train.

### Cited Findings
- Dal Pozzolo, Boracchi, Caelen, Alippi, Bontempi (IEEE TNNLS 2018, "Credit Card Fraud Detection: A Realistic Modeling and a Novel Learning Strategy") name verification latency, the alert-feedback interaction and class imbalance as core challenges. They say "most papers in the literature ignore the verification latency" **[older: 2017/2018]** — [paper PDF](https://boracchi.faculty.polimi.it/docs/2017_FraudsTNNLS.pdf)
  - Two kinds of supervision: (i) investigator **feedbacks**, "limited in number but refer to recent transactions", and (ii) **delayed supervised samples**, "the vast majority", whose labels arrive "after several days (e.g. one month)". Unreported transactions are "considered genuine by default" after a number of days without a cardholder dispute — same PDF, §II-C
  - Formal model: each day the top-k alerts are checked (k = maximum alerts investigators can check, e.g. k = 100 cards). Feedbacks are all recent transactions of the k controlled cards. Labels of all transactions from day t−δ become available at day t. In their experiments δ = 7 (and δ = 15 in a sensitivity test), with M = 8 days of delayed samples, Q = δ + M = 15 days of feedbacks — same PDF, §III and §VI
  - Feedbacks are subject to **sample selection bias** (the model chose them, and their fraud share differs from the base rate). So they train one classifier on feedbacks and another on delayed samples, then aggregate the two. This raised alert precision. Metric: alert precision P_k and card precision CP_k (precision@k per day). Data: >75 million e-commerce card transactions (2013 and 2014-2015 datasets) — same PDF
  - The authors note their constant-δ model is a simplification: "the delayed supervised couples do not come all-at-once, as each disputed transaction might take less (or possibly more) than δ days" — same PDF, §III
- Earlier conference version: "Credit card fraud detection and concept-drift adaptation with delayed supervised information" (IJCNN 2015) **[older: 2015]** — [Boracchi IJCNN 2015 text](https://boracchi.faculty.polimi.it/docs/boracchi15IJCNN_Fraud.txt); [2015 PDF](https://boracchi.faculty.polimi.it/docs/2015_04_Credit_Card_Fraud_Detection_DalPozzolo_Boracchi_Caelen_Alippi_Bontempi.pdf)
- Grzenda, Gomes, Bifet, "Delayed labelling evaluation for data streams" (Data Mining and Knowledge Discovery 34(5), 2020). They argue standard prequential (test-then-train) evaluation is wrong under verification latency and propose **continuous re-evaluation**: score a prediction at several points before the label arrives **[older: 2019/2020]** — [Springer DMKD](https://link.springer.com/article/10.1007/s10618-019-00654-y); companion IJCNN 2020 measures paper — [Waikato preprint](https://researchcommons.waikato.ac.nz/bitstream/10289/14000/8/IJCNN_Delayed_Labeling_2020-preprint.pdf)
- Survey of semi-supervised learning for delayed, partially labelled streams — [arXiv 2106.09170](https://arxiv.org/pdf/2106.09170)
- **Card fraud label clocks**: the Visa cardholder dispute window is generally 120 days from transaction (or expected delivery/service) date, with exceptions up to 540 days and some as short as 75 days. Sources disagree on when the fraud clock starts **[secondary/vendor sources: chargebacks911, ClearSale]** — [Chargebacks911, Visa time limits](https://chargebacks911.com/chargeback-rules/chargeback-time-limits/visa-chargeback-time-limit/); [ClearSale](https://www.clear.sale/blog/understanding-visa-chargeback-time-limits); Adyen's own dispute timeframes page — [Adyen docs](https://docs.adyen.com/risk-management/understanding-disputes/dispute-timeframes)
- **AML label clocks (US)**: a SAR is due no later than 30 calendar days after "initial detection of facts that may constitute a basis for filing". This can extend by 30 more days to find a suspect, but never more than 60 days after detection. Urgent ongoing laundering also needs an immediate phone call to law enforcement — [eCFR 31 CFR 1020.320](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1020/subpart-C/section-1020.320); [FinCEN SAR FAQs, Oct 2025](https://www.fincen.gov/system/files/2025-10/SAR-FAQs-October-2025.pdf); [FinCEN SAR filing instructions](https://www.fincen.gov/sites/default/files/shared/FinCEN%20SAR%20ElectronicFilingInstructions-%20Stand%20Alone%20doc.pdf)
- AMLworld advertises "perfect tagging" of laundering, which "is essentially impossible with real data, where tags typically miss a great deal of laundering activity" (Altman et al., NeurIPS 2023 D&B) **[older: 2023]** — [arXiv 2306.16424](https://arxiv.org/abs/2306.16424v3)

### Inferences
- **AML is slower than card fraud.** The SAR clock starts at *detection*, after the alert is raised and triaged. So "label known" = alert time + queue wait + investigation (≤30-60 days to file). Undetected laundering may never get a label (false negatives stay labelled 0). The label stream should reflect that: in real AML, ground truth arrives mainly *for alerted cases*.
- **Simulation design for this project** (keeps point-in-time correctness):
  1. Topic `labels`, separate from `transactions`. Each label event: `{txn_id, label, label_source ∈ {investigator, delayed_truth}, label_known_at}`.
  2. *Investigator feedback*: when an alert is closed in the review queue (simulated investigator capacity k/day), emit its label at `alert_time + review_delay` (seeded distribution, e.g. lognormal in days, capped by queue position).
  3. *Delayed truth*: for every laundering transaction not alerted, emit the label at `event_time + D`, D drawn from a seeded distribution (e.g. 30-120 days). Some fraction never arrives, to mimic missed laundering. Since AMLworld spans only 18 days, at any realistic δ almost no delayed labels arrive inside the dataset. That is itself a finding to state plainly. A compressed δ (e.g. 3-7 days, as Dal Pozzolo used δ=7) can be offered as a clearly labelled "what-if".
  4. Retraining (Phase 8) may use only labels with `label_known_at ≤ training_cutoff`. This extends the leakage contract to labels. The project's `gold.labels.label_known_at` column already exists for this.
  5. Evaluation: report both precision@k with *eventual* labels (offline truth) and the metric as it was *visible* at each date (delayed). Grzenda et al.'s continuous re-evaluation is the citation.
- Sample-selection bias: training only on investigator-confirmed alerts teaches the model its own past blind spots. Dal Pozzolo's two-model split is the standard reference answer.

### Gaps
- I found no primary industry data on the *distribution* of AML investigation times (median days from alert to SAR) at named banks. Only the regulatory ceiling (30/60 days) is primary.
- The Visa rule text itself was not fetched (it sits behind Visa's Core Rules PDF). The 120-day figures come from secondary/vendor pages.

---

## 4. How payment/fraud companies use replay, backtesting, shadow mode and champion/challenger

### Takeaway
Industry practice has three stages: (1) **backtest** a rule or model on historical traffic before launch (Stripe, Sardine, Unit21 all expose this to customers); (2) run it in **shadow mode** on live traffic, logging decisions without acting (Uber: >75% of critical online models; Sardine: at least a week for new rules); (3) **promote** through champion/challenger or a canary. Public material is mostly product docs and marketing. Engineering detail is rare outside Uber and Stripe.

### Cited Findings
- **Stripe Radar:** before you add or update a rule, Radar searches historical live-mode payments that match it and shows the counts/amounts that would have been blocked vs succeeded. Custom backtests can be run in Stripe Sigma — [Stripe docs, Testing Radar / rules](https://docs.stripe.com/radar/rules); [Stripe Radar Rules 101](https://stripe.com/en-ca/guides/radar-rules-101); [Stripe guide, improve fraud management with Radar and Stripe Data](https://stripe.com/guides/improve-fraud-management-with-radar-and-stripe-data)
- Stripe Radar ML engineering: moved from a Wide & Deep ensemble (which included XGBoost) to a multi-branch DNN-only design inspired by ResNeXt. Radar scores 1,000+ signals and decides in under 100 ms. (Training-time and recall figures come via ByteByteGo/LinkedIn summaries, which are secondary.) — [Stripe blog, How we built it: Stripe Radar](https://stripe.com/blog/how-we-built-it-stripe-radar); [ByteByteGo summary](https://blog.bytebytego.com/p/how-stripe-detects-fraudulent-transactions)
- I did not find a public Stripe doc describing a shadow mode for Radar rules.
- **Uber Michelangelo (Oct 2025):** shadow testing runs a candidate model in parallel on identical live inputs, logging outputs without affecting users. It covers ">75% of critical online use cases" with a target of 100% in 2025 H2. There are two modes: automated deployment shadow (prediction-drift focus) and endpoint shadowing (custom traffic split and metrics). Backtesting on historical production data catches regressions "invisible in aggregate metrics" — [Uber Engineering, Raising the Bar on ML Model Deployment Safety](https://www.uber.com/gb/en/blog/raising-the-bar-on-ml-model-deployment-safety)
- **Sardine:** its rules engine says you can backtest on history, run in shadow mode on live traffic and A/B test strategies. Its blog advises keeping new rules in shadow mode for at least a week **[vendor claim]** — [Sardine rules engine](https://sardine.ai/rules-engine); [Sardine blog, fraud rules](https://www.sardine.ai/blog/fraud-rules); [Sardine backtesting](https://www.sardine.ai/learn/backtesting)
- **Unit21:** "backtesting and shadow mode against any timeframe" for AML transaction monitoring rules **[vendor claim]** — [Unit21 transaction monitoring](https://www.unit21.ai/products/transaction-monitoring); [Unit21 AML rules with examples](https://www.unit21.ai/blog/how-to-set-up-powerful-aml-transaction-monitoring-rules-with-examples)
- A competitor (Flagright) states that Unit21's backtest window and shadow mechanics are not publicly specified **[competitor marketing]** — [Flagright vs Unit21](https://www.flagright.com/compare/flagright-vs-unit21)
- Regulators expect testing before change: the UK FCA Financial Crime Guide (updated by PS24/17, 29 Nov 2024) lists as good practice controls "to measure the effectiveness of their automated system, thresholds and parameters, such as sample testing and tuning", and piloting or evaluation periods for new approaches — [FCA PS24/17](https://fca.org.uk/publication/policy/ps24-17.pdf); [Clifford Chance summary](https://www.cliffordchance.com/insights/resources/blogs/regulatory-investigations-financial-crime-insights/2024/12/fca-updates-financial-crime-guide.html). The UAE Central Bank rulebook describes pre-implementation testing by raising and lowering thresholds on historical data — [CBUAE rulebook 2.4](https://rulebook.centralbank.ae/node/959)

### Inferences
- For a portfolio project, a stream maps naturally onto these stages: **replay = backtest** (fast, as-fast-as-possible mode on validation days); **shadow = a second consumer group** on the same topic that writes to `decisions_shadow` and never to the queue; **champion/challenger** = both groups score every event, a comparison job reports agreement, alert overlap and (once labels arrive) precision@k per model. Kafka consumer groups make the shadow consumer free: it reads the same log independently.
- Uber's "regressions invisible in aggregate metrics" point supports reporting per-segment (currency, payment format, cold-account class) differences between champion and challenger, not just one PR-AUC.

### Gaps
- I found no recent primary engineering posts from Adyen, PayPal, Nubank, Revolut, Monzo, Feedzai or Featurespace on replay/shadow pipelines in this session's budget. Featurespace was acquired by Visa (announced 2024, background knowledge, not verified here).
- No public numbers on how long banks run AML models in parallel before switching off old rules.

---

## 5. The rules + ML + investigator hybrid architecture, and regulatory context

### Takeaway
Real AML/fraud stacks are layered: deterministic rules (thresholds, velocity, structuring, new-account, fan-in/fan-out) run next to an ML score. The outputs merge into alerts by policy (any-trigger, score bands, rule overrides), then go into a capacity-limited investigator queue whose decisions feed back as labels. Regulators do not ban ML. They expect rules/thresholds to be documented, tested (above/below-the-line), tuned and explainable, and they hold the firm responsible for understanding its models.

### Cited Findings
- Typical rule families: **structuring** (several transactions kept just below a reporting/review threshold) and **velocity** (count or volume in a time window, against a fixed threshold or the customer's own baseline). One global threshold often fails in both directions at once, so thresholds are segmented **[practitioner/vendor guide]** — [Sanction Scanner practitioner guide](https://www.sanctionscanner.com/blog/transaction-monitoring-rules-and-scenarios-a-practitioners-guide-to-effective-detection-logic-1371); [SAS, segmentation for TM thresholds](https://blogs.sas.com/content/datamanagement/2021/03/05/techniques-aml-transaction-monitor/) **[older: 2021]**
- **Above/below-the-line (ATL/BTL) testing**: BTL samples activity just under the threshold to see if suspicious cases are missed; ATL checks what raising the threshold would lose. Sample sizes come from available alerts and desired confidence — [Deloitte, optimizing rule-based TM](https://www2.deloitte.com/content/dam/Deloitte/de/Documents/finance/Deloitte-Optimizing-rule-based-transaction-monitoring-systems.pdf); [Deloitte CH blog](https://www.deloitte.com/ch/en/Industries/financial-services/blogs/calibration-of-rule-based-transaction-monitoring-vendor-systems.html)
- Tuning: adjust thresholds in a tuning environment, run an alert cycle, compare with red flags and filed SARs. Thresholds can be set from standard-deviation multiples of customer behaviour — [Protiviti, tuning TM scenarios](https://www.protiviti.com/SG-en/insights/tuning-suspicious-transaction-monitoring-scenarios-combining-aml-expertise-and-data)
- Stripe Radar combines ML scores with rules in real time. For example, newer rules combine "our machine learning models with the issuer's CVC and postal code response". Rules can reference the risk score — [Stripe blog, new Radar features](https://stripe.com/au/blog/new-radar-features); [Stripe docs, fraud prevention rules](https://docs.stripe.com/radar/rules)
- Dal Pozzolo et al.'s FDS diagram shows the layers: terminal/blocking rules → scoring rules → data-driven model → investigators → feedback. Investigators "can only check few alerts per day", which motivates precision@k with k = daily capacity **[older: 2018]** — [TNNLS PDF](https://boracchi.faculty.polimi.it/docs/2017_FraudsTNNLS.pdf)
- **UK FCA**: Financial Crime Guide updated in PS24/17 (Nov 2024) with transaction monitoring good/poor practice for manual and automated monitoring, a case study on HSBC's TM weaknesses, controls to measure effectiveness of thresholds/parameters, piloting new approaches, and recording reasons for decommissioning systems — [FCA PS24/17](https://fca.org.uk/publication/policy/ps24-17.pdf); [Penningtons summary](https://www.penningtonslaw.com/insights/fca-updates-its-financial-crime-guide/); [FCA FCTR 4 handbook](https://handbook.fca.org.uk/handbook/fctr4)
- **JMLSG (UK)**: automated monitoring rules and thresholds should be reviewed regularly and be relevant to the firm's business and customers **[older: 2021]** — [JMLSG Part I ch. 5.7 consultation](https://www.jmlsg.org.uk/wp-content/uploads/2021/09/Consultation-review_Part-I-Chapter-5.7_Board-approved_September-2021.pdf)
- **FATF (July 2021)**: ML in transaction monitoring can reduce false positives and find complex cases. Lack of explainability/transparency is named as a challenge. Supervisors should understand the models, and firms stay responsible for them **[older: 2021]** — [FATF report page](https://www.fatf-gafi.org/en/publications/Digitaltransformation/Opportunities-challenges-new-technologies-for-aml-cft.html); [FATF handout](https://www.fatf-gafi.org/content/dam/fatf-gafi/brochures/opportunities-and-challenges-of-new-technologies-handout.pdf); [Kroll summary](https://www.kroll.com/en/insights/publications/financial-compliance-regulation/fatf-new-technologies-aml-cft)
- **US**: independent testing of a monitoring programme (31 CFR 1020.210) covers scenario logic, data feeds and threshold rationale. Wolfsberg guidance prefers BTL testing over raw alert counts or alert-to-SAR ratios as effectiveness measures **[secondary summary: NHI guide, unverified against primary]** — [NHI AML programme guide](https://nhimg.org/aml-programme-and-transaction-monitoring-guide)

### Inferences
- **Typical combination policies** (to implement and document as an ADR):
  1. *Any-trigger*: alert if a rule fires OR score ≥ threshold. Each alert keeps a `reasons[]` list (rule ids + top SHAP features).
  2. *Score bands*: score < low → clear; low-high → queue (priority by score); ≥ high → priority queue / hold.
  3. *Rule overrides*: hard rules (sanctions hit, both accounts new per FINDING-014) always alert whatever the score. Allow-list rules can suppress.
  4. *Capacity*: the queue holds k slots per (simulated) day. When full, lowest-priority alerts age out or wait. This makes precision@k the operating metric, as in Dal Pozzolo.
- Simple, explainable rules that fit AMLworld: high velocity out of an account in N hours; fan-out (≥ m distinct receivers in window); fan-in (≥ m distinct senders); structuring (several amounts just below a round threshold in a window); new-account + large amount; round-trip (money returns to origin within a window, if cheap to compute online). Each rule must use only as-of state. They then share the leakage contract with the model.
- Rules in a portfolio are valuable for **comparison**: report rules-only, model-only and combined precision@k at the same k. Also report what each catches that the other misses. That honest, rules-as-baseline table is something reviewers trust.

### Gaps
- I did not fetch the Wolfsberg Group's own statement on effective monitoring; the claim above is second-hand.
- No primary source found on exact alert-queue capacity numbers at banks (alerts per investigator per day).

---

## 6. What a strong 2025-2026 Kafka fraud pipeline portfolio project looks like, and the shortcuts reviewers dismiss

### Takeaway
Most public "real-time fraud with Kafka" repos are demos: a producer, a consumer, a model, and a dashboard, often on the Kaggle credit-card or IEEE-CIS datasets. Few deal with replay determinism, idempotency, late events, delayed labels or as-of features. Those are exactly the things that separate a serious project.

### Cited Findings
- Reference/demo projects found: afedulov/Ververica-style Flink+Kafka fraud demo (Docker Compose) — [fraud-detection-demo README](https://github.com/pawel-jedruch-swiftpay/fraud-detection-demo/blob/master/README.md); Flink StateFun per-card fraud actor with exactly-once egress — [StateFun example](https://kzmlabs.github.io/flink-statefun/examples/fraud-detection/); AWS SageMaker Feature Store + MSK streaming aggregates **[older]** — [AWS ML blog](https://aws.amazon.com/blogs/machine-learning/use-streaming-ingestion-with-amazon-sagemaker-feature-store-and-amazon-msk-to-make-ml-backed-decisions-in-near-real-time); Confluent Flink on IEEE-CIS — [msg guide](https://www.msg.group/en/publications/real-time-fraud-detection-a-hands-on-guide-to-confluent-flink/); Apache Fluss fraud blog — [Fluss blog](https://fluss.apache.org/blog/fluss_fraud_detection/); Databricks structured-streaming fraud features — [Databricks community blog](https://community.databricks.com/t5/technical-blog/fraud-detection-feature-engineering-with-structured-streaming/ba-p/151308); Materialize real-time feature store — [Materialize](https://materialize.com/real-time-feature-store-with-materialize/)
- None of the search results combined Kafka, a feature store, deterministic replay and delayed labels in one repo (based on search snippets, not full audits)
- Railgun's point that hopping windows give wrong counts is a ready critique of demos that use tumbling/hopping windows for velocity features — [Railgun arXiv](https://arxiv.org/pdf/2009.00361)

### Inferences
Shortcuts that make reviewers dismiss a streaming fraud project (my synthesis, based on the sources above and the project's own contract):
1. **Random train/test split, then "streaming".** The model has seen the future. (Already prevented here by the frozen time split.)
2. **Features computed over the full dataset**, then looked up at stream time (final degree, global averages). That is point-in-time leakage.
3. **Using `datetime.now()` / processing time in features**, so results change with replay speed.
4. **Labels available instantly**: online learning or metrics that use the label at scoring time. Ignores verification latency.
5. **Kaggle `creditcard.csv` (PCA features, 2 days)**: no entities, so no graph, no velocity. Reviewers have seen it a thousand times.
6. **At-most-once or no dedupe**: auto-commit before processing, with no idempotent sink. A crash loses or doubles decisions.
7. **Hopping windows for velocity** and calling them exact.
8. **Accuracy/AUC as the headline** at a 0.1% base rate, with no precision@k at an investigator capacity.
9. **No rules baseline**: claiming ML value without showing what simple rules already catch.
10. **Unbounded consumer**: no lag metric, no latency SLO measured end to end, no backpressure test.
11. **Single happy-path run**: no restart/duplicate/late-event tests, and no proof that replays are deterministic.

What a strong version shows (checklist): deterministic replay with seq tie-break, with a decision-parity test across pacing modes; seeded fault injection with a fault log, plus a "parity under chaos" test; idempotent Postgres sink keyed by `txn_id`; DLQ for malformed records; schema registry with a compatibility test; as-of feature reads; a separate label topic with `label_known_at` and investigator capacity; shadow consumer group for challenger models; rules-only vs model-only vs combined precision@k; lag/latency dashboards; and an honest note that the data is synthetic and covers 18 days only.

### Gaps
- I did not audit individual GitHub repos in depth (stars, tests, recency). The list above is a pointer set, not a ranking.
- I found no blog post or talk that lists "why reviewers reject streaming fraud portfolios". The shortcut list is synthesis, not a cited survey.
