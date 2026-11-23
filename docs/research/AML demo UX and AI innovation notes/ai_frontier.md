# Frontier AI and agentic investigators in AML (as of 23 Nov 2026)

Scope: what is deployed vs piloted vs marketing; what regulators say; evidence on error rates; and which "innovation" a public, cost-capped GraphGuard demo can credibly show. This builds on `AML investigator interface research 2026 notes/explanations_and_agents.md` (22 Nov) and does not repeat it: that note already covers Lucinity/Unit21/Hawk/Quantexa/Napier/Feedzai basics, Co-Investigator AI, AMLBench, SCAFDS, the Wolfsberg Aug 2025 statement and the MAS Oct 2026 guidelines. About 19 search/fetch calls on 2026-11-23. Vendor numbers are marked **[MARKETING]**. Most sources here are secondary (trade press, law-firm memos, vendor blogs); primary documents are flagged where seen.

---

## (a) Deployed vs piloted vs marketing

### Takeaway
"Assist" (the agent gathers evidence and drafts, the analyst decides) is in real production at named institutions in 2026. "Auto-review" (the agent recommends, a human approves) exists but is a minority. Autonomous auto-close of AML alerts is almost never used: the best usage data found shows it at about 0.5% of AI use. Every outcome number below is vendor-reported or a projection, not an independent measurement.

