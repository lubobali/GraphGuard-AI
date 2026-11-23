# First-run UX and plain-language explanation of an AML detection demo, for complete newcomers

Research notes, 2026-11-23. Scope: how to make the GraphGuard demo make sense at first sight to someone who has never seen an AML dashboard, without dumbing it down for experts. It does not repeat `AML investigator interface research 2026 notes/performance_for_managers.md`, which already covers Shen et al.'s confusion-matrix study (flow chart preferred), natural frequencies for ML metrics, ATL/BTL, and the capacity-slider sentence for managers.

The user test this answers: the visitor expected the model to "catch all 1,083 laundering payments", did not see why only the top list (211 of 1M) is shown, did not understand "flags", "rings", "rules vs model", the capacity-slider sentence or the chart with "rules" and "random" lines, and clicked a decision button 15 times because there was no visible feedback.

Source quality: NN/g, PAIR, Gigerenzer/Harding Center and the Distill and meta-analysis papers are primary. The tour-completion figures come from Chameleon, a vendor that sells product tours. The AML training simulators are vendor pages describing their own products.

---

## 1. Onboarding patterns: value statement, "how it works" strips, tours vs inline hints, progressive disclosure, glossary tooltips

### Takeaway
The evidence favours a usable interface with short, contextual, on-demand help over front-loaded tutorials. In NN/g's test, reading a tutorial did not improve success and made tasks *feel* harder. If you do use a tour, keep it to 3-4 steps and let the user start it: completion falls off a cliff by about 7 steps. Explain the benefit, not the technology. Be upfront early about what the system cannot do. Put jargon definitions behind on-demand tips, but never hide information the task needs inside a tooltip.

