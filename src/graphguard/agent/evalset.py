"""The agent's eval set (S7.10): 5 alerts per ring type + 24 clean, from the top 5,000 of
the validation queue, seeded. Ids and expected answers only -- the expected answer comes from
the answer key, which no tool can reach.

    python -m graphguard.agent.evalset            # writes docs/analysis/s7.10-evalset.json
    python -m graphguard.agent.evalset baseline   # scores the template baseline on it
    python -m graphguard.agent.evalset fresh      # set 2: 64 new alerts, none of set 1's
"""

from __future__ import annotations

import json
import random
import sys

from graphguard.config import REPO_ROOT, SEED

OUT = REPO_ROOT / "docs" / "analysis" / "s7.10-evalset.json"
# Set 2 (fresh): drawn after the checker was fixed on set 1, with none of set 1's alerts,
# and judged by the checker frozen at that commit -- the clean measurement (FINDING-019).
OUT2 = REPO_ROOT / "docs" / "analysis" / "s7.10-evalset-2.json"
SEED2 = SEED + 1
PER_TYPE, CLEAN = 5, 24


def build(repo, seed: int = SEED, exclude: frozenset = frozenset()) -> dict:
    rows = repo._all(
        "SELECT t.event_id, tr.is_laundering, tr.pattern_type FROM transactions t "
        "JOIN truth tr USING (event_id) JOIN subgraphs s USING (event_id) "
        "WHERE t.rank <= 5000 ORDER BY t.event_id"
    )
    rows = [r for r in rows if r["event_id"] not in exclude]
    rng = random.Random(seed)
    by_type: dict[str, list[int]] = {}
    clean = []
    for r in rows:
        if r["pattern_type"]:
            by_type.setdefault(r["pattern_type"], []).append(r["event_id"])
        elif not r["is_laundering"]:
            clean.append(r["event_id"])
    cases = [
        {"event_id": e, "expected": t}
        for t in sorted(by_type)
        for e in sorted(rng.sample(by_type[t], PER_TYPE))
    ]
    cases += [{"event_id": e, "expected": "none evident"} for e in sorted(rng.sample(clean, CLEAN))]
    return {"seed": seed, "per_type": PER_TYPE, "clean": CLEAN, "cases": cases}


def score(repo, cases: list[dict], make_report) -> dict:
    from graphguard.agent import checker, tools

    n_claims = n_bad = ring_hit = ring_n = none_hit = none_n = 0
    for c in cases:
        out = checker.check_report(
            make_report(repo, c["event_id"]), tools.evidence(repo, c["event_id"])
        )
        n_claims += out["n_claims"]
        n_bad += out["n_unsupported"]
        if c["expected"] == "none evident":
            none_n += 1
            none_hit += out["typology"] == "none evident"
        else:
            ring_n += 1
            ring_hit += out["typology"] == c["expected"]
    lo, hi = checker.wilson(n_bad, n_claims)
    return {
        "cases": len(cases),
        "claims": n_claims,
        "unsupported": n_bad,
        "unsupported_rate": n_bad / n_claims if n_claims else 0.0,
        "unsupported_rate_95ci": [round(lo, 4), round(hi, 4)],
        "ring_type_recall": f"{ring_hit} of {ring_n}",
        "none_evident_correct": f"{none_hit} of {none_n}",
    }


def main(argv: list[str]) -> int:
    from graphguard.demo.queries import PgRepo

    repo = PgRepo()
    if len(argv) > 1 and argv[1] == "baseline":
        from graphguard.agent import template

        cases = json.loads(OUT.read_text())["cases"]
        result = {
            "reporter": "template baseline (code, no LLM)",
            **score(repo, cases, template.report),
        }
        (REPO_ROOT / "docs" / "analysis" / "s7.10-baseline.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps(result, indent=2))
        return 0
    if len(argv) > 1 and argv[1] == "fresh":
        first = frozenset(c["event_id"] for c in json.loads(OUT.read_text())["cases"])
        data = build(repo, SEED2, first)
        OUT2.write_text(json.dumps(data, indent=2) + "\n")
        print(f"{len(data['cases'])} fresh cases -> {OUT2.relative_to(REPO_ROOT)}")
        return 0
    data = build(repo)
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(f"{len(data['cases'])} cases -> {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
