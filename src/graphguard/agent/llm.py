"""The LLM investigator (S7.10): an OpenRouter model drafts the report, the checker judges it.

    python -m graphguard.agent.llm run --model deepseek/deepseek-v4.1-flash [--limit N]
    python -m graphguard.agent.llm rescore     # re-judge saved reports (no model calls)
    python -m graphguard.agent.llm publish     # all runs -> docs/analysis/s7.10-agent.json
    python -m graphguard.agent.llm store       # checked reports -> demo.agent_reports (owner)

One alert per conversation. The model may call the four read-only tools (bound to that alert:
no tool takes an id, so it cannot wander to another alert or to the answer key), then answers
with one JSON report. Hard limits in code, on top of the key's own credit limit set in the
OpenRouter console: `MAX_TURNS` model calls per alert and a dollar cap per run, checked
against the cost OpenRouter reports after every call.
"""

from __future__ import annotations

import functools
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

from graphguard.agent import tools
from graphguard.config import REPO_ROOT

URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_TURNS = 6  # model calls per alert: up to 4 tool rounds + the answer + one repair
RUNS_DIR = REPO_ROOT / "docs" / "analysis" / "s7.10-runs"
OUT = REPO_ROOT / "docs" / "analysis" / "s7.10-agent.json"
# Dollar cap per full run (64 alerts). Prices checked on openrouter.ai/api/v1/models
# 2026-11-22: deepseek-v4.1-flash $0.05 / $0.20 per M tokens in/out, claude-sonnet-5.5
# $2 / $10. Expected: ~$0.10 and ~$4 a run.
SPEND_CAP = {"deepseek/deepseek-v4.1-flash": 1.0, "anthropic/claude-sonnet-5.5": 6.0}

SYSTEM = """You are an anti-money-laundering investigator's assistant. The data is synthetic
(IBM AMLworld simulator); names are synthetic. You review ONE alerted payment and draft a
short case report for a human investigator, who decides.

Use the tools to look at the alert, the model's reasons, the money flow around it (only
payments BEFORE the alert, 72 hours, at most 6 per account and direction; "more" counts what
was cut) and both accounts' earlier payments.

Then reply with ONLY one JSON object, no other text:
{"summary": "2-3 plain sentences",
 "typology": one of "FAN-OUT", "FAN-IN", "CYCLE", "GATHER-SCATTER", "SCATTER-GATHER",
             "STACK", "BIPARTITE", "RANDOM", "none evident",
 "claims": [{"text": "one fact in plain words",
             "cites": [transaction ids that show it],
             "amount": {"value": number, "currency": "..."} or null,
             "time": "YYYY-MM-DD HH:MM" or null,
             "relation": {"from": "payer name or id", "to": "payee name or id"} or null,
             "count": number or null}]}

Typologies (AMLworld): FAN-OUT one account pays many; FAN-IN many pay one; CYCLE money
returns to where it started; GATHER-SCATTER many pay one, which then pays many;
SCATTER-GATHER one pays many, which all pay one; STACK layers of accounts passing money on;
BIPARTITE a group of payers pays a group of payees; RANDOM money hops through a random
chain. Say "none evident" when the flow shows no such shape: most alerts are not laundering.

Rules: every claim cites only transaction ids you were shown. A claim's amount, time,
relation and count must match the cited payments exactly (a count is the number of ids
cited). Do not write numbers that are not in the cited payments. Amounts are in many
currencies: never add them up. Fewer true claims beat many guesses."""

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    }
    for name, desc in (
        ("get_alert", "The alerted payment: who paid whom, amount, time, rank, rules."),
        ("get_reasons", "Why the model ranked it: plain reasons and top feature contributions."),
        ("get_ring", "The money flow around the alert, as it was before the alert."),
        ("get_history", "Each account's 20 most recent earlier payments."),
    )
]


