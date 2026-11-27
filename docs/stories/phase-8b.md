# Phase 8b — Make it findable: stories

**Status:** approved by Lubo 2026-11-27 (address `graphguard.lubobali.com`; work in `/srv/lubobali-staging` allowed). Runs **before Phase 8** (R-6:
AWS re:Invent the following week).

**How stories are expanded:** one at a time, just before work starts on it. S8b.1 is fully
expanded; the rest stay short until their turn.

## Main goal

A stranger can reach the live demo, understand what it does, and find the repo, without Lubo
explaining anything (PLAN.md, Phase 8b "Done means"). And Lubo can explain it himself in 90
seconds.

**Honesty rules for everything public in this phase:**
- "Synthetic data (IBM AMLworld)" comes first, every time.
- Every number is a **validation** number. The test window is still sealed (R-5, R-6).
- No weak spots: no ports, versions, paths, keys, or audit findings (CLAUDE.md). Every public
  diff is grepped before it is pushed.
- Nothing that has not been done is claimed (no "drift alert then retrain" yet: Phase 8).

**Epic / Definition of Done:** the public URL answers from outside the box; the AI stand-in
test (S8b.1) run again on the *public* URL finds no blocker; README, website page, video
script, 90-second answer, post and resume bullet exist; LuBot is untouched (its health checks
are the same before and after).

---

## S8b.1 — Close Phase 7: three small fixes and the AI stand-in test

**As** a first-time visitor, **I want** the try-a-case tour to have no odd bits, **so that**
I understand it without help. **As** Lubo, **I want** the Phase 7 gate closed honestly
without the real-person test (R-6).

Fixes (each with a test first):
- [ ] The score line is hidden until the first answer: the kicker reads "Case 1 of 3", not
      "Case 1 of 3 · 0 of 0 right" (`tourLogic.scoreText([])` returns "").
- [ ] When a case was flagged by a rule, that rule is its first reason in plain words (for
      example, "just under a 10,000 reporting line"), taken from the alert's own rule text and
      never from the answer key. `tour.json` is rebuilt and the live test still holds it
      equal to the database.
- [ ] Business types read plainly: "Sole Proprietorship #29351" becomes "A small business
      (#29351)". This is one pure function, tested on every type in the data, and used
      wherever a name is shown.

The AI stand-in test:
- [ ] A reviewer agent with **no project context** gets only screenshots, phone and desktop:
      home, then `/try` all the way through, then one Case page. It answers the S7.11
      questions in writing: what the system does, what it would do next, where it got stuck,
      and what it would tell a friend.
- [ ] Run twice: as someone who has never heard of money laundering, and as a bank
      investigator.
- [ ] Every blocker it names is fixed or written down with a reason. Its words are kept in
      `docs/stories/phase-7.md`.
- [ ] The gate is marked in CLAUDE.md and PLAN.md as "met with an AI stand-in (R-6); a real
      person still owed", never as a real-person test.
- [ ] Web tests and CI green, both remotes match.

## S8b.2 — Safe to open to the internet

**As** Lubo, **I want** strangers to be able to use the demo without hurting the box, LuBot,
or the data, **so that** a public link is not a risk.
- [ ] The real visitor's address is used for rate limits behind nginx. The forwarded header is
      trusted only from the local proxy. Today every visitor would share one limit.
- [ ] Visitor writes are capped: per visitor, and in total per day. Visitor rows can be
      cleared with one command; Sam's seeded cases are never touched.
- [ ] Only the API's own routes and the static site answer. Errors show no stack traces.
      Security headers and CSP are checked from outside.
- [ ] The answer key appears only where the design shows it (after a decision, or in the
      tour). A test calls every route without a decision.
- [ ] Load: a burst from outside (for example, 50 visitors at once) keeps memory under the cap,
      and LuBot's health is unchanged.
- [ ] A kill switch: one command takes the public site down without touching anything else.
- [ ] The weak-spot notes for this go to `private/` only.

## S8b.3 — The public URL

**As** a stranger, **I want** a normal web address with HTTPS, **so that** I can click it from
a post or a resume.
- [ ] Name and DNS chosen by Lubo (for example, `graphguard.lubobali.com`).
- [ ] The nginx site and certificate are added **by the LuBot session** (a box-wide change).
      We hand it the exact block; we do not edit nginx ourselves.
- [ ] Afterwards: `just edge-baseline`, the edge and health checks green, and lubot.ai and its
      siblings still answer.
- [ ] Checked from outside the box: the home page, `/try`, a case, and a decision saved.
- [ ] The scorer alert (or an uptime check) covers the public URL.

## S8b.4 — The README and a 10-second diagram

**As** a hiring engineer, **I want** to understand the project in one screen, **so that** I keep
reading.
- [ ] Top: synthetic data first, one line on the problem, the live link, the diagram, 3
      screenshots.
- [ ] The headline numbers (validation): 127 of 168 rings at 5,000 alerts; XGBoost vs the GNN
      (the GNN lost, and that is written up); p99 13–15 ms; the full window replayed with 0
      mismatches; the agent's measured unsupported-claim rate.
- [ ] "What I'd do differently" and "Next" (Phase 8, the sealed window's one-time replay,
      Phases 9–10).
- [ ] How to run it, links to the findings, ADRs and stories.
- [ ] Every number is checked against its source file by a test, and the README is grepped for
      weak spots.

## S8b.5 — The project page on Lubo's website

**As** a visitor of lubobali.com, **I want** to find GraphGuard, **so that** the site leads to
the demo and the repo.
- [ ] A short page or card with the link, the diagram and 3 lines, in that project's own style.
- [ ] Made in that project's repo (`/srv/lubobali-staging`, public mirror, no secrets) with
      Lubo's OK, or by its own session.

## S8b.6 — The pitch kit

**As** Lubo at re:Invent and in interviews, **I want** to explain it simply and the same way
every time.
- [ ] Demo video script, 2–3 minutes: home, try one case, Case page, manager page, one honest
      finding. Lubo records it.
- [ ] A 90-second answer: the problem, why a graph, the result, what I'd do differently.
      Lubo says it out loud at least 3 times.
- [ ] A LinkedIn post draft in Lubo's voice (not polished), with one honest finding as the hook.
- [ ] A resume bullet with the real number in it.
- [ ] Pitched as receiving-bank mule-network detection, with the caveats (R-2).

Out of scope (after re:Invent): Phase 8 (monitoring, retraining, champion/challenger, model
card), the go-live replay of the sealed window, Phases 9–10, logins, live AI calls.
