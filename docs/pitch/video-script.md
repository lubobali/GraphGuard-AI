# GraphGuard demo video: the script (S8b.6, voice of S8b.4c)

About **5 minutes** when read slowly (~700 spoken words). Screen + your voice. No face needed.

**How to read it:** each step has **DO** (what you click, on top) and **SAY** (what you read
while you click, below). Short pauses are fine. If you make a mistake, keep going.

**The message:** money laundering hides in patterns, not payments. Problem first, like a
Forward Deployed Engineer: what it changes for a bank, then what I built behind it and why.

Every click and number below was checked on the live site on 2026-11-28.

---

## Before you record

- Open a **fresh Chrome window** (or a new profile) at **https://graphguard.lubobali.com**.
  A fresh window has no old decisions from you, so the pages look like this script.
- Zoom **110%** (Cmd +). Hide the bookmarks bar (Cmd Shift B).
- At the top, **View as** should say **Investigator**.

---

## Step 1: The problem

**DO:** Stay on the home page. Don't move yet.

**SAY:**
> Money laundering hides in patterns, not payments.
> Every single payment looks normal.
> The crime is in how they connect: money split out to many accounts, then collected again.
> I built GraphGuard to find that pattern.
> I worked like a Forward Deployed Engineer: I played the meeting with a bank myself.
> First understand their problem. Then build the tool that fits it.
> Quick note: the data is made up, by IBM's simulator. No real people, no real client.

---

## Step 2: The size of the problem

**DO:** Point your mouse at the line **"Over 2 days: 1,015,300 payments, 1,083 laundering"**.

**SAY:**
> Here is the bank's real problem.
> In just two days: over one million payments.
> Hidden inside: about one thousand laundering payments.
> No person can search a million payments by hand.
> A computer has to look at every one.

---

## Step 3: Which 100?

**DO:** Point at the slider **"Your team checks the top 100 payments a day"** and **"= about 5 people"**.

**SAY:**
> A bank team of about 5 people can check about 100 payments a day.
> With GraphGuard or without it. That doesn't change.
> What changes is **which 100.**

**DO:** Point at **"Old fixed rules, same 211 checks: 1 laundering payment found."**

**SAY:**
> Before GraphGuard, banks use **fixed rules**, like a checklist.
> For example: a payment just under 10,000. Or an account paying too many people in one day.
> Each rule looks at **one payment at a time.**
> But here, every criminal payment looks normal. The crime is only in the pattern.
> With the old fixed rules, in two days: 211 checks.
> **210 of them are innocent customers.** One criminal found.
> Two days of salaries, almost all wasted.

**DO:** Point at the green box **"167 laundering found"**, then **"44 false alarms"**.

**SAY:**
> With GraphGuard: the same 211 checks.
> **167 are real money laundering.** Only 44 false alarms.
> Same people. Same salaries. From **one** criminal found to **167**.

**DO:** Point at **"916 laundering missed"**.

**SAY:**
> And it shows what it still misses. No system catches everything. I don't hide it.

---

## Step 4: The list

**DO:** Scroll down slowly to **"The list: most suspicious payments first"**. Point at **"211 payments from 190 senders"**.

**SAY:**
> This is the investigator's list. Out of a million payments, the riskiest come first.
> Each one says **why** it was flagged, in plain words, and **when** it must be checked.

---

## Step 5: The investigator

