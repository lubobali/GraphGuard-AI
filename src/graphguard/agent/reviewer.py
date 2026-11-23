"""The AI second reviewer (S7.17): it argues AGAINST the person's decision.

    python -m graphguard.agent.reviewer run --model M --set 2        # measure (both directions)
    python -m graphguard.agent.reviewer publish                       # s7.17-reviewer.json
    python -m graphguard.agent.reviewer demo --model M --top 400      # precompute for the site
    python -m graphguard.agent.reviewer store                         # into demo.ai_reviews

Banks use AI to draft and assist; this one challenges a decision a person already made, with
facts the frozen S7.10 checker can match to payments. The same loop and the same four
read-only tools as the investigator (bound to one alert, no id argument); it never sees the
simulator's labels. It is shown only AFTER the person decides, so it cannot anchor them.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field

from graphguard.agent import checker, tools
from graphguard.agent.llm import (
    SPEND_CAP,
    SpendCapReached,
    Usage,
    _compact,
    _key,
    _ratio,
    _slug,
    http_post,
)
from graphguard.agent.llm import Investigator as _Loop
from graphguard.config import REPO_ROOT

__all__ = ["SpendCapReached", "Reviewer", "ask", "checked", "summarize", "stored_rows"]

RUNS_DIR = REPO_ROOT / "docs" / "analysis" / "s7.17-runs"
OUT = REPO_ROOT / "docs" / "analysis" / "s7.17-reviewer.json"
DIRECTIONS = ("escalate", "close")
STRENGTHS = ("strong", "some", "none")

SYSTEM = """You are a second reviewer in an anti-money-laundering team. The data is synthetic
(IBM AMLworld simulator); names are synthetic. An investigator has ALREADY decided one alerted
payment. Your job is not to decide again: find the strongest facts AGAINST their decision, so
they can check before the case is final. If there is no real case against it, say so.

Use the tools to look at the alert, the model's reasons, the money flow around it (only
payments BEFORE the alert, 72 hours, at most 6 per account and direction; "more" counts what
was cut) and both accounts' earlier payments.

Then reply with ONLY one JSON object, no other text:
{"strength": "strong" | "some" | "none"   (how strong the case against the decision is),
 "summary": "1-2 plain sentences: the case against the decision",
 "claims": [{"text": "one fact in plain words",
             "cites": [transaction ids that show it],
             "amount": {"value": number, "currency": "..."} or null,
             "time": "YYYY-MM-DD HH:MM" or null,
             "relation": {"from": "payer name or id", "to": "payee name or id"} or null,
             "count": number or null}]}

Against an ESCALATE decision, look for signs of ordinary activity: a regular counterparty,
steady amounts, no money moving on, no split-and-gather shape. Against a CLOSE decision, look
for laundering shapes: money split to many accounts or gathered from many, passed on quickly,
returning in a circle, layers of accounts.