class SpendCapReached(RuntimeError):
    pass


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0

    def add(self, u: dict) -> None:
        self.calls += 1
        self.prompt_tokens += int(u.get("prompt_tokens") or 0)
        self.completion_tokens += int(u.get("completion_tokens") or 0)
        self.cost += float(u.get("cost") or 0.0)


def _key() -> str:
    from graphguard.config import secrets_dir

    for line in (secrets_dir() / "openrouter.env").read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("no OPENROUTER_API_KEY in openrouter.env (just secret-set openrouter.env)")


def http_post(body: dict, key: str, retries: int = 4) -> dict:
    data = json.dumps(body).encode()
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            URL,
            data=data,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Title": "GraphGuard-AI",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2**attempt * 2)
                continue
            raise RuntimeError(f"OpenRouter {e.code}: {e.read()[:300]!r}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries:
                time.sleep(2**attempt * 2)
                continue
            raise
    raise AssertionError("unreachable")


def parse_report(text: str) -> dict | None:
    """The JSON object in the model's answer (tolerates a ```json fence), or None."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None


def _compact(obj) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


@dataclass
class Investigator:
    model: str
    post: Callable[[dict], dict]
    spend_cap: float = 1.0
    usage: Usage = field(default_factory=Usage)

    def _call(self, messages: list[dict], with_tools: bool) -> dict:
        if self.usage.cost >= self.spend_cap:
            raise SpendCapReached(f"${self.usage.cost:.4f} spent, cap ${self.spend_cap}")
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            # Thinking models spend output tokens on reasoning first: a 2,000 cap left one
            # alert with 2,000 reasoning tokens and no report (smoke run). Same budget for
            # every model: reasoning <= 3,000, the whole reply <= 8,000.
            "max_tokens": 8000,
            "reasoning": {"max_tokens": 3000},
            "usage": {"include": True},
        }
        if with_tools:
            body["tools"] = TOOL_SPECS
        resp = self.post(body)
        self.usage.add(resp.get("usage") or {})
        choice = resp["choices"][0]
        return {**choice["message"], "finish_reason": choice.get("finish_reason")}

    def report(self, repo, event_id: int) -> tuple[dict, dict]:
        """The model's report for one alert, and a trace (tool calls, turns, seconds)."""
        bound = {name: functools.partial(getattr(tools, name), repo, event_id)
                 for name in tools.TOOLS}  # fmt: skip
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Review alert {event_id} and draft the report."},
        ]
        trace = {"tool_calls": [], "turns": 0, "repaired": False}
        t0 = time.monotonic()
        report = None
        for turn in range(MAX_TURNS):
            trace["turns"] = turn + 1
            last = turn == MAX_TURNS - 1
            msg = self._call(messages, with_tools=not last)
            trace.setdefault("finish", []).append(msg.get("finish_reason"))
            calls = msg.get("tool_calls") or []
            if calls and not last:
                messages.append(
                    {"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls}
                )
                for c in calls:
                    name = c["function"]["name"]
                    trace["tool_calls"].append(name)
                    result = bound[name]() if name in bound else {"error": f"no tool {name}"}
                    messages.append(
                        {"role": "tool", "tool_call_id": c["id"], "content": _compact(result)}
                    )
                continue
            report = parse_report(msg.get("content") or "")
            if report is not None or last:
                break
            trace["repaired"] = True
            messages.append({"role": "assistant", "content": msg.get("content") or ""})
            messages.append(
                {"role": "user", "content": "Reply with ONLY the JSON object, nothing else."}
            )
        trace["seconds"] = round(time.monotonic() - t0, 2)
        if report is None:
            trace["no_report"] = True
            report = {"summary": "", "typology": "none evident", "claims": []}
        return report, trace


# --- running and publishing ----------------------------------------------------------------
def run(model: str, limit: int | None = None, post=None, repo=None, cases_file=None) -> dict:
    from graphguard.agent import checker, evalset

    if repo is None:
        from graphguard.demo.queries import PgRepo

        repo = PgRepo()
    if post is None:
        key = _key()

        def post(body):
            return http_post(body, key)

    cases = json.loads((cases_file or evalset.OUT).read_text())["cases"][:limit]
    inv = Investigator(model, post, SPEND_CAP.get(model, 1.0))
    rows = []
    for c in cases:
        try:
            raw, trace = inv.report(repo, c["event_id"])
        except SpendCapReached as e:
            print(f"stopped: {e}", file=sys.stderr)
            break
        checked = checker.check_report(raw, tools.evidence(repo, c["event_id"]))
        rows.append({**c, "raw": raw, "checked": checked, "trace": trace})
        print(
            f"{c['event_id']:>8} expected {c['expected']:<15} said {checked['typology']:<15} "
            f"claims {checked['n_claims']:>2} dropped {checked['n_unsupported']:>2} "
            f"${inv.usage.cost:.4f}",
            flush=True,
        )
        time.sleep(0.5)  # pacing: well under any rate limit
    return {"model": model, "usage": inv.usage.__dict__, "cases": rows}


def summarize(run_out: dict) -> dict:
    from graphguard.agent.checker import wilson

    rows = run_out["cases"]
    n_claims = sum(r["checked"]["n_claims"] for r in rows)
    n_bad = sum(r["checked"]["n_unsupported"] for r in rows)
    rings = [r for r in rows if r["expected"] != "none evident"]
    clean = [r for r in rows if r["expected"] == "none evident"]
    lo, hi = wilson(n_bad, n_claims)
    secs = sorted(r["trace"]["seconds"] for r in rows)
    reasons: dict[str, int] = {}
    for r in rows:
        for d in r["checked"]["dropped"]:
            kind = d["why"].split(" ")[0] if d["why"] != "cites nothing" else "cites"
            reasons[kind] = reasons.get(kind, 0) + 1
    u = run_out["usage"]
    return {
        "reporter": run_out["model"],
        "cases": len(rows),
        "claims": n_claims,
        "unsupported_before_checker": n_bad,
        "unsupported_rate_before_checker": round(n_bad / n_claims, 4) if n_claims else 0.0,
        "unsupported_rate_95ci": [round(lo, 4), round(hi, 4)],
        "unsupported_after_checker": 0,  # the checker drops every claim it cannot support
        "dropped_by_reason": dict(sorted(reasons.items())),
        "ring_type_recall": f"{sum(r['checked']['typology'] == r['expected'] for r in rings)} "
        f"of {len(rings)}",
        "none_evident_correct": f"{sum(r['checked']['typology'] == 'none evident' for r in clean)}"
        f" of {len(clean)}",
        "no_report": sum(bool(r["trace"].get("no_report")) for r in rows),
        "seconds_median": secs[len(secs) // 2] if secs else None,
        "seconds_max": secs[-1] if secs else None,
        "model_calls": u["calls"],
        "tokens_in": u["prompt_tokens"],
        "tokens_out": u["completion_tokens"],
        "cost_usd": round(u["cost"], 4),
    }


def stored_rows(run_out: dict) -> list[tuple[int, str, str]]:
    """(event_id, model, checked report) for the demo's agent_reports table. The checked
    report only: what was kept, what was dropped and why -- never the eval set's expected
    type, which comes from the answer key."""
    rows = []
    for r in run_out["cases"]:
        c = r["checked"]
        report = {
            "summary": c["summary"],
            "typology": c["typology"],
            "kept": c["kept"],
            "dropped": c["dropped"],
            "seconds": r["trace"]["seconds"],
        }
        rows.append((int(r["event_id"]), run_out["model"], _compact(report)))
    return rows


def store(runs: list[dict]) -> int:
    from psycopg2.extras import execute_values

    from graphguard.demo import db

    rows = [row for r in runs for row in stored_rows(r)]
    with db.connect(db.OWNER, secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute(db.SCHEMA)  # creates agent_reports on a database set up before S7.10
        cur.execute(db.GRANTS)
        execute_values(
            cur,
            "INSERT INTO agent_reports (event_id, model, report) VALUES %s "
            "ON CONFLICT (event_id, model) DO UPDATE SET report = EXCLUDED.report, at = now()",
            rows,
        )
    return len(rows)


def _ratio(text: str) -> float:
    k, n = text.split(" of ")
    return int(k) / int(n) if int(n) else 0.0


def log_to_mlflow(result: dict) -> None:
    """One MLflow run per reporter, in the project's experiment (tag stage=s7.10-agent)."""
    import mlflow

    from graphguard.tracking import start_tracking

    _, exp = start_tracking()
    for m in [result["baseline"], *result["models"]]:
        with mlflow.start_run(experiment_id=exp, run_name=f"s7.10 agent: {m['reporter']}"):
            mlflow.set_tags({"stage": "s7.10-agent", "data": "validation (synthetic AMLworld)"})
            mlflow.log_params({"reporter": m["reporter"], "cases": m["cases"],
                               "max_turns": MAX_TURNS})  # fmt: skip
            unsupported = m.get("unsupported_before_checker", m.get("unsupported", 0))
            mlflow.log_metrics({
                "claims": m["claims"],
                "unsupported_before_checker": unsupported,
                "unsupported_rate_before_checker": unsupported / m["claims"] if m["claims"] else 0,
                "unsupported_rate_ci_high": m["unsupported_rate_95ci"][1],
                "ring_type_recall": _ratio(m["ring_type_recall"]),
                "none_evident_correct": _ratio(m["none_evident_correct"]),
                "cost_usd": m.get("cost_usd", 0.0),
            })  # fmt: skip
            mlflow.log_dict(m, "summary.json")


def _slug(model: str) -> str:
    return model.replace("/", "__")


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "run":
        model = argv[argv.index("--model") + 1]
        limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
        fresh = "--set" in argv and argv[argv.index("--set") + 1] == "2"
        from graphguard.agent import evalset

        out = run(model, limit, cases_file=evalset.OUT2 if fresh else None)
        where = RUNS_DIR / "set2" if fresh else RUNS_DIR
        where.mkdir(parents=True, exist_ok=True)
        (where / f"{_slug(model)}.json").write_text(_compact(out) + "\n")
        print(json.dumps(summarize(out), indent=2))
        return 0
    if cmd == "publish":
        baseline = json.loads((REPO_ROOT / "docs/analysis/s7.10-baseline.json").read_text())
        runs = [json.loads(p.read_text()) for p in sorted(RUNS_DIR.glob("*.json"))]
        result = {
            "what": "S7.10: LLM investigator vs the template baseline on the 64-case eval set "
            "(validation alerts, synthetic AMLworld). The checker judges every claim; "
            "unsupported claims are dropped before anything is shown.",
            "baseline": baseline,
            "models": [{**summarize(r), "first_pass_checker": r.get("first_pass")} for r in runs],
        }
        OUT.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        log_to_mlflow(result)
        return 0
    if cmd == "rescore":
        # Re-judge the saved reports with the current checker (no model calls). The first
        # judgement is kept beside it: S7.10 found three checker bugs this way, and both
        # numbers are published (FINDING-019).
        from graphguard.agent import checker
        from graphguard.demo.queries import PgRepo

        repo = PgRepo()
        for p in sorted(RUNS_DIR.glob("*.json")):
            out = json.loads(p.read_text())
            out.setdefault("first_pass", summarize(out))
            for r in out["cases"]:
                r["checked"] = checker.check_report(r["raw"], tools.evidence(repo, r["event_id"]))
            p.write_text(_compact(out) + "\n")
            print(p.name, json.dumps(summarize(out)))
        return 0
    if cmd == "store":
        runs = [json.loads(p.read_text()) for p in sorted(RUNS_DIR.glob("*.json"))]
        print(f"{store(runs)} checked reports -> demo.agent_reports")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
