"""The claim checker (S7.10): deterministic, and the only judge of what the agent may say.

A claim is supported only if every id it cites is in the evidence the tools returned, and
every amount, time, relation and count it states matches the cited records -- and every
number written in its prose appears in a cited record (amount or time). No LLM judges here.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

TYPOLOGIES = ("FAN-OUT", "FAN-IN", "CYCLE", "GATHER-SCATTER", "SCATTER-GATHER", "STACK",
              "BIPARTITE", "RANDOM", "none evident")  # fmt: skip
_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


@dataclass
class Verdict:
    supported: bool
    why: str = ""


def _numbers_in(rec: dict) -> set[float]:
    """Numbers a claim may write about this payment: its amount, its time's parts, and the
    numbers inside its account names ("Corporation #35871" is a name, not an amount)."""
    out = {round(float(rec["amount"]), 2)}
    for field in ("t", "from", "to"):
        for part in re.findall(r"\d+", str(rec.get(field) or "")):
            out.add(float(part))
    return out


def check_claim(claim: dict, evidence: dict[int, dict]) -> Verdict:
    cites = claim.get("cites") or []
    if not cites:
        return Verdict(False, "cites nothing")
    missing = [c for c in cites if c not in evidence]
    if missing:
        return Verdict(False, f"cites ids not in the evidence: {missing}")
    recs = [evidence[c] for c in cites]
    if (a := claim.get("amount")) is not None and not any(
        abs(r["amount"] - float(a["value"])) < 0.01 and r["currency"] == a.get("currency")
        for r in recs
    ):
        return Verdict(False, f"amount {a} matches no cited payment")
    if (t := claim.get("time")) is not None and not any(r["t"][:16] == str(t)[:16] for r in recs):
        return Verdict(False, f"time {t} matches no cited payment")
    if (rel := claim.get("relation")) is not None and not any(
        r["from"] == rel.get("from") and r["to"] == rel.get("to") for r in recs
    ):
        return Verdict(False, f"relation {rel} matches no cited payment")
    if (n := claim.get("count")) is not None and int(n) != len(set(cites)):
        return Verdict(False, f"says {n}, cites {len(set(cites))}")
    allowed = set().union(*(_numbers_in(r) for r in recs)) | {float(len(set(cites)))}
    for raw in _NUM.findall(claim.get("text", "")):
        v = float(raw.replace(",", ""))
        if v <= 24 and float(v).is_integer():  # small counts and hours ("two", "1 hour")
            continue
        if round(v, 2) not in allowed:
            return Verdict(False, f"number {raw} in the text is in no cited payment")
    return Verdict(True)


def check_report(report: dict, evidence: dict[int, dict]) -> dict:
    kept, dropped = [], []
    for claim in report.get("claims", []):
        v = check_claim(claim, evidence)
        (kept if v.supported else dropped).append(claim if v.supported else {**claim, "why": v.why})
    typology = report.get("typology")
    return {
        "summary": report.get("summary", ""),
        "typology": typology if typology in TYPOLOGIES else "none evident",
        "kept": kept,
        "dropped": dropped,
        "n_claims": len(kept) + len(dropped),
        "n_unsupported": len(dropped),
    }


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson interval for a rate k/n (honest at 0 and with small n)."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))
