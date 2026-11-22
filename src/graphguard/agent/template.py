"""The template baseline (S7.10): the same report shape, built by code. Supported by
construction; its ring type is a shape heuristic. The LLM must beat it to earn its place."""

from __future__ import annotations

from graphguard.agent.tools import _alert


def ring_type(ring: dict) -> str:
    edges = ring["edges"]
    seeds = {n["seed"]: n["id"] for n in ring["nodes"] if n.get("seed")}
    s, r = seeds.get("sender"), seeds.get("receiver")
    if any(e["role"] == "downstream 2" and e["to"] == s for e in edges):
        return "CYCLE"
    out_s = {e["to"] for e in edges if e["from"] == s}
    in_r = {e["from"] for e in edges if e["to"] == r}
    in_s = {e["from"] for e in edges if e["to"] == s}
    out_r = {e["to"] for e in edges if e["from"] == r}
    if len(in_s) >= 2 and len(out_r) >= 2:
        return "GATHER-SCATTER"
    if len(out_s) >= 3:
        return "FAN-OUT"
    if len(in_r) >= 3:
        return "FAN-IN"
    return "none evident"


def report(repo, event_id: int) -> dict:
    a = _alert(repo, event_id)
    ring = a["ring"] or {"nodes": [], "edges": []}
    eid = a["event_id"]
    claims = [
        {
            "text": f"{a['from_name']} paid {a['to_name']} {a['amount_paid']:,.2f} "
            f"{a['payment_currency']}.",
            "cites": [eid],
            "amount": {"value": a["amount_paid"], "currency": a["payment_currency"]},
            "relation": {"from": a["from_name"], "to": a["to_name"]},
        }
    ]
    seeds = {n["seed"]: n["id"] for n in ring["nodes"] if n.get("seed")}
    payees = [e["id"] for e in ring["edges"] if e["from"] == seeds.get("sender") and e["id"] != eid]
    if payees:
        claims.append(
            {
                "text": f"The sender made {len(payees)} other payments in the drawn window.",
                "cites": payees,
                "count": len(payees),
            }
        )
    payers = [e["id"] for e in ring["edges"] if e["to"] == seeds.get("receiver") and e["id"] != eid]
    if payers:
        claims.append(
            {
                "text": f"The receiver got {len(payers)} other payments in the drawn window.",
                "cites": payers,
                "count": len(payers),
            }
        )
    return {"summary": " ".join(a["reasons"] or []), "typology": ring_type(ring), "claims": claims}
