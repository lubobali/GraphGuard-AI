"""The case workflow (S7.15), pure: states, who may do what, reasons, repeats.

A case is one alert for one owner: each visitor has their own cases, so nobody locks an
alert for anyone else. Rows are append-only (`case_actions`); the state is always computed
from them, never stored.

    new --(escalate | close)--> awaiting_review --approve--> escalated | closed
                                      |  ^
                               send_back  (escalate | close: a changed decision, a new row)
                                      v  |
                                   sent_back

After the end, a new decision reopens the case (another row). A reviewer may review their
own case in the demo (labelled: in a bank this must be another person) or the seeded
decisions of "Sam", the demo investigator, so a first-time reviewer has real work.
"""

from __future__ import annotations

import datetime as dt
import random

DEMO = "demo"  # the case owner of Sam's seeded decisions
CLOSE_CODES = {
    "explained": "Explained by normal activity",
    "duplicate": "Duplicate of another alert",
    "insufficient": "Not enough evidence",
    "other": "Other",
}
INVESTIGATOR_ACTIONS = {"escalate", "close"}
REVIEWER_ACTIONS = {"approve", "send_back"}
MAX_REASON = 500
SAR_DAYS = 30  # FinCEN SAR FAQ (Oct 2025): 30 calendar days from detection

# Sam's decisions (event id, action, code, reason, matches the answer key). Chosen
# 2026-11-23 from the top 60 alerts with the answer key, so that 3 are WRONG and a reviewer
# has real mistakes to catch; the agent and the model never see this list.
DEMO_CASES: tuple[tuple[int, str, str | None, str, bool], ...] = (
    (2176404, "escalate", None,
     "Ten accounts paid the receiver within days; money moved on in minutes.", True),
    (2332851, "escalate", None,
     "Money split to several accounts, then collected in one German account.", True),
    (2192360, "escalate", None,
     "The money came back round to an account it started near.", True),
    (3016188, "escalate", None,
     "A group of accounts paying another group, all within hours.", True),
    (3067683, "close", "explained",
     "A normal supplier payment; the receiver is paid by many clients.", True),
    (2485818, "escalate", None, "Sent fast after receiving; looks like a pass-through.", False),
    (2273065, "close", "insufficient", "Only one earlier payment; not enough to say.", False),
    (3459511, "close", "explained",
     "Regular-looking amount between two small businesses.", False),
)  # fmt: skip


def demo_history(event_id: int) -> list[dict]:
    """Sam's seeded row for one alert (empty if Sam did not decide it)."""
    for eid, action, code, reason, _ in DEMO_CASES:
        if eid == event_id:
            return [{"actor": DEMO, "case_owner": DEMO, "role": "investigator", "action": action,
                     "code": code, "reason": reason, "at": None}]  # fmt: skip
    return []


def visible(rows: list[dict], owner: str, viewer: str) -> list[dict]:
    """The rows of `owner`'s case that `viewer` sees: all of their own case; of Sam's case,
    only their own reviews (each reviewer has a private copy of Sam's queue)."""
    if owner == DEMO:
        return [r for r in rows if r["case_owner"] == DEMO and r["actor"] == viewer]
    return [r for r in rows if r["case_owner"] == owner]


def case_state(history: list[dict]) -> dict:
    s = {"state": "new", "decision": None, "code": None, "reason": None, "decided_at": None,
         "final_at": None, "sar_due": None}  # fmt: skip
    for r in history:
        a, at = r["action"], r.get("at")
        if a in INVESTIGATOR_ACTIONS:
            s.update(
                state="awaiting_review",
                decision=a,
                code=r.get("code"),
                reason=r.get("reason"),
                decided_at=at,
                final_at=None,
                sar_due=None,
            )
        elif a == "approve" and s["state"] == "awaiting_review":
            final = "escalated" if s["decision"] == "escalate" else "closed"
            due = at + dt.timedelta(days=SAR_DAYS) if final == "escalated" and at else None
            s.update(state=final, final_at=at, sar_due=due)
        elif a == "send_back" and s["state"] == "awaiting_review":
            s.update(state="sent_back", decision=None, code=None)
    return s


def allowed(state: str, role: str) -> set[str]:
    if role == "investigator":
        return set(INVESTIGATOR_ACTIONS)  # new, sent back, a change, or a reopen
    if role == "reviewer" and state == "awaiting_review":
        return set(REVIEWER_ACTIONS)
    return set()


