# ADR 0007 — How rules and the model combine into one alert queue

**Status:** accepted, 2026-11-21 (S6.8)
**Decided by:** Lubo approved S6.8 (rules next to the model, a written combination policy);
the measurement is FINDING-016.

## Context

Fraud/AML systems are hybrids: deterministic rules (explainable, expected by regulators — the
UK FCA asks firms to measure and tune monitoring thresholds), an ML score, and a capacity-
limited investigator queue. The consumer scores every transaction; it needs one rule for
which ones become alerts and in what order.

## Decision

- **Rules** (`src/graphguard/stream/rules.py`): velocity, fan-out, fan-in, structuring,
  new account + large amount, both accounts new. Only as-of inputs — the same before-state
  the model sees — so they run live, and offline on the same features give the same answer
  (the e2e check compares both for every transaction).
- **Thresholds from the training window only** (quantiles), generated into
  `stream/rule_thresholds.py`, committed and shipped in the image. Never tuned on validation.
- **Queue order** `priority(score, rules)`: a hard rule (`both_new`, FINDING-014) or two rules
  at once go above every model-only alert; otherwise the model score decides.
- **The alert line** is the priority at rank 5,000 on validation — an investigator capacity
  of ~5,000 alerts per ~50 hours of traffic (the project's k). Each alert carries `reasons`
  (the rules that fired, or "model score") and goes to the `alerts` topic through the
  outbox, in the same transaction as its decision.

## Measured (FINDING-016)

Rules alone: p@5000 0.0042 (21 launderers). Model alone: 0.1084 (542). Combined: 0.1084 at
k, PR-AUC 0.262 vs 0.282 — the override reorders the long tail, not the queue.

## Consequences

- On AMLworld the rules are a safety net and a baseline, not a source of alerts; the queue is
  the model's. This is stated, not hidden.
- Changing a threshold or the capacity = rerun `python -m graphguard.stream.rules`, commit the
  generated module, rebuild the image.
- Champion/challenger (S6.10) compares models under this same policy.

## Alternatives rejected

- **Rules fire alerts on their own regardless of score** — floods the queue with ~1%
  structuring hits at 0.34% precision.
- **Per-account / peer-group thresholds** — better rules, but that is tuning; a later step,
  measured on its own.

**Update 2026-11-22 (S7.3):** at a small team size the override costs a little. With a
100-alerts-a-day team (k = 211 over the window) the combined queue catches 167 laundering
transactions against 170 for the model alone; at k = 5,000 both catch 542
(`docs/analysis/s7.3-capacity.json`). The override stays (it carries FINDING-014's hard
rule), and the screen shows the system's own numbers, not the model's.
