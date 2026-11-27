# GraphGuard demo video: the script (S8b.6)

About **2½–3 minutes** (~370 words, read slowly). Screen + your voice. No face needed.

**How to read it:** **CLICK** = what you do. **SAY** = what you read out loud.
Short pauses are fine. Read slowly. If you make a mistake, keep going: small mistakes sound real.

Every number below was checked on the live site on 2026-11-27.

---

## 1. The hook (0:00 – 0:15)

**CLICK:** Start on the home page, https://graphguard.lubobali.com. Don't move yet.

**SAY:**
> Money laundering hides in plain sight.
> The crime is in the **shape**: how the money moves between accounts.
> I built GraphGuard to find that shape.
> Quick note: the data is synthetic, from IBM's simulator. No real people, no real banks.

---

## 2. The big number (0:15 – 0:45)

**CLICK:** Move your mouse over the slider: "Your team checks the top 100 payments a day".

**SAY:**
> A bank can't check a million payments.
> So GraphGuard scores every one, and puts the riskiest on top.
> Five people, 100 checks a day.
> In two days, that's 211 checks, and **167 of them are real laundering.**

**CLICK:** Point at the line "Old fixed rules, same 211 checks: 1 laundering payment found."

**SAY:**
> The old fixed rules, with the same 211 checks?
> They find... **one.**

**CLICK:** Point at the box "916 laundering missed".

**SAY:**
> And I show what it misses, too. No system finds it all.

---

## 3. You are the investigator (0:45 – 1:40)

**CLICK:** The blue button **"Try one case — 2 minutes"**.

**SAY:**
> Now, you are the investigator.
> This payment: 9,539 euros, just under a reporting line.

**CLICK:** **"Play all"**. Wait until the arrows stop.

**SAY:**
> Each box is an account. Each arrow is a payment.

**CLICK:** **"I've looked: decide →"**, then **"Suspicious"**.

**SAY:**
> I say: suspicious.
> ...And I was right.
> The red arrows are the scheme: money split out to many accounts, then collected again.

**CLICK:** **"What does the AI say? →"**

**SAY:**
> My favorite part: an AI reads the same payments, and **argues against me.**
> Every fact it says is checked by code, against the real payments.
> This time, the AI is wrong. And that's the point:
> **the AI helps. A person decides.**

---

## 4. The real tool (1:40 – 2:10)

**CLICK:** **"See the full tool: the whole list, worst first"**. Scroll down to the list. Click **#1**.

**SAY:**
> The full tool. Alert number one, and why, in plain words.

**CLICK:** Scroll down slowly to **"AI draft, checked"**.

**SAY:**
> An AI writes the first draft. Every fact links to its payment.
> If the AI says something the data can't prove, the code throws it out.
> Before the check, about 5 in 100 AI facts could not be proven.
> After the check: **zero** reach the screen.

---

## 5. The manager (2:10 – 2:20)

**CLICK:** At the top, **View as → "Manager"**.

**SAY:**
> And the manager sees the whole team:
> what's open, what's late, and how many people they need.

---

## 6. The honest part, and goodbye (2:20 – 2:45)

**CLICK:** Click **"GraphGuard"** (top left) to go back home.

**SAY:**
> One honest result.
> I also built a graph neural network. **It lost.** XGBoost found 127 of 168 laundering rings. The neural network found 60.
> I wrote that down. I didn't hide it.
>
> Under the hood: Kafka, Kubernetes, 99 of 100 scores in under 15 milliseconds,
> and over a million payments replayed with every score matching the offline test.
>
> Try it yourself at **graphguard.lubobali.com**. The code is on GitHub.
> I'm Lubo Bali. Thanks for watching.

---

## Where each number comes from

| Said | Source |
|---|---|
| 211 checks, 167 found, 916 missed | the home page at 100 a day (`docs/analysis/s7.3-capacity.json`) |
| old rules find 1 | the same page, "Old fixed rules" |
| 9,539 euros, 9,000–9,999.99 line | /try case 1 |
| about 5 in 100 AI facts | FINDING-019: 4.0% (DeepSeek) and 5.6% (Claude Sonnet) before the checker |
| 127 vs 60 of 168 rings | `docs/model_comparison.md` |
| 99 of 100 under 15 ms | FINDING-013: p99 13–15 ms |
| over a million payments, every score matched | the overnight soak: 1,015,300 payments, 0 score mismatches |
