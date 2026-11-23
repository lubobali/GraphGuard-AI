"""Why this alert, in plain words (S7.4).

One sentence per model feature, filled with that transaction's as-of value. The numbers
come from the feature vector the stream stored (what the model saw), plus the
transaction's own amount and currencies.

Two features are sums of earlier amounts across 15 currencies (no exchange rates exist in
the data), so they are never printed as money: they are said as a share of the window
("higher than in 97% of the payments in this window"), computed by the build over all
validation transactions.
"""

from __future__ import annotations

import math
from collections.abc import Callable

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _n(v: float) -> str:
    return f"{int(round(v)):,}"


def _payments(v: float) -> str:
    n = int(round(v))
    return f"{n:,} payment" + ("" if n == 1 else "s")


def _duration(seconds: float) -> str:
    s = int(seconds)
    for unit, size in (("day", 86_400), ("hour", 3_600), ("minute", 60)):
        if s >= size:
            q = s // size
            return f"{q} {unit}" + ("" if q == 1 else "s")
    return "less than a minute"


def _share(pct: float) -> str:
    return f"{int(pct)}%"


Template = Callable[[float, dict, dict], str]

TEMPLATES: dict[str, Template] = {
    "hour": lambda v, tx, p: f"Sent at {int(v):02d}:00.",
    # FINDING-018: a calendar pattern of the simulator, said so -- not hidden, not dressed up.
    "weekday": lambda v, tx, p: (
        f"Sent on a {WEEKDAYS[(int(v) - 1) % 7]} "
        "(a calendar pattern of the simulator, not a real warning sign; FINDING-018)."
    ),
    "log_amount": lambda v, tx, p: (
        f"The amount: {tx['amount_paid']:,.2f} {tx['payment_currency']}."
    ),
    "amount_ratio": lambda v, tx, p: (
        "Paid and received in the same currency."
        if tx["payment_currency"] == tx["receiving_currency"]
        else f"Paid in {tx['payment_currency']}, received in {tx['receiving_currency']}."
    ),
    "is_same_bank": lambda v, tx, p: (
        "Sender and receiver use the same bank."
        if v >= 0.5
        else "Sender and receiver use different banks."
    ),
    "payment_currency_code": lambda v, tx, p: f"Paid in {tx['payment_currency']}.",
    "sender_n_sent_before": lambda v, tx, p: (
        "This is the first payment we have seen from the sender."
        if v < 0.5
        else f"The sender had made {_payments(v)} before this one."
    ),
    "sender_amount_sent_before": lambda v, tx, p: (
        "How much the sender had sent before is higher than in "
        f"{_share(p['sender_amount_sent_before'])} of the payments in this window."
    ),
    "sender_distinct_out_before": lambda v, tx, p: (
        f"The sender had already paid {_n(v)} different account"
        + ("" if int(round(v)) == 1 else "s")
        + "."
    ),
    "sender_sent_last_24h": lambda v, tx, p: (
        f"The sender made {_payments(v)} in the 24 hours before this one."
    ),
    "sender_seconds_since_last_send": lambda v, tx, p: (
        "The sender had never sent a payment before."
        if v is None or (isinstance(v, float) and math.isnan(v))
        else f"The sender's previous payment was {_duration(v)} earlier."
    ),
    "receiver_n_received_before": lambda v, tx, p: (
        "This is the first payment we have seen to the receiver."
        if v < 0.5
        else f"The receiver had received {_payments(v)} before."
    ),
    "receiver_amount_received_before": lambda v, tx, p: (
        "How much the receiver had received before is higher than in "
        f"{_share(p['receiver_amount_received_before'])} of the payments in this window."
    ),
    "receiver_distinct_in_before": lambda v, tx, p: (
        f"The receiver had already been paid by {_n(v)} different account"
        + ("" if int(round(v)) == 1 else "s")
        + "."
    ),
    "in_out_ratio_before": lambda v, tx, p: (
        "The receiver gets many payments compared with how often the sender pays."
        if v >= 1
        else "The sender pays out much more often than the receiver gets paid."
    ),
}

