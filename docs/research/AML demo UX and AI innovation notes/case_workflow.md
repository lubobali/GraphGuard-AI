# AML case workflow in real tools: states, decisions, review, deadlines, manager metrics (as of Nov 2026)

Method note: 18 tool calls. This file extends `docs/research/AML investigator interface research 2026 notes/investigator_tools.md` and does not repeat it. That file already covers queue sort order, Oracle's red overdue dates, Unit21 queues and deadlines, Lucinity's four-eyes and blind review, Flagright maker-checker, the BPI figure of 21 h per SAR, and the generic KPI list.

The strongest sources here are **primary documents**: Oracle ECM and Investigation Hub user guides, the Lithic case API docs, and the FinCEN SAR FAQ PDF of 9 Oct 2025, read in full from the PDF text. Several sources were blocked:
- Unit21 docs redirect to a login.
- The FFIEC manual returned 403.
- The eCFR redirected to a bot wall.
- Flagright's and Hummingbird's help centres did not show up in search.

Vendor blogs (Sphinx, Sardine) are marked as practitioner opinion, not standards.

## 1. Workflow states and disposition / closure codes

### Takeaway
Real tools have a small set of top-level states, roughly **Open → Assigned → In review → (Pending info / On hold) → Escalated → Pending approval ("Recommend Closure") → Closed**. Teams add their own sub-statuses under these. The closure decision is a **short, fixed list of resolution codes plus a mandatory comment**. The canonical AML split is **"closed, no SAR" vs "closed, SAR filed / escalate to SAR"**. Detailed reason-code taxonomies are configured per firm and not published.

