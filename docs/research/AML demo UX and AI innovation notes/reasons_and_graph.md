# Alert reasons and money-flow graphs for AML investigators: what real tools and the research say (as of 23 Nov 2026)

Scope: concrete guidance for GraphGuard-AI's Case page and the queue's "why flagged" column. This builds on, and tries not to repeat, `docs/research/AML investigator interface research 2026 notes/explanations_and_agents.md` (SHAP mechanics, CFPB four-factor rule, Wolfsberg mapping inventory, LLM agents) and `ring_visualization.md` (libraries, layered layout, hub cap, Feedzai decluttering paper). About 18 search/fetch calls, 2026-11-23. Vendor claims are marked **[VENDOR]**, and anything not sourced is under Inferences. Problems found in testing that this work addresses: (a) "Sent on a Wednesday" is the top reason on many alerts (a true SHAP value from a simulator artifact, FINDING-018); (b) self-payments "Corporation #X → Corporation #X" appear with no explanation; (c) a newcomer did not understand the graph's roles (sender, receiver, alert edge, upstream/downstream, "+4 more payees").

Local facts used below (from `docs/findings.md`, not from the web): 18.0% of normal training traffic is an account paying itself ("Reinvestment" format), against 0.2% of laundering rows. Reinvestment has 481,056 rows and **0** laundering (FINDING-005/006). Weekday is among the top-3 SHAP reasons for 77.9% of the queue, and dropping it costs nothing (PR-AUC 0.28253 vs 0.28155, FINDING-018).

---

## 1. Reason codes in production: how vendors turn model contributions into reasons

### Takeaway
The one vendor with public docs (Google Cloud AML AI) does not show single features. It groups features into named **"feature families"** written as behaviours ("Unusual rapid movement of funds"), gives each family one signed attribution, explains only high-risk parties, and tells investigators to start with the biggest positive families and mostly ignore negative ones. Other vendors (Featurespace, Hawk, Lucinity, Actimize, Feedzai) advertise "human-readable reason codes" but publish no format details. The common pattern is therefore: group features into human concepts, rank them by signed contribution, show a handful, and describe each one as a behaviour, not as a variable name.