### Cited Findings
- **Unit21, usage data from 1M+ live AI alert reviews over about a year** (published 6 Nov 2026, presented 3 Nov 2026):
  - Usage split: assist about 84%, auto-review about 16%, auto-close "about half a percent".
  - The AI agreed with human reviewers 99% of the time on sanctions alerts and 95% on transaction-monitoring alerts.
  - True-positive rate about 2x human-only overall, about 15x in fraud and about 7x in EDD.
  - No override or error rates are given. It recommends a test set of about 100 verified alerts per use case.
  - **[MARKETING]**, but it is the only usage-mix data found.
  - Source: [Unit21 blog](https://www.unit21.ai/blog/what-1m-live-ai-alerts-tell-us-about-ai-in-fincrime)
- **FIS + Anthropic, Financial Crimes AI Agent:**
  - Announced 4 May 2026, with BMO and Amalgamated Bank developing it.
  - The agent gathers evidence across core systems, checks activity against typologies and flags the highest-risk cases for review. "Investigators will remain in control of every decision", and each agent conclusion links back to its source data.
  - Source: [FIS press release](https://www.fisglobal.com/about-us/media-room/press-release/2026/fis-brings-agentic-ai-to-banking-with-anthropic-starting-with-financial-crimes)
- **FIS AML Investigations Agent, commercially available to any US bank 15 Oct 2026:**
  - Amalgamated Bank is the first production deployment (Oct 2026).
  - Output is an analyst-ready case summary, with every conclusion linked to a source record. No case closes without explicit analyst confirmation.
  - Amalgamated's figures are **projections from workflow analysis, not measurements**: L1 review time down more than 90%, L2 down about 98%, SAR narrative preparation down more than 80%.
  - The article notes that no FinCEN, OCC or FFIEC guidance yet says how examiners should evaluate agent-assisted AML decisions.
  - Source: [TechTimes, 19 Oct 2026](https://www.techtimes.com/articles/329205/20261019/fis-opens-claude-powered-aml-agent-any-us-bank-cutting-investigator-data-assembly-time.htm)
- **Oracle + Lucinity:**
  - Oracle secured rights to Lucinity's investigation tech for its FCCM platform (press release 9 Apr 2026), with rollout "over the next 12 months". That makes it **announced, not deployed**.
  - Lucinity's Luci-powered Customer 360 is said to be "in production at a Tier 1 financial institution" (Jul 2025, unnamed).
  - Lucinity claims a case went from 3 h to 29 min **[MARKETING]**.
  - Sources: [Oracle press release](https://www.oracle.com/anz/news/announcement/oracle-brings-new-ai-capabilities-and-agents-to-its-financial-crime-and-compliance-portfolio-2026-04-09/); [Lucinity blog](https://lucinity.com/blog/oracle-brings-lucinitys-ai-agent-driven-capabilities-to-its-financial-crime-platform-as-lucinity-expands-into-human-ai-operations); [SecurityBrief](https://securitybrief.co.uk/story/oracle-adds-lucinity-ai-investigation-tools-for-banks)
- **Hawk AML Investigative Agent** (Mar 2026): a model-agnostic overlay. Coverage names no bank customer and gives no measured outcome. — [fintech.global, 25 Mar 2026](https://fintech.global/2026/03/25/hawks-ai-agent-automates-aml-investigations/)
- **Hummingbird:** one guide says it added a Research Agent and a Review Agent in June 2026 (platform + API), with no named bank. Secondary only. — [bankingnewsai](https://www.bankingnewsai.com/ai-agents-in-banking) (via search snippet)
- **Quantexa:** agent-ready platform relaunched Nov 2025, with domain agents "promised for 2026". No AML agent deployment with a named bank was found. — [bankingnewsai: Quantexa](https://www.bankingnewsai.com/vendors/quantexa) (via search snippet)
- **Auto-close claims:**
  - WorkFusion's Tara "auto-closes false positive alerts" that are highly unlikely to escalate.
  - Greenlite claims its agents clear "up to 95% of routine AML alerts".
  - Neither claim is independently verified **[MARKETING]**.
  - Sources: [WorkFusion blog](https://www.workfusion.com/blog/tips-to-evaluate-an-ai-agent-for-your-aml-compliance-program/); [KYC Chain, hype vs reality](https://kyc-chain.com/ai-compliance-agents-kyc-aml/)
- **Google Cloud AML AI** (risk scoring, not an LLM agent):
  - Launched June 2023. HSBC reported 2-4x more suspicious activity found and alert volume down more than 60%.
  - Other early adopters: Bradesco and Lunar.
  - No newer (2025-26) figures were found.
  - Sources: [Google Cloud press](https://www.googlecloudpresscorner.com/2023-06-21-Google-Cloud-Launches-AI-Powered-Anti-Money-Laundering-Product-for-Financial-Institutions); [HSBC on Google Cloud blog](https://cloud.google.com/blog/topics/financial-services/how-hsbc-fights-money-launderers-with-artificial-intelligence)
- **AI as QA reviewer, sold today:** Flagright markets an "AI forensics for quality assurance" agent that checks every case against the SOP step by step, flagging missed steps and unsupported conclusions. It is a vendor product, with no measured results. — [Flagright](https://www.flagright.com/ai-forensics-for-quality-assurance)
- **Managed service:** Lucinity launched "Human AI Powered FinCrime Operations" (Dec 2025), where it does triage and investigation under SLAs. — [SecurityBrief](https://securitybrief.co.uk/story/oracle-adds-lucinity-ai-investigation-tools-for-banks)

### Inferences
- The deployed pattern in 2026 is exactly GraphGuard's: the agent reads one alert, gathers evidence, writes a summary with citations to source records, and the human decides. **FIS/Amalgamated (Oct 2026) is now a named production example of "every conclusion links to its source record."** So per-claim citations alone are no longer novel at the frontier. What is still missing in public is a *measured* citation-faithfulness rate and a *deterministic* check of each claim. FIS says conclusions are linked, not verified.
- Auto-close is the line the industry has not crossed (0.5% of use at one vendor). A demo should not cross it either.

### Gaps
- No independent, post-deployment measurement of any LLM investigator (FIS's figures are projections; Unit21's are self-reported).
- No primary pages were retrieved for SymphonyAI Sensa agents, Napier's GenAI features, Sardine, Abrigo, Feedzai AML agents or WorkFusion customer outcomes. Analyst reports (Celent, Chartis, Datos) were not reachable; the only Datos figure seen is the second-hand "90-95% false positives".
- The McKinsey "Agentic AI in financial-crime prevention: lessons from winners" page timed out; it is not used.

---

## (b) Regulator stance

### Takeaway
No regulator bans GenAI or agents in AML, and the US is actively pro-technology (the FinCEN April 2026 proposal lets examiners credit AI use). But nobody has written rules for *agentic* AML decisions. The new US model-risk guidance (SR 26-2) explicitly leaves GenAI/agentic AI out of scope, FinCEN has no AI-specific SAR guidance, the FCA works through existing rules plus live testing, and in the EU AML monitoring is probably *not* AI Act high-risk (draft guidance). Everywhere, the institution stays accountable and a human signs off. That vacuum is why banks stay at "assist".

### Cited Findings
- **US model risk, SR 26-2** (Fed/OCC/FDIC, 17 Apr 2026):
  - It supersedes SR 11-7 and SR 21-8. The OCC version is Bulletin 2026-13.
  - A footnote puts generative and agentic AI **outside scope** as "novel and rapidly evolving"; broader risk management should govern them instead. A request for information on AI/GenAI/agentic AI is planned but was not found issued.
  - Sources: [Fed SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/sr2602.htm); [SR 26-2 PDF](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.pdf); [CRA analysis, Jul 2026](https://media.crai.com/wp-content/uploads/2026/07/09165122/FE-Insights-MRM-Guidance-SR-26-2-In-the-Era-of-AI-July2026.pdf); [American Banker opinion](https://www.americanbanker.com/opinion/regulators-guidance-on-model-risk-leaves-many-questions-unanswered)
- **FinCEN AML/CFT program NPRM:**
  - Issued 7 Apr 2026 and published in the Federal Register 10 Apr 2026 (91 FR 18704, docket FINCEN-2026-0034). It supersedes the July 2024 proposal; comments closed 9 Jun 2026.
  - Examiners would consider whether an institution deploys "innovative and effective compliance tools, including the use of artificial intelligence". Several firms read this as AI use counting as evidence of an effective program.
  - It is a proposal, not a final rule.
  - Sources: [govinfo FR PDF](https://www.govinfo.gov/content/pkg/FR-2026-04-10/pdf/2026-07033.pdf); [FinCEN fact sheet](https://www.fincen.gov/system/files/2026-04/Program-NPRM-FactSheet.pdf); [WilmerHale](https://www.wilmerhale.com/en/insights/client-alerts/20260413-fincen-issues-proposed-rule-revising-the-aml-program-requirements-for-financial-institutions); [Jones Day](https://www.jonesday.com/en/insights/2026/05/modernizing-amlcft-fincen-proposes-fundamental-reforms-to-program-requirements)
- **FinCEN on AI-drafted SARs:**
  - One source says that as of 24 Sep 2026 FinCEN had issued no guidance on AI-prepared SARs, and its filing instructions and Oct 2025 SAR FAQs do not mention AI. The same narrative standard (clear, complete, concise; who/what/when/where/why/how) applies whoever drafts it, and the bank is accountable.
  - These are vendor and secondary blogs; the claim is unverified against FinCEN's site.
  - Sources: [Zyphe](https://www.zyphe.com/resources/blog/can-ai-draft-sar-narratives-2026); [Oscilar](https://oscilar.com/blog/sar-narrative-automation); [Fivenines](https://blog.fivenines.com/ai-drafted-sar-vs-analyst-drafted-sar-regulatory-exposure-compared-under-fincen-guidance)
- **FCA (UK):**
  - "AI in financial services: good practice and areas for improvement" (19 Oct 2026) creates no new requirements; existing rules apply. Law firms note that fraud/financial-crime models sit within governance that "will need to evolve".
  - Speech the same day (Jessica Rusu): the FCA is building AI tools to supervise about 60,000 AML firms entering its remit in 2028. Governance should define when staff must intervene and keep human control where needed. An agentic framework (agent identity, delegated authority, accountability) is not yet final.
  - One secondary source says eight firms are live-testing agentic applications including AML/KYC, with evaluation in Q1 2027 (not verified against the FCA).
  - Sources: [Fincrime Central, 20 Oct 2026](https://fincrimecentral.com/fca-ai-aml-supervision-agentic-finance-2028/); [Clifford Chance](https://www.cliffordchance.com/insights/resources/blogs/regulatory-investigations-financial-crime-insights/2026/10/fca-sets-out-good-and-poor-practice-for-firms-using-ai.html); [Freshfields](https://www.freshfields.com/en/our-thinking/briefings/2026/10/ai-in-financial-services-fca-good-and-poor-practice-and-the-road-to-agentic-finance); [FinanceX, Jul 2026](https://www.financexmagazine.com/post/amla-drops-its-first-real-playbook-as-agentic-ai-eats-the-compliance-stack-2)
- **EU AI Act:**
  - The majority view is that bank AML transaction monitoring is **not** an Annex III high-risk category. Draft Commission guidelines (19 May 2026, consultation to 23 Jun 2026, not adopted) reportedly confirm that an obliged entity doing its own AML is not acting for law enforcement (point 6). Point 5(b) excludes financial-fraud detection from the credit high-risk category.
  - Some vendor blogs and Kroll say the opposite, so the sources **conflict**.
  - The Annex III deadline was reportedly moved to 2 Dec 2027 (attributed to the "Digital Omnibus"; not verified against the Official Journal).
  - Sources: [TrustSphere](https://www.trustsphere.ai/post/the-eu-ai-act-s-high-risk-deadline-for-financial-crime-systems-has-moved-and-the-scope-is-narrower); [Unit21 EU AI Act FAQ](https://www.unit21.ai/blog/eu-ai-act-2026-faqs-what-fraud-and-aml-teams-need-to-know); contra [Kroll](https://www.kroll.com/en/publications/financial-compliance-regulation/fca-expectations-governance-skills)
- **AMLA:** direct supervision starts in 2028. One source says it had to submit 23 technical standards/guidelines by 10 Jul 2026. No AMLA text on AI or agents was found. — [FinanceX](https://www.financexmagazine.com/post/amla-drops-its-first-real-playbook-as-agentic-ai-eats-the-compliance-stack-2); [Liminal](https://liminal.co/articles/insights/the-state-of-aml-compliance-in-2026/)
- **Auto-closing:** commentary says no cited regulator prohibits it, but the bank is accountable for every closure, and fully autonomous closure of complex AML alerts "remains unusual". A Valley Bank sanctions-alert case (2025) is described only second-hand. — [Medium, auto-closure legality](https://medium.com/@georgekar91/auto-closures-of-kyc-aml-screening-false-positives-is-it-legally-permissible-5d4d729da5db); [KYC Chain](https://kyc-chain.com/ai-compliance-agents-kyc-aml/)

### Inferences
- Banks stay at "assist" not because AI is banned, but because (1) SR 26-2 left agentic AI with no validation template, (2) no examiner guidance exists on agent-assisted decisions, and (3) the bank owns every closure and every SAR word. Anything that makes an agent's output **mechanically auditable** directly answers the open question regulators have left.
- A public demo should say: "draft only; a person decides; nothing is auto-closed; nothing is filed."

### Gaps
- FATF: no 2025-26 FATF publication on GenAI or agents was found (search did not surface one).
- The text of the FCA's financial-crime section in the Oct 2026 paper was not retrieved.
- The adopted (final) EU AI Act high-risk guidelines were not found; only the May 2026 draft as described by blogs.
- MAS: covered in the earlier note.

---

## (c) Evidence on accuracy and error rates

### Takeaway
There is still **no public benchmark or audited error rate for AI-written AML narratives or SARs.** The best numbers are vendor agreement rates (Unit21: 95-99% agreement with humans on dispositions) and projections. General hallucination benchmarks put per-claim error in the low single digits for frontier models on grounded tasks, which matches GraphGuard's measured 4-6% raw unsupported claims.

### Cited Findings
- Unit21's 95% (TM) and 99% (sanctions) are *agreement* with human reviewers. That is not the same as a narrative-faithfulness rate, and no error rates are disclosed. — [Unit21](https://www.unit21.ai/blog/what-1m-live-ai-alerts-tell-us-about-ai-in-fincrime)
- FIS/Amalgamated time savings are projections, not measured. — [TechTimes](https://www.techtimes.com/articles/329205/20261019/fis-opens-claude-powered-aml-agent-any-us-bank-cutting-investigator-data-assembly-time.htm)
- A search for an LLM SAR-narrative hallucination benchmark found none. The nearest analogues are general benchmarks:
  - A 2026 re-evaluation of package hallucination found per-model rates of about 3.6-5.0% across the 2026 frontier cohort.
  - HalluLens covers summarisation faithfulness.
  - Sources: [arXiv 2605.17062](https://arxiv.org/pdf/2605.17062); [HalluLens arXiv 2504.17550](https://arxiv.org/pdf/2504.17550)
- A 2026 LLMOps paper for fraud/AML describes an LLM-as-judge release gate (golden references, expert calibration, multi-judge scoring). Seen as a search snippet only. — [arXiv 2605.11232](https://arxiv.org/html/2605.11232v1)
- A vendor (Botminds) markets the principle "a SAR narrative generator should never check its own work", meaning an independent checker. **[MARKETING]** — [Botminds](https://www.botminds.ai/solutions/sar-narrative-and-filing/sar-narrative-generator)
- A practitioner essay warns that LLM compliance rationales cite clauses not in the source, or paraphrase too loosely to trace. — [HackerNoon](https://hackernoon.com/what-happens-when-the-model-reads-it-wrong-building-llm-compliance-review-that-survives-an-audit)

### Inferences
- GraphGuard's measured 4-6% raw unsupported claims, reduced to 0 shown by a deterministic checker, is **more evidence than any vendor publishes**. Its credibility depends on publishing the denominator, the checker's rules, Wilson CIs, and what the checker *cannot* catch (true-but-misleading claims, omissions). That boundary is the honest caveat.
- "0 shown after the checker" must be worded as "0 claims that failed a data check were shown", not "0 errors". The checker verifies support, not judgement.

### Gaps
- No judge-human agreement numbers for AML narratives were found anywhere.
- No regulator or auditor publication was found that measured AI investigation error rates.

---

## (d) Innovation candidates: what banks do not do yet, ranked for a public demo

### Takeaway
The most credible and safe "innovation" to demo is **a fully verified SAR-style draft where every sentence is a checked claim, with a public, re-runnable accuracy scorecard** (candidates 1+2 merged). Production vendors (FIS) link conclusions to records, but none publishes per-claim deterministic verification or an error rate. The second-best, and the most novel UX, is an **AI second reviewer (four-eyes) that challenges a human's verdict using only checked facts**. It is precomputable, fits the $10 cap, and is something banks do with human QA today but not with AI on live decisions. Live natural-language SQL and live MCP on a public site are the riskiest and should stay offline or sandboxed.

### Cited Findings (what each candidate is grounded on)
- Linked citations in production: FIS/Amalgamated. — [TechTimes](https://www.techtimes.com/articles/329205/20261019/fis-opens-claude-powered-aml-agent-any-us-bank-cutting-investigator-data-assembly-time.htm)
- AI QA against an SOP, sold by a vendor but unmeasured. — [Flagright](https://www.flagright.com/ai-forensics-for-quality-assurance)
- Narrative-vs-data consistency is patented as a separate step (USPTO 12536544, in the earlier note); "never check its own work". — [Botminds](https://www.botminds.ai/solutions/sar-narrative-and-filing/sar-narrative-generator)
- Auto-close is barely used (0.5%). — [Unit21](https://www.unit21.ai/blog/what-1m-live-ai-alerts-tell-us-about-ai-in-fincrime)
- MCP/public-tool risks:
  - OWASP's MCP Top 10 lists tool poisoning (MCP03), prompt injection via contextual payloads (MCP06) and insufficient auth (MCP07).
  - Prompt injection remains #1 in the OWASP LLM Top 10. OWASP advises assuming that instruction boundaries will be bypassed and constraining actions and outputs.
  - More than 30 MCP CVEs were reported in Jan-Feb 2026 (vendor count).
  - Sources: [OWASP MCP Top 10](https://owasp.org/www-project-mcp-top-10/); [SC World](https://scworld.com/brief/prompt-injection-remains-top-llm-threat-owasp-report-finds); [dev.to MCP security 2026](https://dev.to/luckypipewrench/the-state-of-mcp-security-2026-incidents-attack-patterns-and-defense-coverage-2h45)

### Inferences — ranked candidates
Each candidate is scored on N (novelty vs bank practice), S (safety on a public site), A (demo appeal) and C (cost under the $10 OpenRouter cap). The scores are my judgement, based on the findings above.

1. **Verified SAR-style draft + public accuracy scorecard** (merge "verified-claim narratives" and "auto SAR draft with every fact checked"). N: medium-high (banks link, nobody publishes deterministic per-claim checks or rates). S: high (precomputed, read-only, synthetic). A: high (hover a sentence → see payment ids → see the check pass; a toggle to show the dropped claims, in red, with why). C: about zero at view time. **Recommended headline.** Make it SAR-shaped (who/what/when/where/why/how sections, each made only of checked claims) and label it "draft — not filed, a person decides". Banks do not do this yet because narrative tools are sold on speed, not on verification, and SR 26-2 gives no validation template for GenAI, so nobody publishes an error rate that would become a standard they could be examined against.
2. **AI second reviewer (four-eyes by AI).** After the visitor (or a stored analyst verdict) decides, a precomputed "challenger" lists the checked facts that argue *against* that verdict, never the answer key. N: high (QA today is human sampling after the fact; AI QA products check SOP steps, not the decision itself, and nothing measured was found). S: high if precomputed for both verdicts per alert (128 × 2). A: high and interactive. C: low (256 precomputed runs). Banks avoid it live because of automation-bias and accountability questions (MAS names automation bias), so it fits a demo as "the AI argues, the human decides". Measure it: how often the challenger's points are all checker-supported, and whether it flags the known-truth disagreements.
3. **Step-by-step ring storytelling.** The checked claims played in time order over the existing as-of subgraph. N: medium. S: high. A: very high for non-experts (it fits the S7.11 real-person test). C: about zero (built from existing checked claims; can be deterministic). Low risk, but more UX than "AI frontier".
4. **Counterfactual "what would make this alert go away".** Use SHAP/the tree to find the smallest feature change that drops the alert below the line, then the LLM phrases it, checked. N: medium (common in credit, rare in AML UIs). S: medium: on a public site it reads as an evasion guide ("send fewer than N payments") and needs framing or coarse banding. A: medium. C: low. Banks avoid it for exactly that tipping-off/evasion reason.
5. **AI explains the model to a manager** (capacity slider + precision@k in words). N: low-medium. S: high. A: medium. C: about zero if precomputed. Useful, not frontier.
6. **Agent-run lookback.** Re-investigate past alerts after a model change and list newly suspicious cases. N: medium-high (lookbacks are expensive consultant projects). S: high offline. A: medium (a batch report). C: medium; run it once offline within budget. Leakage: it must respect `labels.known_as_of` and the sealed window.
7. **Natural-language questions over the queue → safe SQL.** N: medium (copilots like Q Assist claim it). S: **low live**: prompt injection, cost abuse, data exfiltration and SQL validation all apply. If shown, use a fixed menu of precomputed questions, or compile to a whitelisted query DSL, not raw SQL. A: high. C: per-query spend that can be abused.
8. **Live MCP access for external agents.** N: high-ish for AML. S: **lowest**: OWASP MCP06/MCP07, a public endpoint is a cost and abuse target. Keep it as a documented local/stdio server plus a recorded demo video, not a public endpoint.

### Public-demo safety (inference, grounded on the OWASP items above)
- **Precompute everything shown by default**: reports, challenger runs, stories. There is no live model call on page load. That gives zero injection surface from visitors and zero cost per view.
- If one live feature is added, make it a **fixed, server-side allow-list** (pick an alert + pick one of N questions), so the visitor never sends free text to the model:
  - per-IP and global rate limits;
  - a hard daily dollar cap enforced server-side (the existing `llm.SPEND_CAP` pattern), plus the OpenRouter console limit as a second wall;
  - a cache keyed on (alert, question, model, prompt version);
  - a kill switch.
- Tool outputs are data, not instructions. AMLworld fields are synthetic and fixed, so indirect injection through data is low risk. Still render model text as plain text, never HTML.
- Never expose the answer key (`truth`) to any tool (already a rule). Keep the model's tools read-only and bound to one alert.

### Gaps
- OpenRouter prices for "DeepSeek V4.1 Flash" and "Claude Sonnet 5.5" were not looked up in this session. Compute the cost of 256 precomputed challenger runs from the agent's measured tokens per run before committing.
- No published measurement of an AI second reviewer catching analyst errors was found. The demo's own measurement would be first-of-kind but small-sample, and should be labelled as such.
- Whether any bank uses counterfactual explanations for AML alerts internally is unknown (none found).