### Cited Findings
- **Oracle ECM 8.1.2.11** has two resolution actions under *Take Action → Resolution*: **"No SAR Filed- Closed"** and **"Close and generate SAR"**. **Comments are mandatory**; a warning appears if they are missing. Attachments, owner/assignee and due date are optional. When a case reaches Closed, the system **clears the due date** and **starts a suppression-request workflow** (to suppress similar future alerts). — [Oracle ECM 8.1.2.11: Taking Resolution Action](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/enterprise-case-management/8.1.2.11.0/ecgug/taking-resolution-action.html)
- Oracle FCCM (older Case Management guide): you close from status *Investigation* or *Review in Progress* via *Take Action → Resolution → Close Case*, and **a closure reason is mandatory**. A case sent for supervisor review moves to **"Pending Review"**. — [Oracle Case Management guide: Taking Action on Cases](https://docs.oracle.com/cd/F22800_01/html/cmug/Responsive_HTML5/Taking_Action.htm) (summarised from search result; not fetched in full)
- **Oracle Investigation Hub Cloud 26.02.01** (sanctions/payment-filtering cases):
  - The *Case Decision* pane offers **Escalate** alongside Recommend Block / Release.
  - Escalating requires a **Reason from a drop-down**, plus optional Due Date, running Comments (kept in a comment history) and drag-and-drop documents.
  - The status becomes **"Escalated"**.
  - Two buttons: **"Submit"** returns to the Case List; **"Submit and Next"** opens the next case assigned to the user.
  - An admin setting decides whether **each event (transaction) must get its own disposition before the case decision** ("Event-level disposition required before case decision") or the case is decided as a whole ("Case-level disposition only"). — [Oracle Investigation Hub: Escalating the Case](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/investigation-hub-cloud/26.02.01/ihueg/escalating-case.html)
- **Lithic** (card-issuer TM case API, beta):
  - Statuses: `OPEN`, `ASSIGNED`, `IN_REVIEW`, `ESCALATED`, `RESOLVED`, `CLOSED`.
  - Default resolution codes: `CONFIRMED_FRAUD`, `SUSPICIOUS_ACTIVITY`, `FALSE_POSITIVE`, `NO_ACTION_REQUIRED`, `ESCALATED_EXTERNAL`. A queue can replace them with its own `allowed_resolutions`. A code outside the queue's list is rejected with HTTP 400, and past resolutions are not re-validated when the list changes.
  - `resolution_notes` is set on resolve/close.
  - Assigning sets `assignee` and `status=ASSIGNED` together and **stops new transactions being added to the case**. — [Lithic: Transaction monitoring cases](https://docs.lithic.com/docs/transaction-monitoring-cases)
- **Flagright** release note (May 2026): **custom alert statuses** emit events named `OPEN_<custom>` and `ESCALATED_<custom>`, which means custom statuses sit *under* the fixed Open / Escalated parents. Alerts can be filtered by **AI-agent disposition** and by **auto-closed vs sent to human review**. — [Flagright release notes, 1 May 2026](https://tickets.flagright.com/en/articles/14666880-1-may-2026) (via search summary)
- **Sumsub** (KYC/AML case tool): statuses Open, **Awaiting user** (the "pending info" state), Resolved (split into **Valid threat** / **False positive**), and Blocked, with custom stages under each. Escalating a case resets it to Open's default stage. — [Sumsub: Adjust case status](https://docs.sumsub.com/docs/adjust-case-status) (via search summary)
- **Socure RiskOS**: Open / **On Hold** / Closed. "In Review" is the default sub-status of Open, and "Escalated" can be added as a custom sub-status. — [Socure: Cases & Manual Review](https://help.socure.com/riskos/docs/cases-and-manual-review) (via search summary)
- **Sardine** (practitioner explainer, vendor blog) names three disposition outcomes: **close with no action**, **escalate to a case / EDD**, **refer for SAR**. Every disposition needs a written rationale that "actually supports the decision and addresses every flagged transaction". Boilerplate that could fit any customer is treated as a weakness. — [Sardine: Alert disposition](https://www.sardine.ai/learn/alert-disposition)

### Inferences
- A realistic GraphGuard decision set is a **fixed list of 3-5 codes with a required free-text rationale**. For example: *Closed - no suspicious activity (explained)*, *Closed - false positive (data/model)*, *Escalated to case/EDD*, *Escalated - SAR recommended*. Plus a "pending info" hold state.
- Oracle's "Submit and Next" button is worth copying. It is how real L1 queues get worked.
- Oracle's "event-level disposition" option maps to GraphGuard's rings. An analyst could mark each transaction in the ring before deciding the alert.

### Gaps
- No vendor publishes its full closure reason-code list (for example "explained by customer profile"). Unit21's alert/disposition docs are behind a login. Hawk, Actimize, Quantexa and NetReveal reason lists were not found.

## 2. Four-eyes, QA sampling, SAR handoff and deadlines

### Takeaway
Two kinds of review exist:
- **Quality control (QC)**, inside the workflow. In Oracle an analyst's close becomes **"Recommend Closure"** and a supervisor approves or rejects it.
- **Quality assurance (QA)**, after the fact. A second-line team samples *closed* alerts.

Deadlines come from US law. The **SAR is due 30 calendar days after initial detection** (60 days if no suspect is identified). FinCEN's **9 Oct 2025 FAQs** relaxed two widely held expectations: a separate continuing-activity review is not required, and **documenting a no-SAR decision is not required**.

### Cited Findings
- **Oracle ECM maker-checker**:
  - When an **Analyst** takes a resolution action on a non-closed case, it moves to **"Recommend Closure"** and must be assigned to a supervisor, who approves or rejects.
  - A **rejection returns the case to its previous status**.
  - When a **Supervisor** takes the resolution action, the case closes directly.
  - Specified roles can "acknowledge" approved or rejected changes, with comments. — [Oracle ECM 8.1.2.11: Taking Resolution Action](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/enterprise-case-management/8.1.2.11.0/ecgug/taking-resolution-action.html)
- Oracle ECM 8.1.2.10 describes the same flow. A known issue (My Oracle Support note 3049379.1) reports a case stuck in "Pending Review" after "Approve Recommendation". — [Oracle ECM 8.1.2.10: Taking Resolution Action](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/enterprise-case-management-application-pack/8.1.2.10.0/ecgug/taking-resolution-action.html); [MOS 3049379.1](https://support.oracle.com/knowledge/More%20Applications%20and%20Technologies/3049379_1.html) (via search summary)
- **FinCEN FAQ, 9 Oct 2025** (primary PDF, read in full):
  - "Financial institutions are generally required to file a SAR **no later than 30 calendar days after the date of the institution's initial detection** of facts that may constitute a basis for filing a SAR." An extra 30 days is allowed to identify a suspect, "but reporting must not be delayed more than **60 days** after the date of initial detection" (citing 31 CFR 1020.320(b)(3)).
  - Q2: an institution is **not required** to conduct a separate review after filing a SAR to determine whether activity continued.
  - Q3: for firms that choose to follow the old 90-day continuing-activity guidance, the timeline is **Day 0 detection → Day 30 initial SAR → Day 120 end of 90-day period → Day 150 continuing SAR**. Without a suspect: Day 60 / 150 / 180. The older guidance had set 120 days after the previous SAR.
  - Q4: "There is **no requirement or expectation** under the BSA ... to document its decision not to file a SAR ... In most cases, a **short, concise statement** documenting a financial institution's SAR decision will likely suffice."
  - Issued with the federal banking agencies; the NCUA and FDIC republished it. — [FinCEN SAR FAQs, Oct 2025 (PDF)](https://www.fincen.gov/system/files/2025-10/SAR-FAQs-October-2025.pdf); [FinCEN news release](https://www.fincen.gov/news/news-releases/fincen-issues-frequently-asked-questions-clarify-suspicious-activity-reporting); [NCUA copy](https://ncua.gov/regulation-supervision/regulatory-compliance-resources/bank-secrecy-act-resources/frequently-asked-questions-regarding-suspicious-activity-reporting)
- Law firms still advise documenting no-SAR decisions as prudent, as a defence if an examiner later challenges the decision. — [King & Spalding](https://www.kslaw.com/insights/articles/fincen-relaxes-suspicious-activity-reporting-requirements-via-four-new-faqs); [Mayer Brown, 12 Nov 2025](https://www.mayerbrown.com/en/insights/publications/2025/11/fincen-publishes-faqs-to-reduce-certain-compliance-burdens-associated-with-sar-filings)
- **QA sampling practice** (Sphinx, vendor blog, practitioner opinion):
  - Sample **closed alerts**, not escalations, because missed suspicious activity (false negatives) can only be in the closed population.
  - Use three strata reported separately: **risk-weighted, random, targeted**.
  - Size samples by absolute count, not percentage: "Reviewing 5 percent of 200 alerts is underpowered." By the rule of three, 0 errors in 30 only shows the error rate is probably under 10%. "Any 'industry standard 5 percent' figure is convention, not regulation."
  - QC is first-line and pre-decision (maker-checker, owned by operations). QA is second-line and post-decision (owned by compliance). Independent testing is separate again (FFIEC sound practice: every 12-18 months).
  - Error taxonomy: **critical** (a SAR should have been filed), **substantive**, **documentation**, **process/SLA**, **systemic**.
  - Use a held-out **blind re-investigation** set in which reviewers cannot see the original disposition. Sample the AI auto-close population separately and track override rates in both directions. — [Sphinx: AML QA program](https://sphinxhq.com/blog-posts/aml-quality-assurance-program)
- The same source reports an OCC enforcement action (Community Federal) where an automated triage system auto-closed "a very high percentage of all ingested alerts". I did not verify this against the OCC's own document. — [Sphinx](https://sphinxhq.com/blog-posts/aml-quality-assurance-program)
- **Hummingbird** customer BHG Financial built automation that selects SAR cases for regular QA review. BHG reports SAR filing time fell from **90-180 min to 20-30 min** (vendor case study, claim). Hummingbird also claims filing-status tracking through direct FinCEN e-filing and batch filing. — [Hummingbird: BHG case study](https://www.hummingbird.co/resources/how-bhg-financial-files-sars-five-times-faster-with-hummingbird); [Hummingbird: SAR filing status](https://www.hummingbird.co/resources/get-complete-transparency-into-the-status-of-your-sar-filings-plus-batch-filing-with-fincen?hsLang=en)
- Sardine (vendor blog): QA and examiners "sample dispositions to test whether closes and escalations were justified". Red flags include boilerplate rationales, unaddressed flagged transactions, inconsistency across analysts, and a high reopen rate in QA. — [Sardine: Alert disposition](https://www.sardine.ai/learn/alert-disposition)

### Inferences
- For the demo, an analyst's "Close" should become **"Recommended: close - awaiting second review"**, not a final close. A second user (or the same user in a "reviewer" role, clearly labelled) approves or rejects, and a rejection returns the alert to its previous state.
- The 30-day SAR clock gives the demo a real **due date**: alert time + 30 days for an escalated / SAR-recommended alert. The demo should say plainly that this is the US rule and that the data is synthetic.
- A "QA sample" view fits GraphGuard's evaluation story. A random plus a risk-weighted draw from *closed* alerts, re-checked blind against the answer key, is the operational version of measuring false negatives.

### Gaps
- No regulator states a QA sampling percentage. The "5%" figure is described as convention. The FCA Financial Crime Guide was not reached.
- The exact clock-start ("initial detection" = alert generation vs. the end of the review that finds it suspicious) is not defined in the FAQ text read. The FFIEC manual section (blocked, 403) is the usual source.

## 3. What one decision may be: single disposition, reopening, audit trail

### Takeaway
Each alert or case carries **one current resolution**, but every change is kept in an **append-only activity log** that records actor type, previous value and new value. Reopening exists (Unit21, see previous file). Edits to comments are logged as new entries, and the originals are kept.

### Cited Findings
- **Lithic** activity log:
  - `event_type` is one of `STATUS`, `TITLE`, `ASSIGNED_TO`, `RESOLUTION_OUTCOME`, `RESOLUTION_NOTES`, `TAGS`, `PRIORITY`, `COMMENT`, `FILE`.
  - `actor_type` is one of `DASHBOARD_USER`, `API_USER`, `INTERNAL`, `RULE`.
  - Each entry also has `actor_token`, `previous_value` / `new_value` and `created`.
  - The log is **append-only and chronological**. Comment edits and deletes are logged as new entries, and the originals are kept. — [Lithic: Transaction monitoring cases](https://docs.lithic.com/docs/transaction-monitoring-cases)
- Lithic: changing a queue's allowed resolutions does not re-validate resolutions already recorded, so past decisions are immutable. — [Lithic](https://docs.lithic.com/docs/transaction-monitoring-cases)
- Oracle Investigation Hub keeps a **comment history**, and saved comments can be deleted by their author. — [Oracle Investigation Hub: Escalating the Case](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/investigation-hub-cloud/26.02.01/ihueg/escalating-case.html)
- Flagright distinguishes **agent disposition** from human review, and auto-closed alerts can be filtered. — [Flagright release notes, May 2026](https://tickets.flagright.com/en/articles/14666880-1-may-2026) (via search summary)

### Inferences
- GraphGuard's append-only `verdicts` table already matches the real pattern. On the Case page, show it as a timeline: who (human / agent / rule), what changed (from → to), when, and the note. A "reopen" should be a new row, never an edit.

### Gaps
- Oracle's reopen behaviour and its audit-history screen were not on the pages fetched.

## 4. Manager / team-lead dashboards: metrics and real numbers

### Takeaway
New in this pass: **SAR-side timing benchmarks** (vendor-reported), a QA framing in which the fail rate is reported by error category rather than as a single pass/fail number, and the regulatory day markers (30/60/150) that drive SLA buckets. Independent per-analyst throughput numbers are still missing.

### Cited Findings
- SAR preparation time at one Hummingbird customer: 90-180 min before, 20-30 min after (claim). — [Hummingbird BHG](https://www.hummingbird.co/resources/how-bhg-financial-files-sars-five-times-faster-with-hummingbird)
- QA reporting: report each stratum separately and score each dimension on its own. "Holistic pass/fail scoring drifts into meaninglessness within a couple of quarters." Track AI override rates in both directions. — [Sphinx QA](https://sphinxhq.com/blog-posts/aml-quality-assurance-program)
- A reopen rate in QA sampling is a named warning signal. — [Sardine](https://www.sardine.ai/learn/alert-disposition)
- Regulatory day markers that SLA buckets can follow: 30 days (SAR, suspect known), 60 days (no suspect), 150 days (continuing SAR under the old guidance). — [FinCEN FAQ Oct 2025](https://www.fincen.gov/system/files/2025-10/SAR-FAQs-October-2025.pdf)

### Inferences
- Manager panel for the demo: backlog by age bucket (0-7 / 8-14 / 15-30 / >30 days, the last tied to the SAR clock), pending-second-review count, escalation rate, SAR-recommended rate, reopen/overturn rate on second review, and agent vs human agreement.

### Gaps
- No independent published numbers for alerts per analyst per day or QA fail rates. The previous file's vendor estimates (about 20 alerts/day, 20-90 min/alert) are still the best available.

## 5. Queue status markers, grouping, due dates

### Takeaway
Few new primary details were found beyond the previous file. In practice, status is shown as the state name plus the assignee. Assigning a case freezes it (Lithic stops adding transactions). Closing clears the due date (Oracle). "Submit and Next" moves the analyst through their assigned queue.

### Cited Findings
- Lithic: assignment stops new transactions being added to the case, and records two events (`ASSIGNED_TO`, `STATUS`). — [Lithic](https://docs.lithic.com/docs/transaction-monitoring-cases)
- Oracle ECM: closure clears the due date. — [Oracle ECM 8.1.2.11](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/enterprise-case-management/8.1.2.11.0/ecgug/taking-resolution-action.html)
- Oracle Investigation Hub: an escalation can set a new due date, and "Submit and Next" opens the next case assigned to the user. — [Oracle Investigation Hub](https://docs.oracle.com/en/industries/financial-services/ofs-analytical-applications/investigation-hub-cloud/26.02.01/ihueg/escalating-case.html)

### Inferences
- In the demo queue, show columns for status chip (New / In review / Awaiting 2nd review / Escalated / Closed), owner, due date (red if overdue) and rank. Worked alerts stay visible but greyed, behind a "show closed" filter.

### Gaps
- No public screenshots or field lists for Actimize ActOne, Hawk, Quantexa, NetReveal or SAS queues or decision dialogs were reachable in this pass. Unit21 docs need a login.
