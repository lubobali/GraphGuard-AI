# Financial crime business problems banks are paying for (as of Nov 2026)

Research date: 2026-11-17. About 21 search/fetch calls. Primary sources I actually opened: the UK Finance press release (15 Jun 2026). The Bratby Law summary of the PSR/Frontier evaluation and the Zyphe summary of the FCA mule review are secondary write-ups of primary documents, and they are cited as secondary. Many other figures come from search-result summaries of press, law-firm and vendor pages. Treat those as "verify against the primary source before quoting". Vendor claims are labelled VENDOR CLAIM.

## 1. APP scams: losses, UK reimbursement regime and its effect, moves elsewhere

### Takeaway
APP fraud is the fastest-growing loss line in UK payments: £576.4m in 2025, up 19%. Investment scams drive it. Since 7 Oct 2024 the UK has made sending and receiving PSPs split reimbursement 50/50, up to £85,000 per claim. That puts a direct P&L cost on the *receiving* bank for every mule account it hosts. The first independent evaluation (Jul 2026) found in-scope losses fell about 21%, but fraud is moving to out-of-scope channels (international payments, crypto). Other countries are copying the idea unevenly. Australia's SPF is the closest match. Singapore's SRF excludes authorised payments. The EU PSR is still not in force. In the US there is no federal regime, and the fight runs through state litigation (NY AG v. Zelle/EWS).