def problem(action: str, code: str | None, reason: str) -> str | None:
    """What is wrong with an action's fields, or None."""
    if action == "close" and code is None:
        return "a close needs a code"
    if action == "close" and code not in CLOSE_CODES:
        return "unknown close code"
    if action != "close" and code is not None:
        return "only a close has a code"
    if action != "approve" and not reason.strip():
        return "a reason is required"
    if len(reason) > MAX_REASON:
        return f"the reason is longer than {MAX_REASON} characters"
    return None


def is_repeat(history: list[dict], actor: str, action: str, code: str | None, reason: str) -> bool:
    mine = [r for r in history if r["actor"] == actor]
    return bool(mine) and (mine[-1]["action"], mine[-1].get("code"), mine[-1].get("reason")) == (
        action, code, reason)  # fmt: skip


def check(history, actor, owner, role, action, code, reason) -> str | None:
    """Why this action may not be stored, or None."""
    if role == "investigator" and owner != actor:
        return "an investigator decides only their own cases"
    if role == "reviewer" and owner not in (actor, DEMO):
        return "a reviewer reviews only their own cases or Sam's"
    if action not in allowed(case_state(history)["state"], role):
        return f"{action} is not allowed now"
    return problem(action, code, reason)


def score(cases: list[dict]) -> dict:
    """Training feedback: decisions that match the answer key (escalate = laundering), and
    how often the model's flag itself was right on the same cases."""
    decided = [c for c in cases if c["decision"]]
    return {
        "decided": len(decided),
        "right": sum((c["decision"] == "escalate") == c["is_laundering"] for c in decided),
        "model_right": sum(bool(c["is_laundering"]) for c in decided),
    }


# ---- S7.16: the manager's numbers ---------------------------------------------------------


def metrics(cases: list[dict], reviews_done: int) -> dict:
    """Counts for the manager's page. `cases`: state, decision (latest), is_laundering and
    ai_leans_suspicious (the AI draft named a pattern; None when there is no draft)."""
    decided = [c for c in cases if c["decision"]]
    with_ai = [c for c in decided if c.get("ai_leans_suspicious") is not None]
    return {
        "decided": len(decided),  # a case sent back has no current decision
        "escalated": sum(c["decision"] == "escalate" for c in decided),
        "closed": sum(c["decision"] == "close" for c in decided),
        "waiting_review": sum(c["state"] == "awaiting_review" for c in cases),
        "sent_back": sum(c["state"] == "sent_back" for c in cases),
        "final_escalated": sum(c["state"] == "escalated" for c in cases),
        "final_closed": sum(c["state"] == "closed" for c in cases),
        "reviews_done": reviews_done,
        "matched": sum((c["decision"] == "escalate") == bool(c["is_laundering"]) for c in decided),
        "model_right": sum(bool(c["is_laundering"]) for c in decided),
        "ai_strong_against": {  # S7.17: the AI second reviewer found a strong case against
            "cases": sum(c.get("ai_strong_against") is not None for c in decided),
            "strong": sum(c.get("ai_strong_against") is True for c in decided),
        },
        "ai_agreement": {
            "cases": len(with_ai),
            "agree": sum(
                (c["decision"] == "escalate") == c["ai_leans_suspicious"] for c in with_ai
            ),
        },
    }


def backlog(undecided: list[dict], as_of: dt.datetime) -> dict:
    """Undecided alerts by age at `as_of` (the data's clock: the window's end)."""
    ages = [(as_of - r["event_time"]).total_seconds() / 3600 for r in undecided]
    return {
        "total": len(ages),
        "under_24h": sum(a < 24 for a in ages),
        "h24_48": sum(24 <= a < 48 for a in ages),
        "over_48h": sum(a >= 48 for a in ages),
        "oldest": min((r["event_time"] for r in undecided), default=None),
    }


def qa_sample(closed: list[dict], seed: str, n: int = 5) -> list[dict]:
    """Quality assurance: a fixed random sample of closed cases, re-checked blind against
    the answer key (a close is right when the payment was not laundering)."""
    pool = sorted(closed, key=lambda c: c["event_id"])
    picked = random.Random(seed).sample(pool, min(n, len(pool)))
    return [
        {**c, "ok": not c["is_laundering"]} for c in sorted(picked, key=lambda c: c["event_id"])
    ]
