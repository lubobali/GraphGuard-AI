# How commercial AML transaction-monitoring and case-management tools present alerts to investigators (as of Nov 2026)

Method note: 17 tool calls (searches plus fetches of vendor pages). Most of what is publicly available is **vendor marketing**. Hawk's own pages returned 403 and Unit21's detailed docs sit behind a login, so a few products are described through secondary listings. Every efficiency number below is **self-reported by the vendor unless marked [INDEPENDENT]**. Few vendor pages carry a date. Where one does, the date is given.

## 1. The alert queue: sorting, risk score, grouping, SLA timers

### Takeaway
Across vendors the queue is the same: alerts or cases grouped into **queues owned by teams**, with **due date or SLA as the main sort key** (ahead of score), a numeric score or High/Medium/Low priority, owner, status, and overdue items shown in red. Newer vendors set SLA timers by risk level and auto-assign cases. Many products roll alerts up to a **customer or entity case** instead of working each transaction on its own.

### Cited Findings
- **Oracle FCCM / ECM (most concrete public docs):** the case list shows Owner, Created, Due Date and Score. Overdue due dates are **shown in red**, and the firm configures what counts as "nearly due". — [Oracle ECM 8.1.2.10 Viewing Case List](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/enterprise-case-management/8.1.2.10.0/ecgug/viewing-case-list.html)
- Oracle ECM 8.1.2.11 adds a **Priority** column. Advanced search filters by priority High/Medium/Low and by **Case Score**. The default sort is **Due Date, then Priority, then Case ID**. — [Oracle ECM 8.1.2.11 Viewing Case List](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/enterprise-case-management/8.1.2.11.0/ecgug/viewing-case-list.html); [Oracle ECM Using Search Criteria](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/enterprise-case-management-application-pack/8.1.2.10.0/ecgug/using-search-criteria.html)
- Oracle Behavior Detection (the alert-generation layer) sorts its alert list by default on **Due Date ascending, then Create Date descending, then Alert ID**. Its columns include score, status and due date/time. — [Oracle BD Alert List Display Configuration](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/behavior-detection/8.1.2.9.0/bduge/alert-list-display-configuration.html); [Oracle BD Alert List Matrix](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/behavior-detection/8.1.2.10.0/bduge/alert-list-matrix.html)
- Oracle Customer Screening lets users add optional alert-list columns: Alert ID, Created Date, Primary Name, Status, Priority, Due date, Match Score and Risk Score. — [Oracle CS Field Descriptions for Alert List](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/customer-screening/8.1.2.10.0/csoug/field-descriptions-alert-list.html)
- **Unit21:** alerts are triaged **through queues**, and only the team assigned to a queue can see and investigate its alerts. Alerts are OPEN or CLOSED, and a closed alert can be reopened. — [Unit21 docs: Alerts](https://docs.unit21.ai/docs/alerts)
- Unit21: a case belongs to exactly **one queue**, and queues can set **automatic deadlines**. Order of precedence: a manually set due date, then the queue deadline, then a global deadline. — [Unit21 docs: Case Queues](https://docs.unit21.ai/docs/case-queues); [Unit21: queue-based deadlines](https://docs.unit21.ai/docs/how-to-create-queue-based-deadlines)
- Unit21's platform SLA treats it as a P1 incident when alert or case pages take more than 45 s to load. Investigators live in these pages, so load time is a contractual matter. — [Unit21 Support & SLA](https://docs.unit21.ai/page/support-service-level-agreement)
- **Flagright:** SLA timers are configurable **by case type, jurisdiction or risk level**, and overdue investigations are flagged before they breach. Live customer-risk (CRA) scores are embedded in the investigation. — [Flagright Case Management](https://www.flagright.com/case-management)
- **Lucinity:** configurable team and personal "workboards", a "Smart Case Allocator" that distributes work, and bulk claim/close/assign/**merge**. — [Lucinity Case Manager](https://lucinity.com/case-management)
- **NICE Actimize ActOne:** risk scores are shown in the investigation interface with a visual rating per subject party. Separately, X-Sight Entity Risk produces "a single entity trust score" (launched 2022). — [ActOne overview](https://niceactimize.com/enterprise-risk-case-management/enterprise-risk-case-management-overview); [Finextra 2022, X-Sight Entity Risk](https://finextra.com/pressarticle/91967/nice-actimize-promises-single-risk-score-with-x-sight-entity-risk)
- ActOne triage: high-risk alerts are escalated quickly, and low-risk alerts can be **held until recurring patterns appear**, which amounts to hibernating them. — [ActOne brochure (PDF)](https://www.niceactimize.com/Lists/Brochures/actone_modernize_your_financial_crime_investigations_brochure.pdf)
- **SymphonyAI NetReveal:** "Intelligent Event Triage" scores and prioritizes alerts automatically with continuously learning AI. — [NetReveal TM data sheet](https://symphonyai.com/resources/data-sheet/financial-services/netreveal-transaction-monitoring)
- **Feedzai** (secondary review): an ML model prioritizes alerts based on past alert, case and SAR outcomes. — [Sphinx: best TM software 2026](https://sphinxhq.com/blog-posts/best-transaction-monitoring-software-2026)
- **Tiered conversion** (vendor blog): high-priority tiers convert to SARs at 15-40%, low tiers at 2-8%. This is the case for ranking the queue. — [FluxForce: alert prioritization](https://www.fluxforce.ai/controls/alert-prioritization)

### Inferences
- In incumbent products the **regulatory clock (due date) sorts first and the score second**. A queue sorted purely by model score would look odd to a practitioner. A credible queue sorts by due date or SLA state and shows the score, or offers "score within SLA bucket".
- Moving from per-transaction alerts to **per-customer or per-entity cases** (alerts merged, Actimize's entity score, Quantexa's entity-centric view) is the norm. For GraphGuard that means grouping scored transactions by account, and by ring where one is detected.

### Gaps
- No public screenshots or column lists for Hawk, Sardine, Napier, ComplyAdvantage or Feedzai queues. Hawk's pages returned 403, and Unit21's detailed "Managing an Alert" page redirects to a login.

## 2. Network, entity-resolution and ring views (Quantexa especially)

### Takeaway
Network views are entity-centric. You start from a resolved entity, expand hop by hop through shared attributes and transactions, and let the scoring panel highlight risky nodes. Quantexa's own material admits the full graph confuses non-specialists and can be swapped for a simplified view. Newer vendors (Flagright, Hawk) present it as "multi-hop graph + flow of funds".

### Cited Findings
- **Quantexa:** an investigator usually starts from the entity in question and expands through the graph along related documents and entities. Users ask on the community forum how many hops to expand before stopping. The UI elements named are "Multi-Panel UI, Contextual Search, Scoring Panel, Entity Lab". — [Quantexa Community: investigators tag](https://community.quantexa.com/tag/investigators)
- Quantexa detection relies on a **typology-based scorecard** that combines entity resolution, network generation and anomaly detection. The scorecards are "expert-driven". Quantexa Assess lets scores act as rules, triggers or ML features. — [Quantexa: holistic view of financial crime](https://www.quantexa.com/resources/holistic-view-of-financial-crime/)
- In a Quantexa sanctions case study, seeds were linked to the entity of interest by **up to 16 hops**. — [Quantexa blog: Hidden in plain sight](https://www.quantexa.com/blog/hidden-in-plain-sight/)
- Quantexa FAQ: the network view "does not need to be presented to business users" and can be replaced by a simplified view inside existing systems. Its internal-fraud FAQ lists "the network UI is too confusing for business users" as a known objection. — [Quantexa FAQs](https://www.quantexa.com/faqs/); [Quantexa internal fraud](https://www.quantexa.com/solutions/internal-fraud/)
- Quantexa claims entity-resolution accuracy "up to 99%". This is a vendor figure and unverified. — [Quantexa FAQs](https://www.quantexa.com/faqs/)
- Celent's (older, about 5 years) regtech brief describes Quantexa Contextual Monitoring as an alert-generation solution with "promising" pilot results at large banks. — [Celent solution brief](https://www.celent.com/en/insights/779309951)
- **NICE ActOne:** visual exploration of network connections, "non-obvious connections" and **inferred risk** (indirect links to high-risk entities), plus "Risk Exposure Identification" of the riskiest people in a network. — [NICE network analytics brochure (PDF)](https://www.niceactimize.com/Documents/network_analytics_brochure.pdf)
- **Flagright:** multi-hop relationship graphs, shared-entity detection, transaction **flow mapping** and linked-identity analysis inside the case. — [Flagright Case Management](https://www.flagright.com/case-management)
- **Hawk:** the case manager shows alerts, customer profile, **transaction and money-flow details** and earlier investigator decisions in one view. — [Hawk on AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-rpzthzm7wt44i)
- **Lucinity:** the page links alerts to their entities and has a "Customer 360°" module, but does not describe a graph visualization. — [Lucinity Case Manager](https://lucinity.com/case-management)

### Inferences
- For GraphGuard, a credible "ring view" is a **bounded ego-graph** (1-2 hops by default, expand on click) centred on the alerted account, with edges as dated money flows, nodes coloured by score, and a time slider. That lines up with the Phase 1 finding that rings span a median of 8 accounts over 3 days. A side panel listing the ring's members as a table covers users who find graphs confusing, which is the objection Quantexa itself records.

### Gaps
- No official Quantexa UI documentation or screenshots were reachable. Hop limits, layout and how the scorecard explains itself are not publicly documented.

## 3. How alerts are explained

### Takeaway
There are three layers: (a) **reason codes** or typology labels per alert (rules or scorecard hits), (b) a plain-language **"why this was flagged"** sentence, and, since 2023-2025, (c) an **LLM-written case summary and SAR narrative draft** with source-linked evidence. Public pages say almost nothing about feature-contribution (SHAP-style) displays.

### Cited Findings
- **Hawk:** a "reason code" on every alert for investigators, and a "plain-language explanation of why it was surfaced" for each flagged transaction. Third-party reviews call the XAI patent-pending and built for audit-ready reasoning. — [Hawk fraud solution](https://hawk.ai/solutions/fraud); [Hawk on AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-rpzthzm7wt44i); [Slashdot Hawk listing](https://slashdot.org/software/p/HAWK-AI/)
- **Hawk AML Investigative Agent:** gathers and summarizes case data **before the analyst opens the alert**, offers a context-aware chat that returns **source-linked transactions**, keeps the case summary updated, logs its own actions, and drafts SAR narratives. — [Hawk AML Investigative Agent (search snippet; the page returned 403 on fetch)](https://hawk.ai/solutions/aml/aml-investigative-agent)
- **Napier** (secondary): natural-language reason codes that can feed SAR narrative sections, and a library of 100+ AML typologies. — [Fraudio roundup](https://www.fraudio.com/roundups/best-anti-money-laundering-software-for-fintech)
- **ComplyAdvantage:** an ensemble model weighs fraud scenarios and "explains the basis for each alert". — [ComplyAdvantage vendor page](https://complyadvantage.com/vendor/best-fraud-detection-software/)
- **Feedzai** (secondary): "whitebox" or transparent risk scoring and a "TRUST" explainability framework. — [FluxForce comparison](https://www.fluxforce.ai/compare/fluxforce-vs-sardine-vs-feedzai)
- **Quantexa:** example output of the form "Risk score HIGH (9/10), due to detection of a network of fraudulent activity". The explanation is the network finding itself. — [Quantexa blog: contextual information in agentic systems](https://www.quantexa.com/blog/the-role-of-contextual-information-in-enhancing-agentic-systems/)
- **Flagright AI Forensics:** an investigation starts automatically when a case opens, with evidence, **typology matches** and a recommendation ready before the analyst reviews it. — [Flagright Case Management](https://www.flagright.com/case-management)
- **Lucinity:** an Investigation Co-Pilot handles summarization, lookups and explanations. Luci, launched June 2023 with trials at Currencycloud and Arion Bank, writes structured case summaries and narratives. — [Lucinity Case Manager](https://lucinity.com/case-management); [Lucinity Luci press release 2023](https://lucinity.com/luci-press-release)
- **SymphonyAI Sensa Copilot** (generative AI investigator assistant, launched 2023): resolves investigations "up to 70% faster" (vendor claim). — [SymphonyAI Copilot announcement](https://www.symphonyai.com/resources/blogs/symphonyai-sensa-netreveal-unveils-trailblazing-generative-ai-driven-investigator-assistant)
- **NICE:** agentic AI added to ActOne and X-Sight in April 2025. — [BusinessWire, Apr 2025](https://www.businesswire.com/news/home/20250402173967/en/NICE-Actimize-X-Sight-ActOne-Platform-Redefines-Financial-Crime-Investigations-with-Agentic-AI)

### Inferences
- By 2026 the market-standard explanation is **typology label + reason codes in plain language + an evidence-linked summary**. Raw SHAP bars are not something vendors highlight to investigators. For GraphGuard's XGBoost, the credible pattern is to translate the top contributions into named reasons (for example "fan-out: 7 new counterparties in 24 h", "first-seen receiver") with the underlying numbers one click away. Every sentence the agent writes should link to the transactions behind it, as Hawk does.

### Gaps
- No vendor publicly documents a reason-code taxonomy, or shows how feature contributions look on screen.

## 4. Case workflow: triage, investigation, escalation, SAR/STR, dispositions, four-eyes, audit

### Takeaway
The standard flow is **L1 triage (close as false positive or escalate) → L2 investigation (a case, often merging several alerts) → QA or four-eyes approval → SAR/STR draft → filing (FinCEN BSA e-filing / goAML XML) → audit log**. 2026 products add maker-checker gates, blind review, QA checklists, and an audit trail that **separates human from AI actions**.

### Cited Findings
- **Lucinity:** Workflow Designer with steps and phases, team handovers and parallel actions. **Four-Eye Review** (dual approval), **Blind Review**, configurable QA checklists. An audit log that **tells human decisions apart from AI decisions**. SAR previews, automated XML, direct API filing to FinCEN, NCA and some goAML jurisdictions, CTR support. — [Lucinity Case Manager](https://lucinity.com/case-management)
- **Flagright:** custom statuses, no-code workflows with conditional routing and escalation, review gates, configurable **maker-checker** approvals, full exportable audit trail with filing confirmations stored in the case log, SAR templates selected automatically by jurisdiction, narratives pre-filled, every draft version-tracked. The page claims both "70+ goAML jurisdictions" and "33 countries", so it contradicts itself. — [Flagright Case Management](https://www.flagright.com/case-management)
- **Didit** (a different vendor, used here only to illustrate the pattern): resolving a case does not close it. It moves to "Pending approval" with the proposed resolution attached. — [Didit console docs](https://docs.didit.me/console/case-management)
- **Unit21:** alerts → cases → reports (SARs) each have queues and deadlines. Reopening closed alerts is supported. — [Unit21 docs: Alerts](https://docs.unit21.ai/docs/alerts); [Unit21: queue-based deadlines](https://docs.unit21.ai/docs/how-to-create-queue-based-deadlines)
- **Hawk:** SAR/CTR filing workflows in the case manager. Auto-close ML models **learn from investigator decisions** made there. — [Gappsy Hawk review](https://www.gappsy.com/tools/hawk/); [Slashdot Hawk listing](https://slashdot.org/software/p/HAWK-AI/)
- **[INDEPENDENT, industry body]** A 2024 BPI survey of 15 banks with $100B+ in assets put the effort at **21.41 hours per SAR filed**, more than 10x FinCEN's estimate of 1.98 hours. — [BPI: FinCEN underestimates SAR filing demands](https://bpi.com/bpi-survey-finds-fincen-significantly-underestimates-sar-filing-demands/)

### Inferences
- A credible demo shows: a disposition picker (false positive / escalate / SAR recommended, each needing a reason), a second-reviewer approval step, and an append-only audit log tagged human or agent. GraphGuard's late-label policy (S6.9) fits naturally, because the disposition *is* the label, with `label_known_at` set when it is recorded.

### Gaps
- Standard disposition taxonomies (exact codes) are not published by vendors.

## 5. What investigators and managers need or hate (alert fatigue, FP rates, time per alert)

### Takeaway
"90-95% false positives" is quoted everywhere, but almost always by vendors without a traceable method. The strongest independent numbers concern **outcomes and effort**: about 4% of SARs drew any law-enforcement follow-up (BPI, 2017 data), and 21 hours per SAR (BPI, 2024). Time-per-alert estimates run from about 20 min to 90 min, and one bank reported 4 h. All of these are weakly sourced.

### Cited Findings
- **[INDEPENDENT, industry body]** BPI (2018 report on 2017 data): banks filed more than 640,000 SARs, and **only about 4%** led to any law-enforcement follow-up. Of about 2.36M high-risk customers, a median of about 6% were subject to SARs and 0.3% drew a follow-up inquiry. 18% of alerts related to structuring. BPI notes there is no established metric for whether SARs are useful. — [BPI Getting to Effectiveness](https://bpi.com/getting-to-effectiveness-report-on-u-s-financial-institution-resources-devoted-to-bsa-aml-sanctions-compliance/); [BPI Reviewing AML/CFT Effectiveness (PDF, 2019)](https://bpi.com/wp-content/uploads/2019/05/BPI-Reviewing-AML_CFT-Effectiveness.pdf)
- **[INDEPENDENT, industry body]** 21.41 h per SAR (BPI 2024, 15 large banks). — [BPI](https://bpi.com/bpi-survey-finds-fincen-significantly-underestimates-sar-filing-demands/)
- **[INDEPENDENT, survey, adjacent domain]** An Eventus / Datos Insights survey of 20 banks and broker-dealers found 70% with false-positive rates above 25%. It covers trade surveillance, not AML. — [The Full FX](https://thefullfx.com/survey-sees-compliance-alert-fatigue/)
- Vendor ranges for FP rates: 85-95% ([Facctum 2026 report](https://www.facctum.com/blog/aml-false-positive-report)), 90-95% for rule-based TM ([Tookitaki](https://www.tookitaki.com/compliance-hub/reducing-false-positives-transaction-monitoring)). A "Gartner" 90-95% fraud figure is cited secondhand ([FluxForce](https://www.fluxforce.ai/blog/fraud-alert-fatigue)) and I could not verify it.
- Alert-to-SAR conversion is typically 1-5%, and "95-98% of alerts close without a SAR" (vendor blogs). — [Sphinx AML KPIs](https://sphinxhq.com/blog-posts/aml-compliance-kpis-metrics); [Zigram FRAML KPIs](https://www.zigram.tech/article/framl-compliance-kpis/)
- Time per alert (vendor estimates): 20-30 min routine and 60-90 min complex ([Particula](https://particula.tech/blog/aml-alert-triage-ai-false-positives)). 20-60 min ([Flipzen](https://www.flipzen.com/blog/ai-false-positives-aml-transaction-monitoring)). "47 min average" with no method given ([Flagright blog](https://www.flagright.com/post/how-ai-forensics-fixes-alert-overload-for-aml-compliance-analysts)). One global bank averaged about 4 h per alert (secondhand, [krpushkar blog](https://krpushkar08.blogspot.com/2025/10/false-positives-in-aml-strain-on-team.html?m=1)). For sanctions screening, more than 5-10 min per alert with under 10% true matches is a sign the rules need tuning ([Sardine](https://www.sardine.ai/blog/rules-to-reduce-false-positives-in-sanctions-screening)).
- Throughput example: about 20 alerts closed per investigator per day, given as an illustrative baseline. — [Sphinx AML KPIs](https://sphinxhq.com/blog-posts/aml-compliance-kpis-metrics)
- Burnout: "67% of fraud/AML analysts report moderate to severe burnout", attributed to ACAMS by a vendor. I could not find the original. — [FluxForce](https://www.fluxforce.ai/blog/fraud-alert-fatigue)
- Pain points vendors say they address: context switching between systems (Hawk's "one view", Lucinity's Customer 360), narrative writing (Palla testimonial: "90 minutes saved per day on narratives"), backlog. — [Flagright](https://www.flagright.com/case-management); [Hawk AWS listing](https://aws.amazon.com/marketplace/pp/prodview-rpzthzm7wt44i)
- **Vendor outcome claims (unverified):** Hawk, up to 70% fewer false alerts and about 62% less investigation time ([Slashdot](https://slashdot.org/software/p/HAWK-AI/)). NICE, up to 50% less investigation time and 70% less SAR-filing time ([ActOne brochure](https://www.niceactimize.com/Lists/Brochures/actone_modernize_your_financial_crime_investigations_brochure.pdf)). Flagright, 80% faster closes ([Flagright](https://www.flagright.com/case-management)). SymphonyAI, 20% effort savings in L1/L2 within weeks at a "leading European bank" and €3.5M a year saved ([SymphonyAI case study](https://www.symphonyai.com/resources/case-study/financial-services/sensa-investigation-hub-leading-european-bank)), 47%+ FP reduction at an Australian bank and 91.8% at a Spanish bank ([SymphonyAI case studies](https://www.symphonyai.com/resources/case-study/financial-services/sensaai-aml-monitoring-australia/)). Lucinity, "hours to minutes" ([Lucinity](https://lucinity.com/luci)).

### Inferences
- These numbers support GraphGuard's own framing: **precision@k at a fixed daily capacity** (S6.9 already assumes 100 alerts a day) is exactly the operational question. At about 20 alerts per analyst per day, 100 alerts a day is roughly a 5-analyst team, a useful line for a demo. Any time-saving claim should be measured (for example the investigator-agent evaluation in Phase 7), not asserted, because the market is full of unverified percentages.

### Gaps
- No primary ACAMS, Gartner or regulator dataset with measured alerts per analyst per day or minutes per alert was found. No independent study validates any vendor FP-reduction claim.

## 6. Manager dashboards and KPIs; public screenshots and demos

### Takeaway
Manager KPIs are consistent across sources: **backlog and aging buckets against SLA, handle time, alerts closed per analyst, SLA breaches, alert → case → SAR conversion, FP rate, workload distribution**, plus QA results. Vendors rarely show model-performance panels to managers. Public screenshots and detailed demo descriptions are scarce.

### Cited Findings
- **Lucinity** dashboards: time elapsed, SLA breaches, workload distribution, aggregated insights. — [Lucinity Case Manager](https://lucinity.com/case-management)
- **Flagright** operational dashboard: analyst performance, SLA compliance, resolution time, alert-to-case metrics. — [Flagright Case Management](https://www.flagright.com/case-management)
- KPI definitions: backlog = alerts past the internal SLA. Aging buckets at more than 7, 14 and 30 days, by tier. Backlog growth is "the single most reliable leading indicator" of a capacity problem. Conversion can be inflated just by suppressing alerts, so read it next to coverage. — [Sphinx AML KPIs](https://sphinxhq.com/blog-posts/aml-compliance-kpis-metrics); [FluxForce alert prioritization](https://www.fluxforce.ai/controls/alert-prioritization); [Zigram FRAML KPIs](https://www.zigram.tech/article/framl-compliance-kpis/)
- An open-source example of an AML KPI layer (simulated data): open backlog, alerts older than 30 days, SAR conversion on closed cases, alerts closed per investigator per week, alert-volume forecast and capacity model. — [GitHub aml-investigations-capacity-kpis](https://github.com/Siyuan-Zhu/aml-investigations-capacity-kpis)
- Demos: SymphonyAI publishes a Sensa Copilot video ([SymphonyAI video](https://www.symphonyai.com/resources/video/financial-services/sensa-copilot/)). NICE publishes ActOne brochures ([ActOne PDF](https://www.niceactimize.com/Documents/ActOne_Operate_at_the_Speed_of_Risk.pdf)). I did not view their visual content.

### Inferences
- A manager view for GraphGuard could combine operations KPIs (backlog by age bucket, SLA breaches, per-reviewer throughput, alert → escalation → SAR-recommended funnel) with what incumbents lack: **live model health** (precision@k on labels known so far, drift, champion vs shadow from S6.10). The panel must say that labels are delayed and biased toward the champion (FINDING-017).

### Gaps
- I could not inspect any screenshots or videos directly, so the visual layout (colours, density, panel placement) is not sourced. No analyst report (Chartis, Celent 2025-26, Gartner Market Guide) was retrieved in full. Lucinity says it appears in Gartner's 2025 Market Guide for AML, but that is a self-report ([Lucinity search result](https://lucinity.com/blog/lucinity-turns-six)).