### Cited Findings
**UK loss figures (UK Finance Annual Fraud Report 2026, covering calendar 2025, published 15 Jun 2026)**
- Total payment fraud £1.28bn in 2025, up 4%. Industry prevented £1.68bn. — [UK Finance press release](https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release)
- APP losses £576.4m, up 19%. Personal £500.8m, business £75.6m. Cases 248,070, up 7%. — [UK Finance](https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release)
- Investment scams £221.5m, up 40% (14,893 cases, up 26%). That is about 38% of APP losses. Purchase scams £118.1m, up 20%, and 71% of APP cases. Romance £39.2m, up 23%. Impersonation losses down 12%. — [UK Finance](https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release); 38% share per [FinTech Futures](https://www.fintechfutures.com/financial-crime-fraud-prevention/uk-payment-fraud-losses-topped-1-28bn-in-2025-new-uk-finance-report-finds)
- Origin of APP cases: online 66% of cases / 32% of losses; telecoms 17% / 28%; unknown 11% / 24%. — [UK Finance](https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release)
- Banks reimbursed £354.3m, 61% of APP losses, across all payment types. The PSR figure for in-scope Faster Payments is 89% over the first 15 months. UK Finance says the two differ because of scope. — [UK Finance](https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release)
- Unauthorised fraud £703.4m, down 5%, on 3.81m cases, up 11%. — [UK Finance](https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release)

**UK mandatory reimbursement regime (PSR)**
- In force since 7 Oct 2024 for Faster Payments (CHAPS too, per PSR policy). Sending and receiving PSPs split eligible reimbursement 50/50, up to £85,000 per claim. Reimbursement is generally due within 5 business days. Optional excess is up to £100. The Consumer Standard of Caution exception applies. — [Bratby Law on PSR evaluation](https://bratby.law/app-fraud-reimbursement-evaluation/); [PSR PS25/5 consolidated policy statement](https://www.psr.org.uk/media/rhelv4op/ps25-5-app-scams-reimbursement-consolidated-policy-statement-may-2025.pdf)
- The £85k cap replaced a £415k figure first proposed. — [search summary of Edgar Dunn / Norton Rose Fulbright](https://www.edgardunn.com/articles/one-year-on-uks-app-fraud-reimbursement-rules)
- Frontier Economics evaluation for the PSR (published 1 Jul 2026): in-scope Faster Payments APP losses fell about 21%, roughly £73m a year. Scam volumes fell from about 40k to about 35k a month. The share of confirmed losses reimbursed by value rose from 54% to 65%. The PSR dashboard reports 88% of *eligible* claims reimbursed. — [Bratby Law](https://bratby.law/app-fraud-reimbursement-evaluation/)
- Per-PSP reimbursement rates ranged from 21% to 94%. One firm applied the caution exception to more than 25% of value, while others never used it. The cap rarely binds: more than 99% of claims and more than 95% of value fall under £85k. — [Bratby Law](https://bratby.law/app-fraud-reimbursement-evaluation/)
- Displacement: international APP scams rose from £21m (2023) to £60m (2025), and APP to crypto exchanges from about £59m to £153m. After displacement and under-reporting, the net benefit is estimated at -£4m to +£8m a year. PSP non-reimbursement costs are £44m to £56m a year. — [Bratby Law](https://bratby.law/app-fraud-reimbursement-evaluation/)
- Biggest reductions came from firms with the highest pre-policy fraud rates that had not reimbursed before, which is what the incentive design predicted. — [Bratby Law](https://bratby.law/app-fraud-reimbursement-evaluation/)
- Next steps: PSR consultation Dec 2026, decision and revised directions May 2027. Topics include the caution standard, investment-scam returns, and data on the platforms fraudsters use. HM Treasury (Apr 2026) confirmed that PSR functions will move into the FCA, subject to legislation. — [Bratby Law](https://bratby.law/app-fraud-reimbursement-evaluation/)
- Conflicting year-one figures in secondary sources: about £173m returned (88%); 88% of £316m (Oct 2024 to Mar 2026); about £112m (Oct 2024 to Jun 2025). These differ by cut-off date. — [Business Expert](https://www.businessexpert.co.uk/data/payments/fraud-reimbursement-statistics/); [Edgar Dunn](https://www.edgardunn.com/articles/one-year-on-uks-app-fraud-reimbursement-rules)

**US**
- CFPB sued Early Warning Services (Zelle) and JPMorgan, BofA and Wells Fargo in Dec 2024, then voluntarily dismissed with prejudice in Mar 2025. — [OpenClassActions (secondary)](https://openclassactions.com/settlements/zelle-fraud-class-action-settlement.php); [Consumer Finance Monitor](https://www.consumerfinancemonitor.com/2026/07/31/new-york-court-refuses-to-dismiss-attorney-generals-sweeping-fraud-case-against-zelle-operator-early-warning-services/)
- NY AG Letitia James sued EWS under NY law in Aug 2025, alleging more than $1bn in consumer losses on Zelle from 2019 to 2022. On 20 Jul 2026 a NY judge refused to dismiss, and Zelle said it would appeal. — [NY AG press release](https://ag.ny.gov/press-release/2025/attorney-general-james-sues-company-behind-zelle-enabling-widespread-fraud); [Consumer Finance Monitor](https://www.consumerfinancemonitor.com/2026/07/31/new-york-court-refuses-to-dismiss-attorney-generals-sweeping-fraud-case-against-zelle-operator-early-warning-services/); [Insurance Journal](https://www.insurancejournal.com/news/east/2026/07/24/878853.htm)
- Federal bill: the Protecting Consumers from Payment Scams Act (H.R. 9303 / S. 4943, Aug 2024) would have amended the EFTA to cover induced payments, with shared liability between sending and receiving institutions. Bank groups opposed it. I found no 2026 reintroduction. — [ABA Banking Journal](https://bankingjournal.aba.com/2024/08/democrats-introduce-bill-to-require-reimbursements-for-electronic-transfer-fraud/); [govinfo S.4943](https://www.govinfo.gov/content/pkg/BILLS-118s4943is/xml/BILLS-118s4943is.xml)
- FinCEN Alert FIN-2026-Alert005 (3 Sep 2026): about $12.7bn linked to suspected overseas scam-centre activity, from 33,904 BSA reports (Sep 2023 to Dec 2025). The networks use stablecoins, shell companies and money mules. — [AML Intelligence](https://www.amlintelligence.com/2026/09/news-us-treasury-flags-13bn-linked-to-overseas-scam-centers/); [FinCEN alert PDF copy](https://primarynewssource.org/wp-content/uploads/FinCEN-Alert-Scam-Centers.pdf)

**EU / Australia / Singapore**
- EU: under the Instant Payments Regulation, euro-area PSPs had to offer Verification of Payee (IBAN-name check) from 9 Oct 2025. The PSD3/PSR package (payee-verification liability, impersonation-fraud liability) has reached provisional political agreement but, per secondary sources, is not yet in the Official Journal. Phased obligations would follow 18 to 21 months after publication. — [search summary: The Paypers](https://thepaypers.com/payments/expert-views/a2a-payments-regulatory-and-fraud-prevention-frameworks); [HLC](https://www.hlc.com/en/publications/new-era-of-fraud-prevention-global-regulations-demand-accountability-from-banks-and-telcos)
- Australia Scams Prevention Framework (Part IVF, Competition and Consumer Act): banks are designated, and AFCA is the external dispute scheme. Second transitional phase from 1 Sep 2026. Full obligations from 31 Mar 2027. Unlike Singapore, it covers authorised (deceived) transfers. — [Amjid Ali operator guide (secondary)](https://amjid.au/insights/australias-scams-prevention-framework-operators-guide/); [The Industry Spread](https://theindustryspread.com/australia-spf-banking-charter-perimeter-f2026l01140/)
- Singapore Shared Responsibility Framework: in force 16 Dec 2024. It splits losses for *phishing* scams in a waterfall (bank, then telco, then customer) and expressly excludes authorised transfers. — [nhimg comparison (secondary)](https://nhimg.org/scam-reimbursement-rules-comparison-guide); [Lexology](https://www.lexology.com/library/detail.aspx?g=507f312f-9065-48f9-8acc-42b601a6bbf7)

### Inferences
- The UK 50/50 split is the single clearest money reason for a *receiving* bank to buy mule detection. Every APP scam that lands in its account costs it half the reimbursement. Before Oct 2024 the receiving bank paid nothing.
- Displacement to crypto and international rails means a pure "Faster Payments in, Faster Payments out" view is not enough. Cross-channel graph context matters.
- Per-PSP reimbursement ranges of 21% to 94%, and published PSR league tables, mean fraud performance is now a reputation metric as well as a cost.

### Gaps
- I did not open the PSR dashboard or the Frontier report directly. Figures come via Bratby Law.
- Exact current status of EU PSR/PSD3 (Official Journal publication date) is unconfirmed.
- I did not find the official Treasury/ASIC SPF dates, or MAS SRF primary pages.
- No reliable 2026 US federal legislative status. The CFPB's 2026 posture on P2P scams was not found.
- The breakdown of how much reimbursement receiving PSPs actually paid, versus sending PSPs, was not found.

## 2. Money mule accounts: scale, receiving-bank gap, graph approaches, data sharing

### Takeaway
UK firms offboarded about 238k suspected mule accounts in 2025, but filed only 15.3% of them to the shared Cifas database. The FCA's Sept 2026 review explicitly tells firms to look *beyond the first receiving account* to linked accounts and transaction context. Cash-out usually happens at hop 2 to 5. That is a direct regulatory call for network-level (graph) mule detection at the receiving side.

### Cited Findings
- FCA multi-firm review "Money mules: mule activity and cashing out findings" (23 Sep 2026): based on a 35-firm survey and a public-private cell of 22 firms tracing 140 cases across 7 fraud types. — [FCA (primary, via Zyphe link)](https://www.fca.org.uk/publications/multi-firm-reviews/money-mules-activity-cashing-out-findings); [Zyphe summary](https://www.zyphe.com/resources/news/fca-money-mule-accounts-review-september-2026)
- Suspected mule accounts offboarded: 184,935 (2023), 233,269 (2024), 238,396 (2025). Share filed to the NFD: 19.7%, then 17.4%, then 15.3%. 2025 NFD filings were 36,502. Payment and e-money institutions filed about 1.2%. — [Zyphe](https://www.zyphe.com/resources/news/fca-money-mule-accounts-review-september-2026); [Credit Connect](https://www.credit-connect.co.uk/drafts/financial-firms-shut-hundreds-of-thousands-of-suspected-money-mule-accounts/)
- Cash-out typically happens between the 2nd and 5th account in a chain, most often the 2nd. 47.1% of 2025 mule closures were accounts under one year old, and 55,353 were under 3 months old. At retail banks, 45.4% of closures were accounts more than 2 years old, so ongoing monitoring matters as well as onboarding. — [Zyphe](https://www.zyphe.com/resources/news/fca-money-mule-accounts-review-september-2026)
- FCA expectation: controls should look beyond the initial receiving account to linked accounts, payment characteristics and wider transaction context. The review sets no new rules. — [Zyphe](https://www.zyphe.com/resources/news/fca-money-mule-accounts-review-september-2026)
- Cifas: about 13,000 mule filings to the NFD in H1 2026, about 69% to 70% above H1 2025. The dedicated mule category started in 2025, which had more than 22,000 filings, so part of the rise may be adoption of the new code. Personal accounts were 89% of 2025 mule filings. — [AML Intelligence](https://www.amlintelligence.com/2026/08/news-uk-money-mule-cases-surge-69-in-first-half-of-2026/); [Cifas Fraudscape 2026](https://www.fraudscape.co.uk/); [fintechly](https://fintechly.com/banking/money-mule-detection/)
- Note that FCA's 36,502 NFD mule filings (2025) and Cifas's "22,000+" (2025) differ. The likely cause is different category definitions. Unresolved. — [Zyphe](https://www.zyphe.com/resources/news/fca-money-mule-accounts-review-september-2026); [fintechly](https://fintechly.com/banking/money-mule-detection/)
- NCA estimate: more than £100bn laundered through the UK or UK corporate structures each year. — [Credit Connect](https://www.credit-connect.co.uk/drafts/financial-firms-shut-hundreds-of-thousands-of-suspected-money-mule-accounts/)
- UK legal basis for sharing: ECCTA 2023 s.188/189 (in force 15 Jan 2024) disapplies confidentiality and civil liability for qualifying disclosures. The Data (Use and Access) Act 2025 s.70 (from 5 Feb 2026) makes crime prevention a recognised legitimate interest. — [Zyphe](https://www.zyphe.com/resources/news/fca-money-mule-accounts-review-september-2026)
- Europol EMMA 9 (2023 phases): 10,759 mules and 474 recruiters identified, 1,013 arrests, about €32m in losses prevented. Some outlets wrongly report 10,759 as arrests. — [Europol](https://www.europol.europa.eu/media-press/newsroom/news/paper-trail-ends-in-jail-time-for-1-013-money-mules)
- US: FinCEN alerts in 2025 and 2026 repeatedly name money mules as the laundering layer: scam centres (FIN-2026-Alert005), student aid fraud (FIN-2026-Alert004), Chinese money laundering networks (FIN-2025-A003). — [AML Intelligence](https://www.amlintelligence.com/2026/09/news-us-treasury-flags-13bn-linked-to-overseas-scam-centers/); [Orrick InfoBytes](https://infobytes.orrick.com/2026-07-31/fincen-alerts-financial-institutions-of-fraud-schemes-targeting-federal-student-aid-programs/); [LearnSignal on FIN-2025-A003](https://www.learnsignal.com/blog/chinese-money-laundering-networks-fincen-fin-2025-a003-money-mules-insiders-account-red-flags-guide/)
- Industry voices in the UK Finance 2026 release (VENDOR CLAIMS: BioCatch, Nasdaq Verafin) call for disrupting mule accounts with real-time behavioural signals and for more cross-institution data sharing. — [UK Finance](https://www.ukfinance.org.uk/news-and-insight/press-release/fraud-report-2026-press-release)

### Inferences
- "Receiving bank is the gap" is now an official position in the UK. It shows in the FCA's hop-2-to-5 finding, its "look beyond the first account" expectation, and falling sharing rates, all set against the 50/50 cost incentive.
- A single bank only sees its own slice of a ring. Graph models inside one bank still help, by linking a bank's own accounts through shared counterparties, devices and timing. A synthetic full-graph project should say plainly that a real bank would see only a subgraph.

### Gaps
- I could not verify details of the Australian Fraud Reporting Exchange (AFCX), Swift's fraud data-sharing work, or UK Finance's intelligence-sharing schemes in this budget. Searches returned nothing usable.
- No named bank publicly disclosing a graph/GNN mule model in production was found, other than HSBC's AML AI (see section 4).
- No 2025 or 2026 EMMA totals found.

## 3. Transaction monitoring cost, false positives, and enforcement 2024-2026

### Takeaway
Regulators fine banks for monitoring that is *missing, stale, or backlogged*: unmonitored volumes, data feeds that drop transactions, and alert backlogs that delay SARs by more than a year. Being "too noisy" alone is not what gets fined. Noise matters because it creates backlogs. The widely quoted "90-95% false positives" figure has no clean primary source.

### Cited Findings
**Cost**
- LexisNexis Risk Solutions (VENDOR CLAIM, Forrester-run study): US and Canada financial crime compliance spend was $61bn in 2023, with costs up for 99% of institutions. Global spend was more than $206bn (2023 study). — [Forrester/LexisNexis 2023 US & Canada PDF](https://www.corporatecomplianceinsights.com/wp-content/uploads/2024/02/Forrester-LexisNexis-Risk-Solutions-True-Cost-of-Financial-Crime-Compliance-Study-2023.pdf)
- I found no 2025 or 2026 edition of LexisNexis True Cost with transaction monitoring false-positive figures. The 2024 UK edition has a false-positive table where transaction monitoring shows 12.4% and 8.1% in two columns with unclear labels. That conflicts with the "90-95%" claims. — [LexisNexis True Cost 2024 UK](https://risk.lexisnexis.co.uk/-/media/files/business/white-paper/lnrs_true_cost_of_financial_crime_compliance_2024_wp_uk%20pdf)
- "90-95% of rules-based alerts are false positives" is repeated by vendors and blogs, attributed to "industry analyses". No primary source found. — [FluxForce (VENDOR)](https://www.fluxforce.ai/statistics/false-positive-rates-transaction-monitoring)

**Enforcement: what regulators actually criticised**
- **TD Bank (Oct 2024, about $3.09bn, guilty plea to BSA/money laundering conspiracy):** transaction monitoring was not substantively updated from at least 2014 to 2022. About 92% of transaction volume (about $18.3trn) went unmonitored from Jan 2018 to Apr 2024. Regulators and internal audit repeatedly flagged the problem. The bank got a US asset cap and an independent monitor. — [CNBC](https://www.cnbc.com/2024/10/10/td-bank-3-billion-fine-doj-settle-money-laundering-drug-cartel.html); [Bradley](https://www.bradley.com/insights/publications/2024/11/3-billion-td-bank-aml-settlement-is-a-wake-up-call-for-all-banks)
- **Metro Bank (FCA, Nov 2024, £16,675,200 after a 30% discount; £23.8m before):** a data error in the store feeding its automated transaction monitoring system meant transactions were missing or rejected for more than 3 years. That is over 60m transactions, worth more than £51bn, about 6% of volume. — [Lexology](https://www.lexology.com/library/detail.aspx?g=d451b44d-5f84-46ae-8a6c-c207b081443e); [FinTech Futures](https://www.fintechfutures.com/financial-crime-fraud-prevention/metro-bank-fined-16-7m-by-the-fca-for-financial-crime-failings-)
- **Starling (FCA, Oct 2024, £28,959,426):** financial crime controls failed to keep pace with growth. The bank breached a voluntary restriction on onboarding high-risk customers. The FCA called its sanctions screening "shockingly lax". — [search summary incl. ComplyStream](https://www.complystream.com/post/fincrime-fines-starling-monzo-vocalink-wise)
- **Monzo (FCA, Jul 2025, £21,091,300 after a 30% discount; £30.1m before):** inadequate financial crime systems and controls, Oct 2018 to Aug 2020. It opened about 26,325 accounts for high-risk customers (another source says 34,000+) in breach of an agreed restriction from 2020 to 2022. — [FCA press release](https://www.fca.org.uk/news/press-releases/fca-fines-monzo-21m-failings-financial-crime-controls); [HSF Kramer](https://www.hsfkramer.com/notes/fsrandcorpcrime/2025-posts/aml-update-5-aug-2025)
- **Block / Cash App (NYDFS, Apr 2025, $40m plus a 1-year independent monitor):** a significant transaction monitoring alert backlog from 2018 to 2021 meant some SARs were filed more than a year after the alert. It also processed high-risk anonymous Bitcoin transactions without enough scrutiny. Separately, about $80m was paid to other state regulators in Jan 2025 (composition unverified). — [GRC Report](https://www.grcreport.com/post/nydfs-hits-block-inc-with-40-million-settlement-over-cash-app-compliance-failures); [Retail Banker International](https://www.retailbankerinternational.com/news/block-settle-fine/)

### Inferences
- The fined failure pattern is (a) coverage gaps, (b) controls not scaling with fast growth (Starling, Monzo, Cash App: all fintechs), and (c) alert backlogs. A ranked queue that lets a fixed team clear the riskiest alerts first speaks directly to (c). Precision@k at fixed investigator capacity is the right metric to frame it.

### Gaps
- No credible primary 2025 or 2026 false-positive rate found. Report it as "vendors claim 90-95%, unverified".
- I did not open the TD plea agreement or the FCA final notices.
- No 2026 transaction-monitoring fines were found in this search. There may be some I missed.

## 4. AI agents / GenAI in AML investigations: deployments and regulator stance

### Takeaway
Named-bank deployments are few and mostly vendor-announced. HSBC's Google AML AI (ML risk scoring, not GenAI) is the best-documented production ML case. In 2026 the GenAI wave is investigation and SAR-drafting agents. FIS's Claude-based agent, with BMO and Amalgamated Bank as first adopters, is a projection, not measured results. On 17 Apr 2026, US model risk guidance (SR 11-7) was replaced by SR 26-2 / OCC Bulletin 2026-13, which explicitly *excludes* generative and agentic AI.

### Cited Findings
- HSBC with Google Cloud AML AI ("Dynamic Risk Assessment"): piloted from 2021. It reports 2 to 4 times more suspicious activity found and a 60% cut in alerts. Some sources describe the 60% as a cut in false positives instead. VENDOR CLAIM, originating in Google's case study. — [Google Cloud blog](https://cloud.google.com/blog/topics/financial-services/how-hsbc-fights-money-launderers-with-artificial-intelligence?authuser=0); [HSBC views](https://www.hsbc.com/news-and-views/views/hsbc-views/harnessing-the-power-of-ai-to-fight-financial-crime)
- FIS AML Investigations Agent (built with Anthropic Claude) is commercially available to US banks in 2026. BMO and Amalgamated Bank are named first deployers. Projected for Amalgamated: L1 alert review time down more than 90%, L2 investigation time down about 98%, SAR narrative time down more than 80%. VENDOR PROJECTIONS, not measured results. — [FIS press release](https://www.fisglobal.com/about-us/media-room/press-release/2026/fis-aml-investigations-agent-now-commercially-available); [FIS + Anthropic](https://www.fisglobal.com/about-us/media-room/press-release/2026/fis-brings-agentic-ai-to-banking-with-anthropic-starting-with-financial-crimes); [Forbes, 15 Oct 2026](https://www.forbes.com/sites/nicolecasperson/2026/10/15/fis-launches-ai-banking-agent-as-fintech-compliance-faces-a-trust-test/)
- SR 26-2 (Fed) and OCC Bulletin 2026-13, issued 17 Apr 2026 with the FDIC, replace SR 11-7 / OCC 2011-12 with more principles-based model risk guidance. They also rescind the 2021 interagency BSA/AML model risk statement (OCC 2021-19). Generative and agentic AI are excluded, and separate AI guidance is promised but not yet issued. Secondary sources only. — [Tyche Consulting](https://www.tycheconsulting.com/insights/april-2026-mrm-update-and-ai.html); [RiskTemplate](https://risktemplate.com/blog/2026-05-02-occ-fed-fdic-revised-model-risk-management-guidance-2026/)
- FinCEN proposed AML/CFT program rule (7 Apr 2026, comments closed 9 Jun 2026) reframes programs around effectiveness ("does your program actually work"). Not final as of Nov 2026. — [Volkov Law, Oct 2026](https://blog.volkovlaw.com/2026/10/fincen-proposes-to-rewrite-the-aml-program-rule-around-one-question-does-your-program-actually-work/); [FinCEN news release](https://fincen.gov/news/news-releases/fincen-issues-proposed-rule-strengthen-and-modernize-financial-institutions)

### Inferences
- With the 2021 BSA/AML model-risk statement gone and GenAI carved out, the *scoring* model (a tree ranking accounts) sits in well-understood governance territory. LLM narrative drafting sits in a governance gap. Keeping the ranker deterministic and explainable (SHAP-style reasons), with any LLM narrative as a separate optional layer, matches where regulators are.
- The 2026 GenAI products all attack investigator time per alert. A ranked queue with reasons attached is the input those agents consume.

### Gaps
- No primary-source named deployments found for JPMorgan or Standard Chartered GenAI in AML.
- Not covered: FCA (AI Lab / live testing), MAS (FEAT/Veritas, AI risk guidelines), EU AMLA, or FATF statements on AI in AML. Searches returned nothing usable in budget.
- The SR 26-2 text was not verified against the Fed primary page.

## 5. EU AMLA timeline and FinCEN program rule status

### Takeaway
The EU single rulebook (AMLR) applies from 10 Jul 2027. AMLA picks its first group of about 40 directly supervised groups from Jul to Dec 2027, and direct supervision starts in 2028. In the US, the April 2026 FinCEN program-rule NPRM is still not final. If adopted, it takes effect 12 months after issuance. The investment-adviser AML rule was pushed to 1 Jan 2028.

### Cited Findings
- AMLA must start the first selection by 1 Jul 2027 and finish within 6 months. National supervisors collect data Jan to Mar 2027. Direct supervision starts about 6 months after the list is published (2028), capped at about 40 entities. — [AMLA](https://www.amla.europa.eu/amla-takes-next-step-toward-2027-selection-entities-direct-supervision_en); [Eltoma (secondary)](https://www.eltoma-global.com/knowledge-base/amla-eu-aml-timeline-2026-2027-2028)
- 2026 steps: AMLA eligibility reporting package released 12 May 2026. National supervisors' data due 15 Aug 2026. Provisional eligible list expected end-Sep 2026. RTS on CDD are being finalised in 2026 and apply from 10 Jul 2027. Secondary sources conflict on draft RTS dates (10 Jul 2026 vs 30 Sep 2026). — [AMLA](https://www.amla.europa.eu/amla-takes-next-step-toward-2027-selection-entities-direct-supervision_en); [Eltoma](https://www.eltoma-global.com/knowledge-base/amla-eu-aml-timeline-2026-2027-2028)
- AMLR applies directly across all 27 member states from 10 Jul 2027. — [RegReportingDesk (secondary)](https://regreportingdesk.com/eu-aml-package-amlr-amld6-amla-guide/)
- FinCEN: program-rule NPRM issued 7 Apr 2026, comments closed 9 Jun 2026. Effective 12 months after the final rule. No finalisation date announced. — [FinCEN](https://fincen.gov/news/news-releases/fincen-issues-proposed-rule-strengthen-and-modernize-financial-institutions); [Lexology tracker](https://www.lexology.com/library/detail.aspx?g=94b3d1c5-9ec2-4f4c-939e-df33bd628457)
- Investment adviser AML/CFT rule delayed from 1 Jan 2026 to 1 Jan 2028. — [Federal Register, 2 Jan 2026](https://www.federalregister.gov/documents/2026/01/02/2025-24184/delaying-the-effective-date-of-the-anti-money-launderingcountering-the-financing-of-terrorism)

### Inferences
- Both regimes are moving towards "effectiveness" and away from "box-ticking". A project that measures detection quality at a fixed investigator capacity (precision@k, rings caught) speaks that language.

### Gaps
- The FinCEN NPRM text was not read. Its specific treatment of innovation and AI in programs is unverified.
- No AMLA RTS content on transaction monitoring or technology was found.

## 6. Which problem best fits a ranked, explained account/ring queue?

### Takeaway
The best fit is **receiving-side mule-network detection for APP scam proceeds**, framed as "UK receiving PSPs now pay 50% of APP reimbursement, and the FCA (Sep 2026) says look beyond the first account; here is a ranked ring queue at fixed investigator capacity". The secondary framing is **alert backlog and triage** (the Block, TD and Metro pattern).

### Cited Findings
- Receiving PSPs pay 50% of eligible APP reimbursement up to £85k. — [Bratby Law](https://bratby.law/app-fraud-reimbursement-evaluation/)
- FCA expects controls to look beyond the initial receiving account to linked accounts and context. Cash-out happens at hop 2 to 5. — [Zyphe summary of FCA review](https://www.zyphe.com/resources/news/fca-money-mule-accounts-review-september-2026)
- Alert backlogs led to SARs filed more than a year late at Block (NYDFS $40m). — [GRC Report](https://www.grcreport.com/post/nydfs-hits-block-inc-with-40-million-settlement-over-cash-app-compliance-failures)
- 2026 GenAI products target investigator minutes per alert. — [FIS](https://www.fisglobal.com/about-us/media-room/press-release/2026/fis-aml-investigations-agent-now-commercially-available)

### Inferences
- Map project features to real pain:
  - Ring-level output maps to the FCA's "linked accounts" expectation.
  - Precision@k maps to fixed investigator capacity and backlog risk.
  - Real-time scoring maps to the 5-business-day reimbursement clock and stopping cash-out at hop 2.
  - Per-alert explanations map to SAR narrative input and model governance.
- Honesty caveats the write-up should state: IBM AMLworld is synthetic and models laundering, not APP scams specifically. A real bank sees only its own subgraph. The fraud-to-mule link (victim payment, then mule) is not labelled in AMLworld.
- Weaker fits: sanctions screening (the Starling issue) and onboarding/KYC (Monzo/Starling restrictions) are not what a transaction-graph ranker solves.

### Gaps
- No public figure found for what UK receiving banks actually paid under the 50/50 split. That would be the strongest single "cost of the problem" number if the PSR publishes it.
