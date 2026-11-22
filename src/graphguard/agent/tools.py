"""The agent's tools (S7.10): read-only, through demo_reader, never the answer key.

Each returns plain JSON-able data. `evidence()` turns what the tools returned into the
records the checker verifies claims against -- the agent can only cite what it was shown.
"""

from __future__ import annotations

TOOLS = ("get_alert", "get_reasons", "get_ring", "get_history")


def _alert(repo, event_id: int) -> dict:
    a = repo.alert(int(event_id))
    if a is None:
        raise KeyError(f"no transaction {event_id} in the demo window")
    return a


def get_alert(repo, event_id: int) -> dict:
    a = _alert(repo, event_id)
    keys = (
        "event_id",
        "event_time",
        "from_name",
        "from_bank_name",
        "to_name",
        "to_bank_name",
        "amount_paid",
        "payment_currency",
        "amount_received",
        "receiving_currency",
        "payment_format",
        "rank",
        "percentile",
        "cold_policy",
        "rules",
        "rule_text",
    )
    return {k: a[k] for k in keys}


def get_reasons(repo, event_id: int) -> dict:
    a = _alert(repo, event_id)
    return {"reasons": a["reasons"], "contributions": (a["contributions"] or [])[:8]}


def get_ring(repo, event_id: int) -> dict:
    return _alert(repo, event_id)["ring"]


def get_history(repo, event_id: int) -> dict:
    return _alert(repo, event_id)["history"]


def evidence(repo, event_id: int) -> dict[int, dict]:
    """Every payment the tools can show for this alert, keyed by transaction id."""
    a = _alert(repo, event_id)
    out = {
        a["event_id"]: {
            "id": a["event_id"],
            "from": a["from_name"],
            "to": a["to_name"],
            # the ring tool names accounts by id ("bank:account") as well as by name
            "from_id": f"{int(a['from_bank'])}:{a['from_account']}",
            "to_id": f"{int(a['to_bank'])}:{a['to_account']}",
            "from_bank": a["from_bank_name"],
            "to_bank": a["to_bank_name"],
            "rules": " ".join(a["rule_text"] or []),  # get_alert shows the rules' own words
            "amount": float(a["amount_paid"]),
            "currency": a["payment_currency"],
            "t": str(a["event_time"])[:16].replace("T", " "),
        }
    }
    ring = a["ring"] or {"nodes": [], "edges": []}
    names = {n["id"]: n.get("name") or n["id"] for n in ring["nodes"]}
    banks = {n["id"]: n.get("bank") for n in ring["nodes"]}
    # history rows carry names only; give them the ring's id where that name is unambiguous
    by_name: dict[str, list[str]] = {}
    for n in ring["nodes"]:
        by_name.setdefault(names[n["id"]], []).append(n["id"])
    id_of = {name: ids[0] for name, ids in by_name.items() if len(ids) == 1}
    for e in ring["edges"]:
        out.setdefault(
            e["id"],
            {
                "id": e["id"],
                "from": names[e["from"]],
                "to": names[e["to"]],
                "from_id": e["from"],
                "to_id": e["to"],
                "from_bank": banks.get(e["from"]),
                "to_bank": banks.get(e["to"]),
                "amount": float(e["amount"]),
                "currency": e["currency"],
                "t": e["t"][:16],
            },
        )
    for side in ("from", "to"):
        for h in a["history"][side]:
            out.setdefault(
                h["event_id"],
                {
                    "id": h["event_id"],
                    "from": h["from_name"],
                    "to": h["to_name"],
                    "from_id": id_of.get(h["from_name"]),
                    "to_id": id_of.get(h["to_name"]),
                    "amount": float(h["amount_paid"]),
                    "currency": h["payment_currency"],
                    "t": str(h["event_time"])[:16].replace("T", " "),
                },
            )
    return out