### Cited Findings
- **Google AML AI, feature families.** Explanations give "an attribution score per feature family". A feature family is a grouping of related features "meant to be understood by investigators and audit teams". The examples given are "Unusual card debit activity", "Unusual rapid movement of funds" and "Unusual wire debit activity". Families are cut by transaction type (wire, cash, check, card, other) and direction (debit = outgoing, credit = incoming). — [Google Cloud: Understand prediction outputs](https://docs.cloud.google.com/financial-services/anti-money-laundering/docs/understand-prediction-outputs)
- **Google AML AI, sign and reading guidance.** Positive values raise risk ("A high positive value indicates strong contribution to increasing risk score") and negative values lower it. "Feature families with the highest positive attribution value are likely to be the most relevant" to the investigation. Smaller positive values can still be worth a look. Negative ones are unlikely to need inspection. The page gives no scale, no range, and does not say whether the values sum to the score (its examples are 0.4, 0.8, -0.2). — [same page](https://docs.cloud.google.com/financial-services/anti-money-laundering/docs/understand-prediction-outputs)
- **Google AML AI, who gets explained.** Explainability covers the highest-risk parties, including everyone you would investigate, and "may not be included for lower risk customers". — [same page](https://docs.cloud.google.com/financial-services/anti-money-laundering/docs/understand-prediction-outputs)
- **Google AML AI, score wording.** Scores run from 0 to 1 and "shouldn't be interpreted directly as a probability of money laundering activity". — [Google Cloud: AML AI overview](https://cloud.google.com/financial-services/anti-money-laundering/docs/concepts/overview) (as summarised by search; same wording on the prediction-outputs page)
- **Google AML AI, governance.** Model architecture, feature-family explainability and typology-coverage documents are available on request to customers. The product targets core typologies including structuring, money mule networks, and high-risk jurisdictions/cross-border activity. — [Google Cloud AML AI overview](https://cloud.google.com/financial-services/anti-money-laundering/docs/concepts/overview); [risk governance artifacts](https://docs.cloud.google.com/financial-services/anti-money-laundering/docs/collect-model-risk-governance-artifacts?authuser=9)
- **Hawk.** Press coverage says Hawk's patent-pending technology shows the "expected range" of normal behaviour and scores each risk factor "using natural human language", going beyond tools that only list contributing factors **[VENDOR, via TechCrunch 2023]**. — [TechCrunch, 26 Jan 2023](https://techcrunch.com/2023/01/26/hawk-ai-an-anti-money-laundering-and-fraud-prevention-platform-for-banks-raises-16m). Hawk's 2026 Investigative Agent advertises "chain of thought visualisation, confidence scores, citations and detailed action logs" **[VENDOR]**. — [fintech.global, 25 Mar 2026](https://fintech.global/2026/03/25/hawks-ai-agent-automates-aml-investigations/)
- **Featurespace (Visa since Sept 2024).** ARIC Risk Hub is described as giving real-time risk scores and alerts "with understandable reason codes". How the codes are built is not public **[VENDOR, third-party listing]**. — [about-fraud.com: Featurespace](https://www.about-fraud.com/providers/featurespace/)
- **General industry practice (not AML-vendor specific).** An alert typically carries a score, a risk band and a reason-code summary, and reason codes let a second-line reviewer check whether the evidence supports the codes applied. — [Elliptic corpus: risk score explainability and reason codes](https://www.elliptic.co/corpus/gen-3102/risk-score/risk-score-explainability-and-reason-codes-for-wallet-screening-decisions.html) (vendor knowledge page, low weight)
- **Feedzai's own research UI** (the Jesus et al. 2021 study, Section 2) converted SHAP into the **top 6** feature–contribution pairs sorted by absolute value. Each feature name was mapped to a natural-language description, values were made readable ("converting time from seconds to days"), and pairs were coloured **red for pushes toward fraud and green for pushes toward legitimate**. So "what lowers the score" was shown inline, not hidden. — [Jesus et al., FAccT 2021, arXiv 2101.08758](https://arxiv.org/abs/2101.08758)

### Inferences
- **Suppressing artifact features is not documented anywhere I could find.** No vendor page talks about hiding a feature from explanations while keeping it in the model. Real vendors avoid the problem by grouping features into families that carry business meaning (Google). A "weekday" family would never exist in a real bank's taxonomy. The honest options for GraphGuard, best first:
  1. **Remove the feature from the model** (FINDING-018 shows it costs nothing; this is already the planned Phase 8 challenger). Explanation and model then agree, with nothing hidden.
  2. Until then, **demote and label it, never drop it silently**. Show it below the line as "Calendar effect of the simulator (not a reason to investigate)". Exclude it from the top-3 "why flagged" text in the queue, and on the Case page say how much of the score it carries. Hiding it entirely would make the displayed reasons not add up to the score. A senior reviewer would call that dishonest, and it breaks the "explanation = model" contract.
  3. Do not re-normalise the remaining reasons as if the artifact were absent. That would overstate the real reasons.
- **Families for GraphGuard, by analogy with Google.** Sum SHAP within a family (valid because SHAP is additive): "Money passed on quickly" (time since the account last received, sends in 24 h), "New or rare relationship" (first payment to this receiver, distinct counterparties so far), "Unusual amount for this account", "Payment channel" (format, which is partly a simulator artifact, FINDING-006: label it as such), "Account is new" (cold policy), "Calendar (simulator artifact)". Write each one as a behaviour with the actual value: "Sent 4,818 EUR **12 minutes after** receiving 5,000 EUR". Do not write "time_since_last_in = 0.2 h".
- **Show 3 in the queue and up to 6 on the Case page** (Feedzai used 6; the CFPB credit analogy is 4). Show "what lowers the score" on the Case page only, in a separate group ("Points against"). Google tells investigators negatives rarely need inspection, so they should not compete with the main reasons for attention.
- **Score wording:** follow Google and ADR 0008. Say "rank" or "risk score", not "chance of laundering".

### Gaps
- No public documentation of the reason-code templates, top-N counts, or grouping for Actimize, Feedzai's AML product, Featurespace, Lucinity or Hawk was found. All of it is marketing-level.
- Google does not list its feature families or say how many exist (the full list goes to customers on request).
- No source on suppressing non-actionable or artifact features in production explanations was found. Recommendation 2 above is reasoning, not documented practice.

---

## 2. Do SHAP explanations help domain users? Risks and best formats

### Takeaway
The best application-grounded evidence, from Feedzai with real fraud analysts, is **negative or null**. Showing the model score made analysts faster but less accurate. Adding SHAP, LIME or TreeInterpreter explanations recovered part of that accuracy, but no explainer beat "data only". A larger AAAI 2024 follow-up found no added value from explanations over the score alone. The format evidence favours **plain text over charts** for lay users, but most of it measures preference, not correctness. For GraphGuard, explanations are better framed as **"where to look first"** than as proof. The investigator should still be led to the raw evidence (the transactions and the ring).

### Cited Findings
- **Jesus et al. 2021 (FAccT, Feedzai), "How can I choose an explainer?"** 3 professional fraud analysts, a real e-commerce fraud model, balanced samples (random = 50%). Conditions: Data Only (n=200), Data + Score (200), and Data + Score + LIME / TreeInterpreter / SHAP (300 each). Results (accuracy / recall / FPR / mean decision time / Fleiss' kappa):
  - Data Only: 62.00% / 35.87% / 15.74% / 59.5 s / 0.41
  - + Score: 51.02%★ / 25.00% / 19.57% / 44.61 s★ / −0.02
  - + LIME: 58.59% / 27.03% / 10.07% / 50.29 s★ / 0.53
  - + TreeInterpreter: 56.52% / 25.55% / 12.67% / 43.03 s★ / 0.30
  - + SHAP: 59.73% / 31.08% / 12.00% / 45.72 s★ / 0.15
  (★ = significant vs Data Only.) The authors' conclusion: the popular explainers "have a worse impact than desired". Data Only gave the highest accuracy and the slowest decisions. All explainers improved accuracy over Score-only but stayed below Data Only. Showing the score cut decision time by about 25%, and analyst agreement collapsed with the score alone (76.67% vs 63.33% raw agreement). Explanations were the top-6 feature–contribution pairs in plain language, coloured red/green. — [arXiv 2101.08758](https://arxiv.org/abs/2101.08758) (numbers read from the PDF's Table 1; small sample, 3 analysts)
- **Amarasinghe et al. (AAAI 2024; arXiv 2206.13503), "On the Importance of Application-Grounded Experimental Design…"** Re-ran the Feedzai study with professional fraud analysts on real e-commerce transactions, a better design, and a cost-based metric (Percent Dollar Regret). They found **no evidence that the tested explanations (LIME, TreeSHAP, TreeInterpreter) add value** over showing the model score alone. They argue that small design choices (proxy users, simplified metrics) can produce misleading conclusions about explainers. — [arXiv 2206.13503](https://arxiv.org/abs/2206.13503v4); [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/30082) (seen via abstract/excerpts; exact numbers not checked)
- **Weerts et al. 2019, "A Human-Grounded Evaluation of SHAP for Alert Processing"** (domain experts judging alerts): "possibly SHAP explanations alone are not that useful for alert processing". — [arXiv 1907.03324](https://arxiv.org/pdf/1907.03324)
- **Over-trust:** a financial-XAI review warns that feature-relevance visuals such as SHAP "tend to be absorbed at face value", which can stop experts from questioning them. — [arXiv 2309.11960, A Comprehensive Review on Financial Explainable AI](https://arxiv.org/pdf/2309.11960) (review, not a user study)
- **Over-reliance depends on the user:** a confirmatory analysis of two controlled studies (loan approval, candidate screening) found local feature-based explanations reduced over-reliance for low need-for-cognition participants but had the **opposite** effect for high need-for-cognition participants. — [Springer chapter, 2025](https://link.springer.com/chapter/10.1007/978-3-032-08317-3_15) (seen via snippet only)
- **Expertise:** Naqvi, Balaji, Laju, Kaur, "From Curiosity to Caution: How Expertise Shapes the Use of Interpretable Machine Learning", FAccT 2026. 23 data scientists (not investigators): novices were driven by curiosity, which risked over-reliance, while experts were driven by efficiency and caution. — [FAccT 2026 PDF](https://harmanpk.github.io/Papers/FAccT2026_Expertise-ML.pdf) (participants are data scientists, so it only loosely transfers to AML users)
- **Format, text vs chart:** a 2024 healthcare study (QCancer) separated explanation *content* (SHAP vs occlusion) from *format* (chart vs text). The apparent advantage of one method was largely a preference for **text over charts**. Controlling for format, the content difference mostly disappeared. — [arXiv 2408.17401](https://arxiv.org/html/2408.17401v4)
- **Narratives:** XAIstories (2023): over 90% of a general audience found LLM narratives of SHAP convincing. — [arXiv 2309.17057](https://arxiv.org/pdf/2309.17057v2). Ichmoukhamedov et al. (2024) note that user surveys on narratives measure **preference, not faithfulness**, and propose faithfulness metrics. — [arXiv 2412.10220](https://arxiv.org/html/2412.10220v1)
- **AML money-mule deployment report (arXiv 2607.17586, 2026):** analysts found raw SHAP waterfall plots time-consuming to read, and narratives made risk factors easier to act on. This is a deployment report, not a controlled study. — [arXiv 2607.17586](https://arxiv.org/pdf/2607.17586)

### Inferences
- The Feedzai pattern (score makes people faster and worse; explanations partly repair it) is a reason to **lead with evidence, not the score**. On the Case page, the transactions and the ring picture should be the primary content. Reasons should be signposts ("check: money passed on within 12 minutes → see payments 2 and 3 in the ring"). Each reason should link to the rows it is about, which makes it checkable rather than taken on faith.
- **Format:** short plain sentences carry the reason. A small signed bar per sentence is fine as a secondary cue. Avoid waterfall/force plots for investigators (keep them in a "for model reviewers" drawer).
- **Over-trust guard for the S7.11 test:** include a few low-ranked or clean alerts, and check whether the tester's verdict follows the reason text even when the evidence disagrees. This mirrors the Feedzai design (Data Only vs + Score vs + Explanations) at toy scale and would be an honest, citable mini-result.
- An artifact reason at the top (weekday) is exactly the kind of thing that gets "absorbed at face value" or, as in testing, destroys trust in all the reasons. Fixing it is not cosmetic.

### Gaps
- No 2023–2026 controlled user study with **AML** investigators (as opposed to e-commerce fraud analysts) on SHAP/reason formats was found.
- No study comparing grouped "reason families" with raw feature lists for analysts was found.

---

## 3. Typology labels: naming patterns in plain words

### Takeaway
AMLworld's generator uses eight named patterns: fan-out, fan-in, gather-scatter, scatter-gather, simple cycle, random, bipartite and stack. These are graph-shape names, not regulator vocabulary. Regulators (FinCEN, FATF via secondary sources) describe **behaviours** instead: funds arrive and leave quickly, many senders feed one account (funnel or consolidation), outflows are split into smaller amounts, and multiple mule hops are used. They stress that a red flag is not proof. The UI should pair each shape name with a one-sentence behaviour description and a "this is a pattern, not proof" note.

### Cited Findings
- **AMLworld patterns:** fan-out, fan-in, gather-scatter, scatter-gather, simple cycle, random, bipartite, stack. — [Altman et al. 2023, arXiv 2306.16424](https://arxiv.org/pdf/2306.16424). Definitions from a paper that generates these shapes: fan-out/fan-in = one central node linked to ≥2 distinct nodes outward/inward; gather-scatter = fan-in then fan-out through one vertex; scatter-gather = fan-out then fan-in through the **same intermediate** vertices; simple cycle = closed path that revisits no vertex; stack adds a bipartite layer. — [arXiv 2506.13989](https://arxiv.org/pdf/2506.13989v2) (as summarised by search)
- **Shapes alone are not suspicious:** fan-in and fan-out appear in both normal and alert categories in simulated AML data, "emphasizing how criminals often mimic legitimate activity". — [arXiv 2506.13989](https://arxiv.org/pdf/2506.13989v1)
- **FinCEN funnel accounts (FIN-2014-A005):** "an individual or business account in one geographic area that receives multiple cash deposits" made elsewhere. Several funnel accounts may "transfer funds into a single consolidated account from where the funds are subsequently withdrawn". FinCEN gives no bright-line tests and treats red flags "as guidelines rather than rules". — [FinCEN Advisory FIN-2014-A005](https://www.fincen.gov/resources/advisories/fincen-advisory-fin-2014-a005)
- **"Rapid movement of funds"** is a FinCEN red-flag heading ("Funnel account activity and rapid movement of funds"), and FinCEN advisories state that "the mere presence of a red flag is not by itself evidence of criminal activity". — [FinCEN advisories via search](https://www.fincen.gov/resources/advisories/fincen-advisory-fin-2014-a008) (sub-indicators not retrieved)
- **Mule behaviour in plain words** (secondary, vendor pages attributing it to FATF): funds leave within minutes or hours of arriving, the balance returns near zero, outflows are split into smaller amounts. Topologically, many-to-one (aggregation) and one-to-many (distribution) form hub-and-spoke shapes. — [Elliptic: money mule networks](https://www.elliptic.co/corpus/gen-3231/consumer-fraud/money-mule-networks.html); [Elliptic: detecting mule networks](https://www.elliptic.co/mule-networks.html) **[VENDOR]**
- **UK FCA multi-firm review:** fraud proceeds were usually cashed out after moving through **2 to 5 mule accounts**, by which point funds were often split into smaller payments. — [FCA: Money mules, mule activity and cashing out findings](https://www.fca.org.uk/publications/multi-firm-reviews/money-mules-activity-cashing-out-findings)
- **Google AML AI's typology vocabulary:** "structuring", "money mule networks", "high-risk jurisdictions and cross-border activity", and the family name "Unusual rapid movement of funds". — [Google Cloud AML AI overview](https://cloud.google.com/financial-services/anti-money-laundering/docs/concepts/overview)

### Inferences
- A suggested label table for GraphGuard (wording is mine, grounded in the sources above):
  - **Fan-out ("split and send"):** one account sends to many accounts in a short time.
  - **Fan-in ("collect"):** many accounts send to one account (FinCEN's "consolidated account").
  - **Gather-scatter ("collect, then split"):** one account collects from many, then pays out to many.
  - **Scatter-gather ("split, then re-collect"):** money is split across middle accounts and comes back together at one account.
  - **Cycle ("round trip"):** money passes through a chain and returns to where it started.
  - **Bipartite ("group to group"):** a set of senders pays a set of receivers.
  - **Stack ("layers"):** two or more layers of group-to-group payments.
  - **Random ("chain with no clear shape"):** money hops along a chain without a neat pattern.
- Always add: "Synthetic data. These shapes come from IBM's simulator. A shape is a reason to look, not proof." This matches FinCEN's "not by itself evidence" wording and ADR 0008.
- Avoid "smurfing/structuring" for AMLworld rings. Structuring means splitting cash to stay under reporting thresholds, and AMLworld does not model thresholds. Using the word would overclaim.
- Prefer behaviour words in the queue column ("money passed on within minutes", "collects from many new senders"), and keep shape names for the Case page's ring panel, where the picture makes them concrete.

### Gaps
- FATF's primary typology wording was not retrieved (only secondary attributions). The FFIEC BSA/AML manual's red-flag appendix returned HTTP 403.
- No vendor documentation was found on how products name typologies inside the case UI.

---

## 4. Graph and link-analysis UX: roles, legends, time order, amounts, collapsed nodes

### Takeaway
Public material on Quantexa, Linkurious, i2, Neo4j Bloom and Hawk describes **what** their graphs show (the entities around an alert, the flow of money, events over time) far more than **how** they encode roles. The concrete, citable conventions are: show the alert in its surrounding context; i2 link labels carry the transaction **count and summed value** per direction; i2 puts transactions on a **timeline** using their date/time; i2 lets the analyst build a **sequence of chart items to step through** for presentation; flag accounts where large amounts pass through without staying; keep individual payments distinguishable under any aggregated edge. Explicit role legends and numbered steps are not documented anywhere I found. They are design choices GraphGuard has to make and test.

### Cited Findings
- **Linkurious:** opening an alert shows "not just the transaction but also the other elements that are surrounding it". Analysts use the graph view to judge a case's risk, and Ria's case study says investigators see "the full scope of the network around a suspicious activity" **[VENDOR]**. — [Linkurious blog: reinforcing AML with graph](https://linkurious.com/blog/reinforcing-aml-graph-technologies/); [Ria case study](https://linkurious.com/blog/ria-money-transfer-investigation-time/)
- **i2 Analyst's Notebook:** charts show "the flow of data such as telephone calls and financial transactions, and how related events unfold over time". — [i2 ANB 9.4.1 docs: Charts](https://docs.i2group.com/anb/9.4.1/charts.html). Transactions can be placed on a timeline by setting the link's date/time as "Controlling". — [IBM Support](https://www.ibm.com/support/pages/how-can-i-do-datetime-analysis-analysts-notebook-data-information-store). IBM also documents labelling a link with the **number of transactions in each direction and the summed currency value**. — [IBM Support node/716175](https://www.ibm.com/support/pages/node/716175) (only the first step was visible)
- **i2 "Most Connected Items"** can flag accounts "where large amounts pass through without staying", which "may indicate money laundering". — [IBM Support: Most Connected Items](https://www.ibm.com/support/pages/ibm-i2-analysts-notebook-refining-list-most-connected-items-functionality)
- **i2 sequences:** users can build "a sequence of chart items to step through to present data effectively". — [ANB 9.4.1 user help (Scribd copy)](https://www.scribd.com/document/619871490/i2-Analyst-s-Notebook-9-4-1) (secondary copy of official help)
- **Keep payments distinguishable:** "Multiple payments between the same accounts should remain distinguishable. An aggregated edge can summarize a period for analysis, but investigators still need its underlying transactions." Model it as accounts linked by transfer edges, with parties linked to accounts by holder edges. — [PuppyGraph: network analysis in AML](https://www.puppygraph.com/blog/network-analysis-in-aml) **[VENDOR]**
- **Quantexa:** the emphasis is entity resolution, so that "each graph node represents a real entity rather than a duplicate or fragment". A plain database query shows account-to-account transfers, but without entity resolution "the broader mule network remains hidden" **[VENDOR]**. — [Quantexa: in the fight against fraud not all graphs are created equal](https://www.quantexa.com/blog/in-the-fight-against-fraud-not-all-graphs-are-created-equal/)
- Linkurious's entity model (people/companies control accounts; money flows between accounts) and the Feedzai sequential-graph decluttering study are covered in `ring_visualization.md` and not repeated here.

### Inferences (design guidance for the Case page graph; to be tested in S7.11)
- **Say what the picture is, in one sentence, above it:** "How the money moved in the 72 hours before this alert. Each arrow is one payment; arrows are numbered in time order."
- **Number the edges by time** (1, 2, 3…) and list the same numbers in a table beside the graph (time, from, to, amount). This is a static version of i2's "sequence to step through", and it gives screen-reader users the same information. Add a "Play" or "Next step" button that highlights one payment at a time with a sentence: "Step 3: Corporation #12 sent 4,800 EUR to Corporation #40, 12 minutes after receiving 5,000 EUR in step 2."
- **Name roles in words, not only colours.** Use node badges such as **"Sender (this alert)"** and **"Receiver (this alert)"**, give the alert edge a thick outline with a label "**This payment was flagged**", and place a small always-visible legend under the graph. Replace "upstream/downstream" with "**Paid the sender earlier**" and "**Was paid by the receiver later**". Note that later means "later but before the alert" per the as-of rule: nothing at or after the alert is shown. Then say so in the legend: "Only payments before the flagged one are shown".
- **Collapsed nodes:** "+4 more payees" was not understood. Spell it out: "**4 other accounts the sender paid (12,300 EUR in total), hidden to keep the picture readable. Click to show.**" This keeps the i2 count-plus-total convention.
- **Amounts on edges:** show the amount and currency per payment, never a cross-currency sum (ADR 0008). Where several payments go between the same pair, show "3 payments" on the edge and list them on click (the PuppyGraph principle).
- **Pass-through cue:** for middle accounts, a small note "received 5,000 EUR, sent on 4,800 EUR within 12 min". This is the i2 "passes through without staying" idea and the core mule behaviour from Section 3.
- **Typology sentence under the picture**, using the plain-word labels from Section 3, plus "pattern, not proof".

### Gaps
- No public screenshots or docs describe Quantexa's, Hawk's or Neo4j Bloom's node/edge role styling, legends or step numbering in 2024–2026.
- No user study was found on numbered edges vs timelines vs animation for money-flow comprehension by novices.
- i2's exact link-label procedure was only partly visible.

---

## 5. Self-transfers and same-entity payments

### Takeaway
In real monitoring, money moving between a customer's **own accounts** is ordinary and very common (sweeps, treasury moves), but it is not automatically safe: the same customer as sender and overseas beneficiary is a listed red flag, and entity resolution exists precisely to know when two accounts belong to the same party. I found no public vendor documentation on whether products suppress, group or specially label own-account transfers. In AMLworld, self-payments are a generator artifact: 18% of normal traffic, almost never laundering, and "Reinvestment" has zero laundering rows. They must be **explained** on screen, not left looking like a typo.

### Cited Findings
- **Red-flag side:** a PwC transaction-monitoring case study lists as an indicator that the ordering customer was also the overseas beneficiary. A blanket exclusion of own-account transfers could therefore hide real typologies. — [PwC, Towards Better Transaction Monitoring (2019)](https://www.pwc.com/sg/en/consulting/assets/transaction-monitoring-2019.pdf) (as summarised by search)
- **Multi-account customers:** when a customer's several accounts each generate cases, consolidating them into one customer view is a burden unless the system handles it. — [SAS: What is transaction monitoring in AML?](https://www.sas.com/en_gb/insights/articles/risk-fraud/what-is-transaction-monitoring-in-aml.html)
- **Entity resolution:** Quantexa resolves records so each node is a real entity, so account-to-account links can be read at the party level **[VENDOR]**. — [Quantexa blog](https://www.quantexa.com/blog/in-the-fight-against-fraud-not-all-graphs-are-created-equal/). Launderers vary names and registration data to fragment identity. — [TigerGraph: AML graph analytics](https://www.tigergraph.com/blog/aml-graph-analytics-money-laundering/) **[VENDOR]**
- **Graph model:** parties hold accounts (holder edges) and accounts pay accounts (transfer edges). — [PuppyGraph](https://www.puppygraph.com/blog/network-analysis-in-aml) **[VENDOR]**
- **AMLworld (local, not web):** is_self_transfer is 18.0% of normal vs 0.2% of laundering. The Reinvestment format has 481,056 rows and 0 laundering. The generator appears never to emit a self-transfer as a laundering hop. — `docs/findings.md` FINDING-005/006
- **AMLworld entity structure:** "Corporation #X → Corporation #X" in GraphGuard is the same named entity on both sides. Whether this means the *same account* or two accounts of one owner depends on how the demo builds names. This was not checked in this research. (The S7.10 agent run quoted one such row as "a transfer to its own account in the same minute, 4,818.11 EUR".)

### Inferences
- **Label every self-payment explicitly** in tables and graph: an "Own account" chip and the sentence "**Moved money between its own accounts** (in this simulator, 18% of ordinary payments look like this; almost none are laundering)". In the graph, draw it as a small loop on the node with a tooltip, not as an edge to a duplicate node.
- If the entity owns several accounts, say so ("Corporation #27852 has 3 accounts at 2 banks"). Use "own accounts" only when the bank+account pair differs. If it is literally the same account, say "booked to the same account (a 'Reinvestment' entry)".
- **Do not hide self-payments from the ring view**, because they are part of the account's history and their absence would be noticed. Do de-emphasise them (grey), and never count them as "payees" in "+N more payees".
- On the reasons side: if "not a self-transfer" contributes to the score, it is an artifact reason like weekday (the model learned the simulator's free negative-class exclusion). Label it the same way ("simulator effect"), or put it in the artifact family.
- In the Phase 8 write-up, say that in real data own-account transfers would be resolved at the party level (Quantexa-style) and judged by context (cross-border same-owner = red flag; domestic sweep = normal).

### Gaps
- No vendor documentation on suppressing, grouping or labelling own-account transfers in alerts or graphs was found. No regulator guidance on excluding them was found either.
- It was not checked whether GraphGuard's demo "Corporation #X → Corporation #X" rows are the same account or different accounts of one entity. A quick query on `demo.transactions` (from_bank/from_account vs to_bank/to_account) settles it.