Rules: every claim cites only transaction ids you were shown. A claim's amount, time,
relation and count must match the cited payments exactly (a count is the number of ids
cited). Do not write numbers that are not in the cited payments. Amounts are in many
currencies: never add them up. "none" with no claims is a good reply when nothing argues
against the decision."""

EMPTY = {"strength": "none", "summary": "", "claims": []}


def ask(event_id: int, decision: str) -> str:
    if decision not in DIRECTIONS:
        raise ValueError(f"decision must be one of {DIRECTIONS}")
    said = "ESCALATE (suspicious)" if decision == "escalate" else "CLOSE (not suspicious)"
    return (f"The investigator decided to {said} on alert {event_id} ({decision}). "
            "Find the strongest facts AGAINST that decision.")  # fmt: skip


def malformed(claim) -> str | None:
    """Why a claim's shape is not the one the prompt asks for, or None. Checked before the
    frozen checker, which assumes the shape (Sonnet once wrote "amount": 9500.0)."""
    if not isinstance(claim, dict):
        return "malformed: not an object"
    if not isinstance(claim.get("cites"), list):
        return "malformed: cites is not a list"
    a = claim.get("amount")
    if a is not None and not (isinstance(a, dict) and isinstance(a.get("value"), int | float)):
        return "malformed: amount is not {value, currency}"
    if (r := claim.get("relation")) is not None and not isinstance(r, dict):
        return "malformed: relation is not {from, to}"
    n = claim.get("count")
    if n is not None and not (isinstance(n, int | float) or str(n).isdigit()):
        return "malformed: count is not a number"
    if (t := claim.get("time")) is not None and not isinstance(t, str):
        return "malformed: time is not text"
    return None


def checked(raw: dict, evidence: dict[int, dict]) -> dict:
    """The review after the frozen checker: kept and dropped claims, a known strength. A claim
    in the wrong shape is dropped (unsupported) before the checker sees it."""
    claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    bad = [(c, w) for c in claims if (w := malformed(c))]
    good = [c for c in claims if not malformed(c)]
    out = checker.check_report({**raw, "claims": good, "typology": None}, evidence)
    out.pop("typology")
    out["dropped"] = [{**c, "why": w} if isinstance(c, dict) else {"text": str(c), "why": w}
                      for c, w in bad] + out["dropped"]  # fmt: skip
    out["n_claims"] += len(bad)
    out["n_unsupported"] += len(bad)
    s = str(raw.get("strength") or "").strip().lower()
    return {"strength": s if s in STRENGTHS else "none", **out}


@dataclass
class Reviewer:
    model: str
    post: object
    spend_cap: float = 1.0
    usage: Usage = field(default_factory=Usage)

    def review(self, repo, event_id: int, decision: str) -> tuple[dict, dict]:
        loop = _Loop(self.model, self.post, self.spend_cap, self.usage)
        raw, trace = loop.report(repo, event_id, system=SYSTEM, ask=ask(event_id, decision),
                                 empty=EMPTY)  # fmt: skip
        return checked(raw, tools.evidence(repo, event_id)), {**trace, "raw": raw}


# --- running, measuring, storing ------------------------------------------------------------
def _post_fn():
    key = _key()

    def post(body):
        return http_post(body, key)

    return post


def run(
    model: str,
    cases: list[dict],
    repo=None,
    post=None,
    cap: float | None = None,
    save=None,
    resume: dict | None = None,
) -> dict:
    """Both directions for every case. `cases` carry `laundering` only for measuring; the
    reviewer itself is never given it. `save(out)` is called after every review, so a crash
    loses nothing; `resume` (an earlier output) skips the reviews it holds, and its cost
    counts toward the cap. Any error stops the run with what it has."""
    if repo is None:
        from graphguard.demo.queries import PgRepo

        repo = PgRepo()
    rv = Reviewer(model, post or _post_fn(), cap or SPEND_CAP.get(model, 1.0))
    rows = list((resume or {}).get("rows", []))
    if resume:
        rv.usage = Usage(**resume["usage"])
    done = {(int(r["event_id"]), r["direction"]) for r in rows}

    def out(**extra):
        keep = {k: v for k, v in (resume or {}).items() if k == "note"}  # how it was rebuilt
        return {"model": model, "usage": dict(rv.usage.__dict__), "rows": rows, **keep, **extra}

    for c in cases:
        for d in DIRECTIONS:
            if (int(c["event_id"]), d) in done:
                continue
            try:
                got, trace = rv.review(repo, c["event_id"], d)
            except Exception as e:  # noqa: BLE001 -- spend cap or anything else: keep the rows
                print(f"stopped: {type(e).__name__}: {e}", file=sys.stderr)
                return out(stopped=f"{type(e).__name__}: {e}")
            rows.append({**c, "direction": d, "checked": got, "trace": trace})
            if save:
                save(out())
            print(f"{c['event_id']:>8} against {d:<8} {got['strength']:<6} claims "
                  f"{got['n_claims']:>2} dropped {got['n_unsupported']:>2} ${rv.usage.cost:.4f}",
                  flush=True)  # fmt: skip
            time.sleep(0.3 if post is None else 0)
    return out()


def summarize(run_out: dict) -> dict:
    rows = run_out["rows"]
    # a decision is wrong when it closes laundering or escalates a clean payment
    wrong = [r for r in rows if (r["direction"] == "close") == r["laundering"]]
    right = [r for r in rows if (r["direction"] == "close") != r["laundering"]]
    n = sum(r["checked"]["n_claims"] for r in rows)
    bad = sum(r["checked"]["n_unsupported"] for r in rows)

    def strong(rs):
        return f"{sum(r['checked']['strength'] == 'strong' for r in rs)} of {len(rs)}"

    return {
        "model": run_out["model"],
        "reviews": len(rows),
        "claims": n,
        "unsupported_before_checker": bad,
        "unsupported_rate": round(bad / n, 4) if n else None,
        "unsupported_rate_95ci": [round(x, 4) for x in checker.wilson(bad, n)],
        "unsupported_after_checker": 0,
        "strong_when_wrong": strong(wrong),
        "strong_when_right": strong(right),
        "strength_counts": {s: sum(r["checked"]["strength"] == s for r in rows) for s in STRENGTHS},
        # the same rates within one kind of decision: wrong decisions are mostly closes, so a
        # label that just says "strong" to closes looks useful overall and is not
        "strong_by_direction": {
            d: {
                "when_wrong": strong([r for r in wrong if r["direction"] == d]),
                "when_right": strong([r for r in right if r["direction"] == d]),
            }
            for d in DIRECTIONS
        },  # fmt: skip
        "cost_usd": round(run_out["usage"]["cost"], 4),
    }


def stored_rows(run_out: dict) -> list[tuple[int, str, str, str]]:
    """(event_id, direction, model, review) for demo.ai_reviews: the checked review only."""
    out = []
    for r in run_out["rows"]:
        if r.get("from_log"):  # counts rebuilt from a run's log: no text to show
            continue
        c = r["checked"]
        review = {"strength": c["strength"], "summary": c["summary"], "kept": c["kept"],
                  "dropped": c["dropped"], "seconds": r["trace"]["seconds"]}  # fmt: skip
        out.append((int(r["event_id"]), r["direction"], run_out["model"], _compact(review)))
    return out


def _cases_from_evalset(path) -> list[dict]:
    return [{"event_id": c["event_id"], "laundering": c["expected"] != "none evident"}
            for c in json.loads(path.read_text())["cases"]]  # fmt: skip


def main(argv: list[str]) -> int:
    import argparse

    from graphguard.agent import evalset

    p = argparse.ArgumentParser(prog="reviewer")
    p.add_argument("cmd", choices=["run", "publish", "demo", "store"])
    p.add_argument("--model")
    p.add_argument("--set", type=int, default=2)
    p.add_argument("--limit", type=int)
    p.add_argument("--top", type=int, default=400)
    p.add_argument("--cap", type=float, help="dollars; with --resume it counts the earlier cost")
    p.add_argument("--resume", action="store_true", help="skip the reviews the file holds")
    a = p.parse_args(argv[1:])
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if a.cmd == "run":
        cases = _cases_from_evalset(evalset.OUT2 if a.set == 2 else evalset.OUT)[: a.limit]
        name = f"set{a.set}-{_slug(a.model)}" + (f"-first{a.limit}" if a.limit else "")
        out = run(a.model, cases, cap=a.cap, **_saving(RUNS_DIR / f"{name}.json", a.resume))
        print(json.dumps(summarize(out), indent=2))
    elif a.cmd == "publish":
        runs = [json.loads(f.read_text()) for f in sorted(RUNS_DIR.glob("set2-*.json"))
                if "-first" not in f.name]  # fmt: skip
        result = {"note": "S7.17: the AI second reviewer, measured on eval set 2 (64 alerts, "
                          "both directions), judged by the S7.10 checker frozen at c16b79c.",
                  "models": [summarize(r) for r in runs]}  # fmt: skip
        OUT.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        log_to_mlflow(result)
    elif a.cmd == "demo":
        from graphguard.demo.queries import PgRepo

        repo = PgRepo()
        top = repo._all("SELECT event_id FROM transactions WHERE rank <= %s ORDER BY rank",
                        (a.top,))  # fmt: skip
        path = RUNS_DIR / f"demo-top{a.top}-{_slug(a.model)}.json"
        out = run(a.model, [{"event_id": r["event_id"], "laundering": None} for r in top],
                  repo=repo, cap=a.cap, **_saving(path, a.resume))  # fmt: skip
        print(f"{len(out['rows'])} reviews, ${out['usage']['cost']:.4f}")
    elif a.cmd == "store":
        print(f"stored {store()} reviews")
    return 0


def log_to_mlflow(result: dict) -> None:
    """One MLflow run per model, in the project's experiment (tag stage=s7.17-reviewer)."""
    import mlflow

    from graphguard.tracking import start_tracking

    _, exp = start_tracking()
    for m in result["models"]:
        with mlflow.start_run(experiment_id=exp, run_name=f"s7.17 reviewer set2: {m['model']}"):
            mlflow.set_tags({"stage": "s7.17-reviewer", "data": "validation (synthetic AMLworld)"})
            mlflow.log_params({"model": m["model"], "reviews": m["reviews"], "eval_set": "set2"})
            mlflow.log_metrics({
                "claims": m["claims"],
                "unsupported_before_checker": m["unsupported_before_checker"],
                "unsupported_rate_before_checker": m["unsupported_rate"] or 0.0,
                "unsupported_rate_ci_high": m["unsupported_rate_95ci"][1],
                "strong_when_wrong": _ratio(m["strong_when_wrong"]),
                "strong_when_right": _ratio(m["strong_when_right"]),
                "cost_usd": m["cost_usd"],
            })  # fmt: skip
            mlflow.log_dict(m, "summary.json")


def _saving(path, resume: bool) -> dict:
    """Write the output after every review; with `resume`, start from the file."""

    def save(out):
        path.write_text(json.dumps(out, indent=1, default=str) + "\n")

    earlier = json.loads(path.read_text()) if resume and path.exists() else None
    return {"save": save, "resume": earlier}


def store() -> int:
    from psycopg2.extras import execute_values

    from graphguard.demo import db

    rows = []
    for f in sorted(RUNS_DIR.glob("*.json")):
        if f.name.startswith(("demo-", "set2-")) and "-first" not in f.name:
            rows += stored_rows(json.loads(f.read_text()))
    with db.connect(db.OWNER, secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute(db.SCHEMA)
        cur.execute(db.GRANTS)
        execute_values(
            cur,
            "INSERT INTO ai_reviews (event_id, direction, model, review) VALUES %s ON CONFLICT "
            "(event_id, direction, model) DO UPDATE SET review = EXCLUDED.review, at = now()",
            rows,
        )
    return len(rows)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
