# Alert explanations and LLM investigator agents for AML (as of 22 Nov 2026)

Scope: per-alert explanations for an XGBoost AML model (graph + tabular features, six rules alongside) in an investigator UI, and whether/how to build an LLM "investigator agent" with a measured error rate. Research was done 2026-11-22 with about 18 search/fetch calls. Vendor numbers are marked **[MARKETING]**. Dates are given where known.

---

## 1. SHAP for XGBoost in production: exactness, speed, decision-time vs on-demand, pitfalls

### Takeaway
XGBoost's built-in `predict(pred_contribs=True)` gives exact TreeSHAP values on CPU or GPU. The values are path-dependent and in **margin (log-odds) space**, with one extra bias/base column, so they sum exactly to the raw score. It is cheap enough to compute at decision time and store next to each score. The main pitfalls are which baseline is used (path-dependent vs interventional), log-odds vs probability, and credit being split across correlated features.

### Cited Findings
- XGBoost's `pred_contribs` output has shape `(rows, groups, columns + 1)`; the "+1" is the bias column. `pred_interactions` returns `(rows, groups, columns+1, columns+1)`. — [XGBoost docs: Prediction](https://xgboost.readthedocs.io/en/stable/prediction.html)
- With `approx_contribs=False`, XGBoost uses **QuadratureTreeSHAP** for exact attributions "on both CPU and GPU". `approx_contribs=True` is an approximate method that runs on CPU only, and "the GPU predictor does not implement approximated contributions". — [XGBoost docs: Prediction](https://xgboost.readthedocs.io/en/stable/prediction.html)
- For path-dependent SHAP on XGBoost, `shap.TreeExplainer` calls XGBoost's own implementation behind the scenes, and `pred_contribs=True` returns (path-dependent) Shapley values. This comes from a 2026 arXiv paper; I did not confirm it in the XGBoost docs. — [arXiv 2605.04497](https://arxiv.org/html/2605.04497v1)
- shap `TreeExplainer`, `feature_perturbation`:
  - `"interventional"` needs a background dataset; "runtime scales linearly with the size of the background dataset"; 100–1000 random background samples suggested.
  - `"tree_path_dependent"` needs no background; it uses the training-sample counts at each leaf as the background.
  - `"auto"` (the default since 0.47) picks interventional when background data is given, otherwise path-dependent.
  - Source: [shap TreeExplainer docs](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html)
- `model_output="raw"` (the default) explains log-odds for XGBoost binary classification. `"probability"` and `"log_loss"` are **only supported with interventional** perturbation. `expected_value` + SHAP values = model output. `check_additivity` checks this, but only when explaining the margin. `approximate=True` is the Saabas method: fast, but it lacks Shapley consistency guarantees and overweights lower splits. — [shap TreeExplainer docs](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html)
- Path-dependent TreeSHAP is meant to estimate *conditional* Shapley values, but its approximation of conditional expectations is imperfect. Interventional TreeSHAP estimates *marginal* Shapley values and depends only on the model's input–output function. — [Filom et al., "On marginal feature attributions of tree-based models", arXiv 2302.08434](https://arxiv.org/pdf/2302.08434)
- A 2026 taxonomy/reporting-checklist paper on local additive attributions exists. It argues that reports should state the value function, the baseline and the output space. I only saw the title/snippet. — [arXiv 2607.14271](https://arxiv.org/pdf/2607.14271)
- How vendors show contributions: no primary vendor UI documentation was retrieved. The Wolfsberg Group (Aug 2025) says investigators should see "the features that influence the model output, the risk associated to those features, and/or the relevant risk indicators triggering behind those features", and FIs "should consider displaying such information through visualisation tools". — [Wolfsberg Statement on Effective Monitoring Part II (Aug 2025)](https://financialcrime.lu/assets/pdfs/articles/2025/08/20250827%20EN%20Statement%20on%20Effective%20Monitoring%20for%20Suspicious%20Activity%20%C2%A6%20Part%20II%20-%20Transitioning%20to%20Innovation_%5BMD5_F987A8AB6D2B85A2FACE6FDE74F704CD%5D.pdf)

### Inferences
- For GraphGuard: compute `pred_contribs` **in the consumer at decision time** (the model is already in process, per S6.6). Store the top-k (feature, value, contribution) entries plus the bias and the raw margin in the decision row. That makes the explanation reproducible, tied to the exact model version and feature vector, and free to read at UI time. It also fits the existing "decisions + offset + outbox in one transaction" design. Recomputing on demand later would need the exact as-of feature vector, which the decision row already has, so storing is cheap. A cost check against the 10 ms in-process budget is needed (see Gaps).
- Show contributions in **log-odds units** ("pushes the score up/down"), not as percentages of probability. Probability-space SHAP needs interventional mode plus a background set, which is slower and adds a design choice that has to be defended. A simple UI choice: rank by absolute log-odds contribution and show the direction with a sign or colour.
- Correlated features (for example, 24 h send count vs degree as-of time vs distinct counterparties) will split credit. Grouping related features into "reason families" before display (summing their SHAP values, which is valid because SHAP is additive) avoids misleading single-feature rankings.
- Write down which variant is used (path-dependent, raw margin, base value = `expected_value` / bias column). This is the kind of detail a senior reviewer checks.

### Gaps
- **ms per row** for TreeSHAP on our production-sized model: no reliable published benchmark was found. Cost scales with trees x leaves x depth² (Lundberg et al. 2020, *Nature Machine Intelligence*, "From local explanations to global understanding with explainable AI for trees", arXiv 1905.04610; complexity recalled from that paper, page not fetched this session). **Measure it locally** in the latency test (`tests/serving/test_latency_budget.py`), with and without contributions.
- No primary vendor screenshots/docs were retrieved showing how Lucinity, Hawk, Feedzai etc. render feature contributions.

---

## 2. Turning contributions into plain-language reason codes, plus graph evidence

### Takeaway
Credit-scoring practice is the closest mature model. Under US Reg B/ECOA, a model's output must come with **specific principal reasons**, and that applies to complex ML models too. Under FCRA, up to **four** key factors are disclosed (five if inquiries are a factor). For AML, the Wolfsberg Group asks for features → risk indicators → typologies, shown visually. A top-3/top-4 reason list from a maintained feature → reason template table, plus the subgraph, follows both.

### Cited Findings
- CFPB Circular 2022-03 (26 May 2022): Reg B requires that a statement of reasons "must be specific and indicate the principal reason(s) for the adverse action". "Creditors who use complex algorithms, including artificial intelligence or machine learning, in any aspect of their credit decisions must still provide a notice". It warns about "uninterpretable or 'black-box' models" that make it hard to identify specific reasons. — [CFPB Circular 2022-03](https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-based-on-complex-algorithms/)
- Reg B commentary (12 CFR 1002 Supp. I, 9(b)(2)-9), as quoted on the CFPB circular page: the FCRA requires disclosure of "up to four key factors that adversely affected the consumer's credit score" (five if inquiries are a key factor). That disclosure "does not satisfy the ECOA requirement to disclose specific reasons". — [CFPB Circular 2022-03](https://www.consumerfinance.gov/compliance/circulars/circular-2022-03-adverse-action-notification-requirements-in-connection-with-credit-decisions-based-on-complex-algorithms/)
- CFPB Circular 2023-03 (19 Sep 2023) dealt with the proper use of the Reg B sample forms (checklists) for adverse-action reasons. The page is now marked **archived**, and the body text was not retrievable. — [CFPB Circular 2023-03](https://www.consumerfinance.gov/compliance/circulars/circular-2023-03-adverse-action-notification-requirements-and-the-proper-use-of-the-cfpbs-sample-forms-provided-in-regulation-b/)
- Wolfsberg (Aug 2025), on mapping features to risk: "In machine learning, typologies are mapped to data features which are fed into models", so that FIs keep "a mapping inventory that consists of risk indicators or typologies and their relevant features". Model output analysis should involve "correlating feature importance back to typologies". — [Wolfsberg Part II](https://financialcrime.lu/assets/pdfs/articles/2025/08/20250827%20EN%20Statement%20on%20Effective%20Monitoring%20for%20Suspicious%20Activity%20%C2%A6%20Part%20II%20-%20Transitioning%20to%20Innovation_%5BMD5_F987A8AB6D2B85A2FACE6FDE74F704CD%5D.pdf)
- Wolfsberg (Aug 2025), on why: "When the outputs of models are sent for investigation, there is always a need to explain why an alert was generated in the first place." Under rules, "the catalyst for the alert is clear to the analyst but also blunt"; in ML programmes "a confluence of factors" prompts the alert. — [Wolfsberg Part II](https://financialcrime.lu/assets/pdfs/articles/2025/08/20250827%20EN%20Statement%20on%20Effective%20Monitoring%20for%20Suspicious%20Activity%20%C2%A6%20Part%20II%20-%20Transitioning%20to%20Innovation_%5BMD5_F987A8AB6D2B85A2FACE6FDE74F704CD%5D.pdf)
- Grounding narratives in attributions (research): SCAFDS (arXiv 2605.18913) ties each SAR assertion to a SHAP attribution value and suppresses assertions without sufficient attribution support, to address an "auditability gap" in LLM-SAR systems. This is a preprint, seen as a snippet only. — [arXiv 2605.18913](https://arxiv.org/pdf/2605.18913)

### Inferences
- Suggested design (an inference, not a sourced standard):
  1. A static table `reason_templates` keyed by feature (or feature family), giving a typology tag plus a sentence template with slots. Example: `sends_24h` → "Sent {value} payments in the last 24 h (typical for accounts like this: {p50})".
  2. At display time, take the top 3 positive contributions (four is the FCRA ceiling and a sensible upper bound) and fill the templates with the **as-of feature values stored in the decision row**.
  3. Show rule hits separately and verbatim ("Rule R3: fan-out ≥ N in 24 h"), because rules explain themselves.
  4. Show the as-of subgraph: 1–2 hops around sender/receiver, built only from edges before the decision time. The leakage contract applies to the UI as well, since showing future edges would be a leakage-in-the-UI bug.
- This is all deterministic: no LLM is needed for reason codes. That gives a clean baseline to test any LLM summary against.
- A reason should not be shown if its contribution is negative or tiny. Pick a threshold (for example, |contrib| below some fraction of the margin) and test it.

### Gaps
- No AML-specific regulatory standard for the *number* or *format* of reason codes was found. The four-factor rule is credit-scoring (FCRA) practice, borrowed by analogy.
- No primary vendor documentation on reason-code templates in AML products was retrieved.

---

## 3. LLM assistants in AML/fraud investigation (2025–2026): products, tasks, evidence

### Takeaway
Every major vendor now ships an "investigation agent" that gathers evidence, summarises the alert, recommends a disposition and drafts a SAR narrative, with a human approving. **None of the time-savings or accuracy claims found are independently measured.** They are vendor-reported, and denominators and methods are rarely disclosed. The only peer-reviewed-style evidence found is weak (Co-Investigator AI: 6 raters, LLM judge, no hallucination rate).

### Cited Findings
- **Lucinity (Luci):** gathers evidence and writes editable SAR/case narratives, and reportedly does not make decisions. Lucinity claims investigation time drops "from hours to minutes" **[MARKETING]**. Oracle integrated Lucinity's agent-driven investigation technology into its financial crime platform in April 2026 (secondary sources). — [Corsa comparison, 2026](https://corsa.finance/compare/best-ai-tools-aml-alert-triage-sar-drafting); [MightyBot comparison, Nov 2026](https://mightybot.ai/compare/best-aml-investigation-software/); [Startup Stash, 2026](https://startupstash.com/best-agentic-aml-platforms/)
- **Unit21:** separate Alert, Case and SAR agents. They pull transaction histories, assemble evidence, recommend a disposition and draft a narrative in the customer's format. Unit21 says human review and approval before filing is mandatory by design. — [Sphinx: Unit21 alternatives](https://sphinxhq.com/blog-posts/unit21-alternatives); [Corsa: Unit21 alternatives](https://corsa.finance/compare/unit21-alternatives)
- **Hawk:** "AML Investigative Agent" launched March 2026 as a model-agnostic overlay that drafts SAR narratives for analyst review. Sources disagree on whether it documents narrative drafting, and one comparison could not read Hawk's pages. — [Startup Stash](https://startupstash.com/best-agentic-aml-platforms/); [Hawk: Agentic AI guide](https://insights.hawk.ai/agentic-ai-a-practical-guide-for-fcc-leaders)
- **Quantexa:** 75% false-positive reduction and 80% less investigation time, attributed to HSBC/Standard Chartered case studies. These come via secondary sites, and the method is not disclosed **[MARKETING]**. Q Assist is described only as an embedded copilot, with no metric found. — [Beri.net, 2026](https://www.beri.net/article/best-ai-aml-transaction-monitoring-software-2026); [FluxForce comparison](https://www.fluxforce.ai/alternatives/fluxforce-alternative-to-actimize-and-quantexa)
- **Napier AI:** claims more than 90% false-positive reduction (Banco do Brasil case study, per a review) and one live case where alert volume fell from 12% to 2% of screened records. These are screening results, not LLM investigation **[MARKETING]**. — [Napier: Client screening](https://www.napier.ai/client-screening)
- **Feedzai (12 Nov 2026):** release claims 44% more fraud detected in the top 0.1% riskiest sessions and 41% fewer OTPs. These are fraud/login results, not AML investigation, with no test period or sample size disclosed **[MARKETING]**. — [FinanceFeeds](https://financefeeds.com/feedzai-adds-ai-agent-detection-as-banks-reassess-trust-after-login/); [PR Newswire](https://www.prnewswire.com/in/news-releases/your-next-bank-customer-might-not-be-human-feedzai-helps-banks-spot-ai-agents-at-the-front-door-302937160.html)
- **WorkFusion, Sardine, Flagright:** no quantified claims or task descriptions were retrieved in this session (see Gaps).
- **Co-Investigator AI (arXiv 2509.08380, 10 Sep 2025):** an agentic SAR-narrative framework, evaluated by 6 investigators at "a leading global fintech company" on a 1–5 scale.
  - Narrative completeness 3.52/5 (70%); "Efficiency Gains" 3.06/5 (61%). The 61% is a **rating, not a measured time saving**, though the conclusion calls it "saving investigators significant time (around 61%)".
  - The evaluation LLM was Gemini 2.5 Pro, plus an "Agent-as-a-Judge" validator, with **no judge–human agreement reported**.
  - No hallucination rate is reported for the system. The paper says direct prompting "invented details such as fabricated interactions" and cites general LLM hallucination rates of "20–30%" from another source.
  - Its FinCEN baseline is 25–315 minutes per SAR.
  - Source: [arXiv 2509.08380](https://arxiv.org/html/2509.08380v1)
- **AMLBench (arXiv 2611.02530, 2 Nov 2026; Monash, CSIRO, NTU):** 24 real Ethereum laundering cases, 5.05 M transfer records. Agents start from limited clues and use query tools; results are scored against case annotations, and **tool logs are scored as the process**.
  - With "GPT-6 Astra", their AMLAgent reaches 80.82% macro transfer-level precision and 84.73% query coverage. Median F1 is 75.48%, with median precision 95.10% and recall 65.64%.
  - On the three largest cases (>48,000 target transfers), recall stays under 2%, because the agent stops after fetching under 2.5% of targets.
  - In two cases recall is 100% / 94% but precision only 15% / 7.6%.
  - Source: [arXiv 2611.02530](https://arxiv.org/pdf/2611.02530)
- **Pirmorad (arXiv 2507.14785, Jul/Oct 2025):** an exploratory study of LLM in-context learning for money-laundering detection on synthetic financial graphs. It is not a benchmark. — [arXiv 2507.14785](https://arxiv.org/abs/2507.14785v2)
- **"Agentic AI for Financial Crime Compliance" (arXiv 2509.13137, 2025):** exists. Only the title was seen. — [arXiv 2509.13137](https://arxiv.org/pdf/2509.13137)

### Inferences
- The common task split across vendors is (1) data gathering, (2) alert summary, (3) disposition *recommendation*, (4) narrative draft, with (5) the human decides and files. A portfolio project can copy this split and **measure each task separately**, which no vendor publishes.
- The credible evidence bar is low. A small project with a public eval set, a stated hallucination rate with confidence intervals, and judge–human agreement would already exceed what the vendors and the Co-Investigator paper publish. That is the differentiator.
- AMLBench's design (score the outcome against annotations **and** score the tool-call process) carries over directly. AMLworld has ground-truth laundering labels and pattern membership, so an agent's claims ("account X is part of a fan-out ring") can be checked mechanically. One caution is the synthetic data, and another is that labels must be gated by `labels.known_as_of(t)` so the agent cannot see future labels.

### Gaps
- No independent (non-vendor, non-author) measurement of time savings or error rates for any commercial AML LLM assistant was found.
- No primary pages were retrieved for WorkFusion, Sardine, Flagright or Quantexa Q Assist. Hawk's details are the least verified.

---

## 4. How to measure an LLM investigator's accuracy

### Takeaway
Measure **claim-level faithfulness** against the source records: split each output into atomic claims, require a record citation for every claim, and verify each claim mechanically against the database where possible. Add a labelled eval set, human review of a sample to calibrate any LLM judge, and an explicit "insufficient evidence" abstention path. Report the error rate with confidence intervals.

### Cited Findings
- Co-Investigator AI is a counter-example worth citing. It used an LLM judge (Gemini 2.5 Pro) and an "Agent-as-a-Judge" validator, but reported **no agreement rate with humans and no judge-bias analysis**. Its 6-rater 1–5 scores conflate completeness with time saved. — [arXiv 2509.08380](https://arxiv.org/html/2509.08380v1)
- AMLBench is the positive pattern: outcome metrics (transfer- and address-level precision/recall/F1 against annotations) plus process metrics from tool logs (query coverage, retention, token cost). It also shows that high recall can come with very low precision (7.6%), so both must be reported. — [arXiv 2611.02530](https://arxiv.org/pdf/2611.02530)
- Attribution-gated generation: SCAFDS suppresses any SAR assertion without sufficient SHAP attribution support. That is a structural guard against unsupported claims. — [arXiv 2605.18913](https://arxiv.org/pdf/2605.18913)
- A USPTO patent filing covers automated validation of SAR narratives with generative AI, flagging mismatches or gaps between the narrative and the underlying details. This shows the industry treats "narrative vs data" consistency checking as its own step. — [USPTO 12536544](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12536544)
- General hallucination taxonomies and metrics are surveyed in Huang et al. (arXiv 2309.01219). — [arXiv 2309.01219](https://arxiv.org/pdf/2309.01219)
- MAS (Oct 2026) lists automation bias, decision fatigue and skill degradation from over-reliance on GenAI as human-factor risks. Measuring whether reviewers actually catch planted errors is therefore part of "accuracy". — [MAS Guidelines on AI Risk Management, 7 Oct 2026](https://www.mas.gov.sg/-/media/mas-media-library/regulation/guidelines/bd/guidelines-on-artificial-intelligence-risk-management-for-financial-institutions/guidelines-on-artificial-intelligence-risk-management.pdf)

### Inferences
Proposed measurement design for GraphGuard. This is an inference and should go through Phase 7 stories and an ADR.
1. **Constrain the output.** The agent returns structured claims, each with `{text, kind, cited_record_ids}`, where kind is one of amount / count / counterparty / time / pattern / reason. Free text is only rendered from those claims.
2. **Mechanical verification first.** Every numeric or relational claim is re-checked in SQL against the cited records: amount, timestamp, counterparty, 24 h count, and degree as-of the decision. A claim is wrong if it is uncited, cites a non-existent or out-of-window record, or the value does not match. This gives a **hallucination rate with no judge involved**.
3. **LLM judge only for what SQL cannot check** (for example "is this summary misleading?"). Calibrate it against a human-labelled sample and report Cohen's kappa or agreement. Do not use the same model family as judge and generator.
4. **Eval set from validation-window alerts only** (test window sealed), stratified by: true positive / false positive / rule-only / cold-start (`review: both accounts new`). Include **adversarial cases**: alerts where the honest answer is "insufficient evidence", and records with planted conflicting values. The correct behaviour there is to abstain, and abstention rate and correctness are reported.
5. **Report**: claim-level error rate with Wilson 95% CI, abstention precision, disposition-recommendation agreement with labels (keeping FINDING-017's champion-biased labels in mind), latency and cost per alert, and **a baseline**: the deterministic reason-code template from section 2. If the LLM is not better than the templates on a defined metric, that is a finding to publish, in the same spirit as the GNN result.
6. **Human-in-the-loop measure**: plant known errors in a sample of drafts and measure whether the reviewer catches them (automation bias). This can be a small self-study.

### Gaps
- No public AML-specific benchmark for **SAR/alert narrative faithfulness** was found. AMLBench covers crypto fund tracing, not alert narratives.
- No published judge–human agreement numbers for AML narratives were found.
- The "20–30% hallucination rate" quoted in Co-Investigator AI is second-hand. Its original source was not checked, and it should not be quoted as an AML-specific figure.

---

## 5. Regulator stance on generative AI in AML

### Takeaway
No regulator found bans GenAI in AML. Industry bodies (Wolfsberg) actively suggest LLM-generated "investigator-ready summaries", and FinCEN's April 2026 proposal names GenAI as technology to evaluate. The consistent expectations are: explainability of why an alert fired, meaningful human oversight proportionate to risk, guarding against automation bias, and documented validation. No source found requires a human to approve each SAR as a *specific GenAI rule*, but every vendor builds that in.

### Cited Findings
- **Wolfsberg Group (27 Aug 2025), Statement on Effective Monitoring for Suspicious Activity, Part II:**
  - It recommends a hybrid of rules + supervised + unsupervised methods.
  - Explainability is framed through three lenses: risk coverage; model design/development/calibration; model usage.
  - It explicitly says "by leveraging advanced technologies such as large language models (LLMs), FIs can surface the most predictive features and contextual signals behind alerts. These models can generate investigator-ready summaries that clarify the underlying risk and suggest next-best investigative actions."
  - It asks for continuous validation and SME rating of alert-quality samples, and cautions against one-size-fits-all model risk management.
  - Source: [Wolfsberg Part II PDF](https://financialcrime.lu/assets/pdfs/articles/2025/08/20250827%20EN%20Statement%20on%20Effective%20Monitoring%20for%20Suspicious%20Activity%20%C2%A6%20Part%20II%20-%20Transitioning%20to%20Innovation_%5BMD5_F987A8AB6D2B85A2FACE6FDE74F704CD%5D.pdf); [coverage, fintech.global](https://fintech.global/2025/09/01/wolfsberg-calls-for-responsible-ai-use-in-financial-crime-checks/)
- **FinCEN (proposed AML/CFT program rule, 10 Apr 2026, cited as 91 FR 18704 by secondary sources):**
  - It encourages institutions to evaluate new technology, naming machine learning and generative AI among the examples. Per one secondary tracker, "effective use of artificial intelligence" with demonstrable outputs would count in a bank's favour.
  - Interagency model risk guidance (Apr 2026) reportedly places generative/agentic AI **outside** its scope.
  - All of this is secondary; the Federal Register text was **not** fetched.
  - Sources: [FluxForce: FinCEN 2026 priorities](https://www.fluxforce.ai/blog/fincens-2026-priorities-what-compliance-teams-need-to-know-now-1); [Oscilar: AI in AML programs](https://oscilar.com/blog/ai-aml-programs)
- **FinCEN and human-in-the-loop:** no primary FinCEN text mandating human review of AI output was found. Claims that FinCEN makes per-SAR human review "binding" (theneuralbase.com) are **unverified** and conflict with the rest. — [theneuralbase (unverified)](https://theneuralbase.com/ai-for-government/learn/intermediate/financial-crimes-fincen/); [Abrigo on HITL (vendor)](https://www.abrigo.com/blog/human-in-the-loop-aml-software/)
- **MAS (Singapore), Guidelines on AI Risk Management, final 7 Oct 2026** (consultation from 13 Nov 2025):
  - Human oversight should enable "meaningful human intervention", with clear roles, the capability to intervene and documented review, addressing automation bias and decision fatigue. It should be proportionate to the risk materiality of the use case.
  - It names poor oversight of GenAI in mission-critical areas and over-reliance on GenAI as risks, and covers AI agents.
  - The consultation notes that AI for fraud/AML/CFT "may miss suspicious patterns or generate inconsistent detection outcomes".
  - An AI Risk Management Toolkit / Operationalisation Handbook followed in March 2026. One source says some sections apply from 7 Oct 2027 (unconfirmed).
  - Sources: [MAS Guidelines PDF](https://www.mas.gov.sg/-/media/mas-media-library/regulation/guidelines/bd/guidelines-on-artificial-intelligence-risk-management-for-financial-institutions/guidelines-on-artificial-intelligence-risk-management.pdf); [MAS consultation paper](https://www.mas.gov.sg/-/media/mas-media-library/publications/consultations/bd/2025/final_consultation_paper_on_guidelines_on_ai_risk_management_forrelease.pdf); [HLC note](https://www.hlc.com/en/publications/mas-issues-new-ai-risk-management-guidelines-for-financial-institutions)
- A global survey of GenAI regulation in financial institutions (arXiv 2504.21574, 2025) exists as a broader reference; its content was not reviewed in detail. — [arXiv 2504.21574](https://arxiv.org/pdf/2504.21574)

### Inferences
- For a portfolio project, the safe and defensible framing is:
  - The LLM is an **assistant that drafts and cites**; the human decides.
  - Every LLM output is logged with model version, prompt version, the cited records and the reviewer's action (accept/edit/reject). That gives a record trail, which matches MAS's "documented review".
  - The deterministic SHAP reason codes stay the primary explanation of *why the alert fired*. The LLM summary is secondary and checked against them. This matches Wolfsberg's emphasis on explaining why the alert was generated.
- Mapping each feature to a typology/risk indicator (Wolfsberg's "mapping inventory") is cheap to add as a table and directly answers the "risk coverage" lens.

### Gaps
- **FCA (UK):** no 2025–2026 FCA statement on GenAI in AML was retrieved.
- **EU AMLA / EBA, EU AI Act:** not retrieved this session. Whether AML transaction monitoring counts as "high-risk" under the AI Act was not verified.
- **FATF:** no 2025–2026 FATF AI/AML publication was found in search. FATF's 2021 "Opportunities and Challenges of New Technologies for AML/CFT" is known, but it was not fetched and predates GenAI.
- FinCEN's April 2026 proposal was seen only through secondary sources; the primary Federal Register notice should be checked before quoting.