**DO:** Scroll down to row **11** (Partnership #1332 → Small business #3159, 19,169.54 US Dollar). Click it.

**SAY:**
> Let's open one. Number 11.
> On the left: why it's here. Money moved on fast, less than a minute.
> Many different accounts paid the receiver.

**DO:** Scroll down slowly past **"AI draft, checked"** to **"The money around it"**. Click **"▶ Play all"**. Wait until it stops.

**SAY:**
> An AI writes the first report. Every fact links to a real payment.
> AI sometimes says things it can't back up, about 5 facts in 100.
> So my code checks every fact. Anything it can't prove is thrown out.
> Now the money picture. Each box is an account. Each arrow is a payment.
> Watch: many accounts pay in... and the money moves on.
> That's the pattern. No single payment shows it.

**DO:** Scroll back to the top. Click **"Suspicious"**. In the box, type:
*Money goes out to many accounts, then comes back together.*
Click the small grey **"Submit"** button, **not** the blue "Submit and next alert →" (the blue one jumps to the next case).

**SAY:**
> I decide: suspicious. I write my reason, because a bank must explain every decision.
> ...And I was right. This payment was money laundering.
> An AI also gives a second opinion: it looks for reasons I could be wrong.
> Here, it found none.
> **The AI helps. A person decides.**

---

## Step 6: The reviewer (four eyes)

**DO:** At the top, click **View as → "Reviewer"**.

**SAY:**
> In a bank, every decision gets a second look before it's final. It's called "four eyes".
> Here, Sam, a demo investigator, decided 8 alerts. Some are wrong.

**DO:** Click **#10** in the list.

**SAY:**
> Sam closed this one: "not enough evidence".
> But the AI second opinion says: this IS suspicious.
> And the money picture shows it too.

**DO:** In **"Your note"**, type: *Look at the money picture again.* Click **"Send back"**.

**SAY:**
> So I send it back to Sam, with a note.
> Every step is saved. Nothing is edited or deleted. A regulator can read why.

---

## Step 7: The manager

**DO:** At the top, click **View as → "Manager"**. Scroll down slowly to **"Backlog"**.

**SAY:**
> And the manager sees the whole team.
> What's decided. What's waiting. And the quality of the decisions.
> The backlog: about 200 open alerts, and most are already past their 24-hour check time.

**DO:** Scroll to **"Plan the team"**. Move the slider a little to the right, then back to 100.

**SAY:**
> And the manager can plan: more people, more checks, more crime found.
> 100 checks a day: about 5 people.

---

## Step 8: For the engineers

**DO:** Click **"GraphGuard"** at the top left to go home.

**SAY:**
> For the engineers: problem first, model second.
> I measured what the team really needs: when they check a payment, is it a real criminal?
> The old rules: right **less than 1 time in 100.**
> GraphGuard: right **about 79 times in 100.**
> I tested a neural network against a simpler model, XGBoost, with the same rules.
> **The neural network lost.** XGBoost found more than twice as many crime rings.
> So I shipped XGBoost, and wrote down why.
> Then I built it like production: Kafka, Kubernetes,
> almost every payment scored in under 15 milliseconds.
> I replayed over a million payments. Every score matched.

---

## Step 9: Goodbye

**DO:** Stay on the home page.

**SAY:**
> Try it yourself at **graphguard.lubobali.com**. The code is on GitHub.
> I'm Lubo Bali. Thanks for watching.

---

## Where each number comes from

| Said | Source |
|---|---|
| 1,015,300 payments, 1,083 laundering, in 2 days | the home page ("Over 2 days"); the validation window |
| 100 a day = about 5 people; 211 checks | the home page slider at 100 (`docs/analysis/s7.3-capacity.json`, k = 211) |
| 167 found, 44 false alarms, 916 missed | the same page and file (`system`, k = 211) |
| the rules: just under 10,000; paying too many people | `src/graphguard/demo/reasons.py` RULE_TEXT (structuring 9,000-9,999.99; fan out; velocity; fan in; new accounts), limits from training only |
| old rules: 1 found, so 210 innocent | the same file (`rules`, k = 211: 1 caught) |
| 211 payments from 190 senders | the list's header |
| #11 is laundering; #10 (Sam closed it) is laundering | the answer key (`/api/alerts/<id>/answer`), checked 2026-11-28 |
| about 5 in 100 AI facts | FINDING-019: 4.0% (DeepSeek) and 5.6% (Claude Sonnet) could not be proven before the checker |
| about 200 open, most past the check time | the manager page, Backlog (211 open / 147 past 24 h for a fresh visitor; one fewer after your decision) |
| right about 79 in 100 vs less than 1 in 100 | `s7.3-capacity.json` at k = 211: GraphGuard 167 / 211 = 79.1%, rules 1 / 211 = 0.5% |
| more than twice as many rings | `docs/model_comparison.md`: XGBoost 127 of 168, GraphSAGE 60 of 168 |
| almost every payment under 15 ms | FINDING-013: p99 13–15 ms (99 of 100) |
| over a million payments, every score matched | the overnight soak: 1,015,300 payments, 0 score mismatches |

The rules' 1 in 211 is on simulated data: the page itself says the simulator's launderers
rarely break simple rules ("Why so few?"). Say so if someone asks.