### Cited Findings
- **NN/g mobile tutorial test** (70 iPhone users, 4 apps, between-subjects, read vs skip a deck-of-cards tutorial): task success 91% (read) vs 94% (skipped), not significant. Time 93.5 s vs 85.2 s, not significant, and that excludes the time spent reading. Perceived ease (SEQ, 1-7) was 4.92 vs 5.49, significantly *worse* for readers (p = 0.047). Advice: "Think twice about creating a tutorial for simple applications", spend the effort on usability, and if onboarding is needed, prefer interactive methods such as contextual help — [NN/g, Mobile Tutorials](https://www.nngroup.com/articles/mobile-tutorials/).
- NN/g: professionals avoid creating app onboarding where they can and put the resources into making the UI more usable. Onboarding screens are justified in only a few cases — [NN/g, Mobile App Onboarding](https://www.nngroup.com/articles/mobile-app-onboarding/). NN/g's tutorial-examples article recommends progressive disclosure for help: its existence is visible, the detail appears on request. Example: Figma's text-layout help appears only when that tool is opened — [NN/g, Onboarding Tutorials](https://www.nngroup.com/articles/onboarding-tutorials/) (summary from search; the full page was not fetched).
- **Tour length (vendor data, Chameleon 2025):** 3-step tours 72% completion, 4-step 74%, 7-step 16%. Click-triggered (user-started) tours 67%, the best trigger type — [Chameleon Benchmark Report 2025](https://chameleon.io/benchmark-report). Earlier years: average 33.5% across all tours and 21.6% for 5-step tours (2024) — [Chameleon 2024](https://www.chameleon.io/benchmark-report-24); average 30% (2023) — [Chameleon 2023](https://www.chameleon.io/benchmark-report-2023). Methods are not disclosed, so treat these as directional.
- **Google PAIR People + AI Guidebook (Mental Models chapter):** be "up-front about what your product can and can't do" the first time users interact with it. Avoid "AI magic" messaging. Use a frame of core benefit, current limitation ("Right now, it's not able to…") and how it improves. Keep the first introduction short and about core value, and introduce features when they become relevant. Let users try low-risk, reversible actions. Section heading: "Explain the benefit, not the technology". Put technical detail in tooltips or progressive disclosure — [PAIR Guidebook, Mental Models](https://pair.withgoogle.com/chapter/mental-models/).
- **Tooltips:** "Don't use tooltips for information that is vital to task completion" — [NN/g, Tooltip Guidelines](https://nngroup.com/articles/tooltip-guidelines). NN/g says well-built info tips are fine for clarifying jargon and technical terms — [NN/g, Info tips](https://www.nngroup.com/articles/info-tips-bad/). eBay's design system: a tooltip should be no more than one sentence — [eBay MIND Patterns](https://ebay.gitbook.io/mindpatterns/disclosure/tooltip).
- **Progressive disclosure** sequences information and actions across screens or steps to reduce overwhelm — [IxDF](https://ixdf.org/encyclopedia/progressive_disclosure.html). Shneiderman's mantra, "Overview first, zoom and filter, then details-on-demand", is the cognitive-load principle Hohman et al. recommend for explanatory interfaces — [Distill, Communicating with Interactive Articles](https://distill.pub/2020/communicating-with-interactive-articles/).
- **Terminology:** in Shen et al.'s confusion-matrix study, *contextualising the terms* (domain words instead of "true positive") significantly improved lay understanding — [CMU / CSCW 2020](https://dig.cmu.edu/publications/2020-confusion.html).

### Inferences
- No auto-starting multi-step tour. Use: (a) a one-line value statement at the top, e.g. "A computer ranks 1 million payments by how suspicious they look, so a small team can check the worst ones first"; (b) a 3-step strip in the order of the real process, e.g. "1 · The model ranks every payment → 2 · The team checks the top of the list → 3 · Checked cases become labels the model learns from"; (c) an optional "Show me around" tour of at most 3-4 steps, started by the user.
- Replace jargon in the main text with domain-contextual words, and keep the term in a one-sentence tip for experts. "Flag" becomes "sent for a human to check". "Ring" becomes "a group of accounts passing money between them to hide where it came from". "Rules" becomes "fixed if-then checks banks use today (e.g. 'many payments just under a limit')". "Model" becomes "a system that learned patterns from past cases". Key numbers must not live only in a tooltip.
- Lead with the limit, PAIR-style: "It cannot check everything and it is not always right — it puts the most suspicious first."

### Gaps
- No controlled study found comparing tours, inline hints and empty states on *data or ML dashboards* specifically. The evidence is general apps plus vendor data.
- Baymard has no relevant study (its research is e-commerce). None was cited.
- NN/g's dedicated progressive-disclosure article was not retrieved directly.

---

## 2. Explaining imperfect detection to lay people: screening framings, plain-language confusion matrix, natural frequencies, icon arrays, caught / missed / false alarms, capacity

### Takeaway
The best-evidenced frame is **medical screening with natural frequencies**: "out of N, this many are caught, this many missed, this many false alarms", always with a stated reference class. Even 10-year-olds can solve these problems when the numbers are counts but not when they are conditional probabilities. Tabular fact boxes (two options side by side, absolute numbers) work as well as icon arrays in the short term. A rare condition means even a good test raises more false alarms than real finds. That is the "why only a top list, and why not everything is caught" story. PAIR's disease-screening explorable shows how to teach the threshold trade-off: an ideal model, then realistic mistakes, then a slider, then a "why it matters" case for each side.

### Cited Findings
- Natural frequencies (counts sampled from a population, e.g. "950 out of 9,900" healthy women get a false-positive mammogram) make Bayesian screening problems far easier than conditional probabilities. Gigerenzer reports that 10-year-olds can work out the positive predictive value from natural frequencies but are helpless with probabilities — [Gigerenzer, What are natural frequencies? (BMJ 2011)](https://pure.mpg.de/pubman/item/item_2099208_9/component/file_3562683/Gigerenzer_What_2011_VerlPDF_final_LS.pdf). In a training session, 87% of gynaecologists learned to translate sensitivity and false-alarm rates into natural frequencies, after most had first guessed the PPV at 80-90% — same source family ([Gigerenzer et al., PSPI 2007 via Scribd](https://www.scribd.com/document/335278225/pspi-8-2-article1229-pdf)). False alarms are presented as a real *harm* of screening (anxiety, extra tests) — same.
- Graphical grids improve diagnostic inference beyond natural frequencies alone (Garcia-Retamero & Hoffrage 2013, cited in) [Frontiers in Psychology 2015](https://www.frontiersin.org/articles/10.3389/fpsyg.2015.00932/full). The same study warns that many icon arrays carry no numbers, and that low-numeracy readers are overconfident. So put the counts **on** the picture.
- **Harding Center fact box:** two options side by side, benefits and harms in absolute numbers — [Harding Center icon array, mammography](https://www.hardingcenter.de/sites/default/files/2020-05/Icon%20array_mammography_EN_20191012.pdf). McDowell, Gigerenzer et al. (2019) found tabular fact boxes and icon-array versions equally effective for comprehension and recall in the short term — [Medical Decision Making 39(1):41-56](https://ideas.repec.org/a/sae/medema/v39y2019i1p41-56.html). Icon arrays of 100 or 1,000 make the reference class and part-to-whole visible — [MPG paper](https://pure.mpg.de/pubman/item/item_3037619_7/component/file_3047439/id10007998.pdf).
- **The false-positive paradox:** when a condition is rare, even an accurate test produces more false alarms than true finds. Example: about 10 false positives out of 999 healthy people at a 1% false-positive rate — [Scientific American](https://www.scientificamerican.com/article/the-false-positive-paradox-explains-why-you-misjudge-risk/).
- **PAIR "Measuring Fairness"** (a disease-screening model): people drawn as figure icons; "models and tests aren't perfect"; errors called mistakes, a sick person marked healthy is a miss and a healthy person marked sick is a false alarm. Structure: ground truth → an ideal model → realistic mistakes → a threshold slider showing "catching sick people" vs precision → when each matters (follow-up test available → catch everyone; scarce drug → avoid false alarms) → subgroups and base rates. Each step ends with a "Try adjusting…" prompt — [PAIR explorable](https://pair.withgoogle.com/explorables/measuring-fairness/); [Google blog](https://blog.google/technology/ai/pair-ai-interactive-visualizations/).
- Lay readers misread confusion matrices (reading direction, layered quantities). Flow charts most improve objective understanding — [Shen et al. CSCW 2020 PDF](https://www.andrew.cmu.edu/user/hongs/files/CM_CSCW2020.pdf) (covered in the earlier note; repeated only for the flow-chart link).

### Inferences
- Answer "why not catch all 1,083?" with a natural-frequency flow, not percentages: "1,015,300 payments → about 1,083 are laundering (about 1 in 1,000) → the team can check 211 → of those, X are laundering (caught), 211−X are innocent (false alarms), 1,083−X laundering payments stay below the line (missed)." Draw it as a flow chart (Shen) with the counts printed on it.
- Use the airport-security or medical-screening analogy in one sentence: "Like airport screening: no one opens every bag, the scanner picks which bags a person opens, and some bags with something inside still get through." Then: "Checking more means more false alarms per real find. Checking less means more misses. The slider moves that line."
- Turn the capacity sentence into a fact box with two columns, "Model picks 211" vs "Rules pick 211": caught / false alarms / missed as counts. The fact-box evidence says this beats a dense sentence or chart for newcomers.
- Rename the chart lines: "random" becomes "picking payments at random (what you get with no system)", "rules" becomes "today's fixed checks". Label the line ends directly, and put the user's current slider position on the chart.
- Show a 1,000-icon array only when it carries numbers. At a 1-in-1,000 base rate a single icon is the whole class, so a flow chart or fact box will read better than an icon array at full scale. Zoom into "the 211 checked" as an icon grid (caught vs false alarm) instead.

### Gaps
- No study found that tests the airport or spam-filter analogy for *fraud/AML* explanations. These are common framings but untested here.
- Spiegelhalter's own icon-array material was not retrieved.

---

## 3. Explorable explanations and scrollytelling for ML: what makes them land

### Takeaway
Interactive articles are engaging and can help recall, but the evidence base is thin. What has evidence: prediction before reveal ("You Draw It" improved recall), low-stakes quizzes with feedback (the testing effect), segmenting with reader control, multiple linked representations, and details on demand. Scrolly and step layouts are preferred but not proven better for comprehension; slideshows did better in one study. Many readers never touch interactive elements, so the key message must not depend on interaction.

### Cited Findings
- From Hohman, Conlen, Heer & Chau, "Communicating with Interactive Articles" (Distill 2020) — [Distill](https://distill.pub/2020/communicating-with-interactive-articles/):
  - Readers preferred step- or scroll-based layouts to static ones, but engagement did not differ (McKenna et al.). Slideshow layouts gave better comprehension (Zhi et al.). Both studies were desktop only.
  - Prediction before reveal: the NYT "You Draw It" format improved recall (Kim et al.). Showing others' predictions did not clearly add to recall.
  - Low-stakes quizzes with feedback improve later recall (the testing effect). Self-explanation improves learning.
  - Segmenting into bite-sized parts with play, pause and scrub, e.g. R2D3's "A Visual Introduction to Machine Learning". Multiple representations plus the multimedia principle.
  - Unit visualisations (the NYT's 10,000 animated people) remind readers the data is people. Person glyphs alone were not shown to add empathy.
  - Warnings: only a fraction of NYT readers interact with non-static content. Empirical evaluation is sparse. Interactivity can distract or go unused, and not everything needs it.
- PAIR's explorable pattern: each step ends with a "Try adjusting…" prompt and a concrete reason to care about each side of the trade-off — [PAIR](https://pair.withgoogle.com/explorables/measuring-fairness/).

### Inferences
- Add a 30-second "predict first" moment before the queue: "There are about 1,083 laundering payments in 1 million. If your team can check 211, how many do you think you'll catch?" The guess is then shown against the real answer. That uses the evidence behind the prediction effect and directly repairs the "catch all 1,083" expectation.
- Use a short stepped (slideshow-like) intro of 3-4 panels rather than a long scrolly. Every panel must work as static text with its numbers, since many visitors will not interact.
- Use the ring picture as the "data are people/accounts" unit visual, but only after the plain sentence explaining what a ring is.

### Gaps
- No evaluation was found of an explorable about fraud or AML detection specifically.
- No mobile-specific comprehension evidence for scrollytelling (the studies cited were desktop).

---

## 4. Decision feedback UX: confirmation, locked state, undo or change decision, "next item"

### Takeaway
The first usability heuristic is visibility of system status: every click needs an immediate visible state change. For routine, reversible decisions (a demo verdict), the guidance is acknowledge plus undo, not "Are you sure?" dialogs, which users habituate to. Confirmation dialogs are for severe, irreversible actions, with buttons that name the outcome. In the GraphGuard demo, verdicts are an append-only audit, so "change decision" should be a new entry shown in a visible history, not an edit.

### Cited Findings
- Visibility of system status is NN/g's first heuristic: tell users what is going on through timely feedback. It can be as simple as a colour change or a progress indicator — [Educative summary of NN/g heuristic](https://www.educative.io/answers/what-is-the-visibility-of-system-status); [uxdesign.cc on feedback states](https://uxdesign.cc/how-to-design-intuitive-interfaces-using-feedback-mechanisms-and-states-ca376f41d8ed).
- **NN/g on confirmation dialogs:** use them for serious-consequence or irreversible actions. "Try your best to offer undo" because it lowers anxiety and recovers errors. Overused dialogs train users to click "Yes" without reading. Avoid "Are you sure?" and name the item and its effect, with outcome buttons ("Delete file" / "Keep file"). Don't set a default — [NN/g, Confirmation Dialogs](https://www.nngroup.com/articles/confirmation-dialog/).
- Prefer a visible undo notification to confirmation dialogs for less severe actions. People click through confirmations unread — [W3C cognitive a11y list, citing Smashing Magazine](https://lists.w3.org/Archives/Public/public-cognitive-a11y-tf/2020Apr/0059.html); [UXmatters, "Are you sure?" vs undo](https://uxmatters.com/mt/archives/2020/03/are-you-sure-versus-undo-design-and-technology.php).
- Android's pattern guide distinguishes *confirming* (before) from *acknowledging* (after). Acknowledgement can carry an undo. Trivial actions may just toggle back — [Android design patterns, archived](https://stuff.mit.edu/afs/sipb.mit.edu/project/android/docs/design/patterns/confirming-acknowledging.html).
- Microsoft HAX Toolkit has a pattern to "remind of consequences of a past action and ask for reconfirmation" for AI systems — [HAX pattern 16C](https://www.microsoft.com/en-us/haxtoolkit/?p=728).

### Inferences
- After a verdict click: (1) instantly lock the buttons and show the chosen verdict in place ("You marked this: Suspicious · 14:02"), with the button itself changing state, not a toast far away; (2) offer a "Change decision" link that writes a new audit row and shows the history; (3) show the next step, "Next alert →", or auto-advance with a visible "Moved to alert #22" note; (4) disable the button during the request to stop double posts. The server should also make repeat posts idempotent, so 15 clicks can never create 15 rows unnoticed.
- No "Are you sure?" dialog on verdicts: they are frequent and reversible, so dialogs would habituate. A one-time explanation of what a verdict does ("this records your call; it does not change the model") fits PAIR's "low-risk, reversible" advice.

### Gaps
- The NN/g visibility-of-system-status article itself was not fetched (secondary summaries cited). No study found on double-click / repeat-submit rates tied to missing feedback.

---

## 5. Training simulators and gamification: AML/fraud simulations, answer-key reveal, scores, learning evidence

### Takeaway
AML training already uses scenario simulations. Some (Eureka CleanSlate) have learners tune monitor sensitivity against alert volume, false positives and fixed analyst capacity, which is exactly GraphGuard's slider. Others (Attensi, Wolters Kluwer AML Virtuoso, academic Unity games) have learners spot red flags and decide whether to escalate. Gamification has small-to-medium learning effects in meta-analysis (cognitive g ≈ 0.49), with game fiction and social interaction as moderators. The best-supported mechanic for the demo is the testing effect: decide first, then get immediate feedback (the answer key) with an explanation, and keep a running score.

### Cited Findings
- **Eureka Simulations CleanSlate:** learners run a bank's Financial Crime Compliance Committee ahead of an OCC exam. Each round they set four monitors (cash structuring, wire velocity, behaviour deviation, digital-asset gateway) on a 1-10 sensitivity scale, choose trade-finance review, and split analyst hours between new alerts and backlog, with a mid-cycle capacity loss. Learning goals: weigh sensitivity against alert volume and false-positive rate within fixed analyst capacity. 4 rounds, about 75 minutes, executive level, scored per round with an instructor dashboard and a debrief. No learner-facing scoring is described — [Eureka Simulations](https://www.eurekasimulations.com/basics/cleanslate-aml-compliance/) (vendor).
- **Attensi:** short game-based sessions on realistic cases: spotting red flags, difficult customer conversations, deciding when to escalate — [Attensi AML](https://attensi.com/solutions/financial-services-insurance/anti-money-laundering-training/) (vendor). **Wolters Kluwer AML Virtuoso:** a web simulation for training bank staff to "sleuth" laundering. The vendor claims faster learning than traditional methods — [American Banker](https://www.americanbanker.com/news/wolters-kluwer). **ScenarioLab:** a scenario-based interactive investigation worth 3 CPD points — [ScenarioLab](https://scenariolab-website.pages.dev/). **PolyU Hong Kong:** a two-player Unity game where one player is the launderer and the other the AML specialist — [ECGBL paper](https://papers.academic-conferences.org/index.php/ecgbl/article/view/1512). ACAMS offers self-paced certificates (e.g. Leading Complex Investigations, 4 credits). No ACAMS game was found — [ACAMS](https://www.acams.org/en/training/certificates/leading-complex-investigations).
- **Gamification meta-analysis** (Sailer & Homner 2020, Educational Psychology Review 32:77-112): significant small effects on cognitive (g = .49, k = 19, N = 1,686), motivational (g = .36) and behavioural outcomes. The cognitive effect held in high-rigour studies, the motivational and behavioural effects were less stable. Game fiction and social interaction moderated behavioural effects. The authors flag likely underpowering and did not assess publication bias — [Springer](https://link.springer.com/article/10.1007/s10648-019-09498-w); [Augsburg PDF](https://opus.bibliothek.uni-augsburg.de/opus4/files/109056/109056.pdf).
- **Testing effect:** low-stakes quizzes *with feedback* improve later recall, and prediction before reveal improves recall — [Distill, Hohman et al.](https://distill.pub/2020/communicating-with-interactive-articles/).

### Inferences
- Make the verdict flow a mini training simulator: decide → immediate reveal ("The answer key says: YES, part of a ring · here is the pattern") → a running tally "You: 7 right of 10 · the model's top-10 had 6 real" → next alert. The reveal is the feedback that drives learning (testing effect). Keep the answer key hidden until after the decision, which also matches the existing rule that truth is kept apart.
- Offer a CleanSlate-style "manager round" as an optional second mode: the user sets capacity, then sees caught / missed / false alarms for model vs rules as counts. This is the slider, framed as a challenge ("Can you catch more rings with fewer checks?").
- Keep game elements light: a score and a "you vs the model" comparison (social or competitive). No points or badges noise. The meta-analysis effects are modest, and the expert audience must not see it as a toy. Label it clearly: "Training mode — synthetic data."

### Gaps
- No published evidence was found on learning outcomes of *AML-specific* simulators. All effectiveness claims found are vendor self-reports.
- No study found specifically on answer-key-reveal timing (immediate vs delayed) in fraud training. The general testing-effect evidence is the closest.
- No public "spot the fraud" consumer game with evaluation data was found in this pass.