# The rules' own definitions (stream/rules.py), in plain words.
RULE_TEXT: dict[str, str] = {
    "velocity": "Rule: the sender's payments in the last 24 hours are in the top 0.1%.",
    "fan_out": "Rule: the sender pays more different accounts than 99.9% of senders.",
    "fan_in": "Rule: the receiver is paid by more different accounts than 99.9% of receivers.",
    "structuring": "Rule: the amount is just under a reporting line (9,000 to 9,999.99).",
    "new_account_large": "Rule: a never-seen account with an amount in the top 1%.",
    "both_new": "Rule: both accounts have never been seen before (always reviewed).",
}


def sentence(feature: str, value: float, tx: dict, percentiles: dict) -> str:
    text = TEMPLATES[feature](value, tx, percentiles)
    return text[0].upper() + text[1:]


# S7.13: features that are simulator artifacts (FINDING-018). The model uses them, so their
# contribution stays in the numbers, but they are never given as a reason to investigate.
ARTIFACT_FEATURES = frozenset({"weekday"})


def top_features(contribs: dict[str, float], n: int = 3) -> list[str]:
    """The features that pushed the score UP the most (largest positive contributions),
    never a simulator artifact."""
    up = [(c, f) for f, c in contribs.items() if c > 0 and f not in ARTIFACT_FEATURES]
    return [f for c, f in sorted(up, key=lambda x: (-x[0], x[1]))[:n]]


# S7.13: the 15 features as 5 behaviours (like Google AML AI's "feature families"), each
# pointing at the history table where a person can check it.
FAMILIES: tuple[dict, ...] = (
    {"key": "speed", "label": "Money moved on fast", "look": "sender",
     "features": ("sender_seconds_since_last_send", "sender_sent_last_24h")},
    {"key": "receiver", "label": "Many payments into the receiver", "look": "receiver",
     "features": ("receiver_n_received_before", "receiver_distinct_in_before",
                  "receiver_amount_received_before", "in_out_ratio_before")},
    {"key": "sender", "label": "The sender's history", "look": "sender",
     "features": ("sender_n_sent_before", "sender_amount_sent_before",
                  "sender_distinct_out_before")},
    {"key": "payment", "label": "The payment itself", "look": None,
     "features": ("log_amount", "amount_ratio", "payment_currency_code", "is_same_bank",
                  "hour")},
    {"key": "calendar", "label": "Simulator calendar effect (not a reason to investigate)",
     "look": None, "features": ("weekday",)},
)  # fmt: skip


def groups(contribs: dict[str, float], values: dict, tx: dict, percentiles: dict) -> list[dict]:
    """Each behaviour with its summed contribution (log-odds; all groups together equal the
    raw contributions) and its sentences. Pushes up first (largest first), then the ones
    against, the artifact family always last."""
    out = []
    for fam in FAMILIES:
        feats = [f for f in fam["features"] if f in contribs]
        if not feats:
            continue
        total = float(sum(contribs[f] for f in feats))
        artifact = all(f in ARTIFACT_FEATURES for f in feats)
        out.append({
            "key": fam["key"], "label": fam["label"], "look": fam["look"],
            "contribution": total, "features": feats,
            "direction": "artifact" if artifact else ("up" if total > 0 else "against"),
            # strongest feature first inside the group
            "sentences": [sentence(f, values[f], tx, percentiles)
                          for f in sorted(feats, key=lambda f: -abs(contribs[f]))],
        })  # fmt: skip
    rank = {"up": 0, "against": 1, "artifact": 2}
    return sorted(
        out,
        key=lambda g: (rank[g["direction"]], -g["contribution"] if g["direction"] == "up"
                       else g["contribution"]),
    )  # fmt: skip
