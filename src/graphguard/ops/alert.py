"""The scorer alert (S6.1): an email when the scorer breaks, and one when it heals.

    python -m graphguard.ops.alert check          # the timer runs this every 5 minutes
    python -m graphguard.ops.alert status         # exit 1 if the check is stale or mail fails
    python -m graphguard.ops.alert drill          # two real emails, marked DRILL; scorer untouched
    python -m graphguard.ops.alert pause 2h       # silence during planned work
    python -m graphguard.ops.alert resume

**Why.** The scorer once sat broken for 18 days and nobody noticed (S5.2). Phase 6's stream
depends on it, so an outage has to reach a human.

**Only on change.** Healthy -> broken sends one email, broken -> healthy sends one, and a
still-broken scorer reminds once a day. A state changes only after two checks in a row agree,
so a one-check blip (a rolling upgrade) emails nobody. A failed email stays pending and is
retried on the next check. A pause silences email but keeps tracking, so an outage still on
when the pause ends is reported then.

`step` is the whole judgement and is pure (tested with a fake clock). Only `main` talks to
k3s and to AWS SES. The SES key may send only from one verified address.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from graphguard.config import REPO_ROOT, secrets_dir
from graphguard.ops import k8s_health

STATE_FILE = REPO_ROOT / "private" / "alerts" / "state.json"
CONFIRM = 2  # checks in a row before the state changes
REMIND = dt.timedelta(hours=24)
STALE = dt.timedelta(minutes=15)  # the timer runs every 5
RUNBOOK = "docs/runbooks/scorer-down.md"
NAMESPACE = k8s_health.NAMESPACE


@dataclass(frozen=True)
class Email:
    kind: str  # down | reminder | recovered
    subject: str
    body: str


# --- the judgement (pure) ------------------------------------------------------------
def initial_state() -> dict:
    return {
        "status": "healthy",
        "since": None,
        "problems": [],
        "pending_status": None,
        "pending_count": 0,
        "pending_since": None,
        "pending_email": None,
        "outage_notified": False,
        "last_sent_at": None,
        "last_email": None,
        "mail_error": None,
        "last_check": None,
        "paused_until": None,
    }


def _t(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if value else None


def _paused(state: dict, now: dt.datetime) -> bool:
    until = _t(state.get("paused_until"))
    return until is not None and now < until


def _confirm(state: dict, observed: str, problems: list[str], now: dt.datetime) -> None:
    """Count agreeing checks; flip the status after CONFIRM in a row."""
    if observed == state["status"]:
        state.update(pending_status=None, pending_count=0, pending_since=None)
        if observed == "broken":
            state["problems"] = problems
        return
    if state["pending_status"] == observed:
        state["pending_count"] += 1
    else:
        state.update(pending_status=observed, pending_count=1, pending_since=now.isoformat())
    if state["pending_count"] < CONFIRM:
        return
    began = state["pending_since"]
    if observed == "broken":
        state.update(status="broken", problems=problems, pending_email="down",
                     outage_notified=False, down_since=began, since=began)  # fmt: skip
    else:
        # A "recovered" only for an outage someone was told about.
        heard = state["outage_notified"]
        state.update(status="healthy", problems=[], since=began,
                     pending_email="recovered" if heard else None,
                     recovered_at=began, outage_notified=False)  # fmt: skip
    state.update(pending_status=None, pending_count=0, pending_since=None)


def step(state: dict, problems: list[str], now: dt.datetime) -> tuple[dict, Email | None]:
    """One check: the new state, and the email to send now (if any). Pure."""
    state = {**initial_state(), **state}
    state["last_check"] = now.isoformat()
    _confirm(state, "broken" if problems else "healthy", problems, now)

    last = _t(state["last_sent_at"])
    if (
        state["status"] == "broken"
        and state["outage_notified"]
        and state["pending_email"] is None
        and last is not None
        and now - last >= REMIND
    ):
        state["pending_email"] = "reminder"

    if state["pending_email"] is None or _paused(state, now):
        return state, None
    return state, _message(state, state["pending_email"], now)


def mark_sent(state: dict, email: Email, now: dt.datetime) -> dict:
    state = {**state, "pending_email": None, "mail_error": None,
             "last_sent_at": now.isoformat(),
             "last_email": {"kind": email.kind, "at": now.isoformat()}}  # fmt: skip
    if email.kind in {"down", "reminder"}:
        state["outage_notified"] = True
    return state


def mark_failed(state: dict, error: str) -> dict:
    return {**state, "mail_error": error}  # pending_email stays: retried next check


# --- the messages --------------------------------------------------------------------
def _clock(value: str | None) -> str:
    t = _t(value)
    return t.strftime("%Y-%m-%d %H:%M UTC") if t else "unknown"


def _duration(start: str | None, end: str | None) -> str:
    a, b = _t(start), _t(end)
    if a is None or b is None:
        return "unknown"
    minutes = int((b - a).total_seconds() // 60)
    return f"{minutes} min" if minutes < 120 else f"{minutes // 60} h {minutes % 60} min"


_FIRST_STEPS = f"""First steps (on the box):
  just k8s-check       # what is broken
  just k8s-logs        # the scorer's last log lines
  just store-load      # if the reason is "feature store not loaded" (Redis restarted)

Runbook: {RUNBOOK}
Silence during planned work: just alert-pause 2h
"""


def _message(state: dict, kind: str, now: dt.datetime, prefix: str = "[GraphGuard]") -> Email:
    since = state.get("down_since") or state.get("since")
    if kind == "recovered":
        took = _duration(since, state.get("recovered_at"))
        return Email(kind, f"{prefix} scorer recovered (down {took})",
                     f"The scorer is healthy again.\n\nDown from {_clock(since)} to "
                     f"{_clock(state.get('recovered_at'))}: {took}.\n")  # fmt: skip
    problems = "\n".join(f"  - {p}" for p in state["problems"]) or "  - (none recorded)"
    title = "still DOWN" if kind == "reminder" else "DOWN"
    return Email(kind, f"{prefix} scorer {title} since {_clock(since)}",
                 f"The GraphGuard scorer on k3s is broken since {_clock(since)}.\n\n"
                 f"What the check found:\n{problems}\n\n{_FIRST_STEPS}")  # fmt: skip


def drill_emails(now: dt.datetime) -> list[Email]:
    """The two emails of a drill. Built from a throwaway state: the real one is untouched."""
    fake = {**initial_state(), "status": "broken", "since": now.isoformat(),
            "down_since": now.isoformat(), "recovered_at": now.isoformat(),
            "problems": ["DRILL: forced failure (scorer untouched)"]}  # fmt: skip
    return [_message(fake, k, now, "[GraphGuard][DRILL]") for k in ("down", "recovered")]


def status_problems(state: dict | None, now: dt.datetime) -> list[str]:
    """What `just alert-status` complains about; empty means the alert itself is healthy."""
    if not state or not state.get("last_check"):
        return ["the alert check has never run"]
    out = []
    if now - _t(state["last_check"]) > STALE:
        out.append(f"the alert check is stale (last run {_clock(state['last_check'])})")
    if state.get("mail_error"):
        out.append(f"alert mail failing: {state['mail_error']}")
    if state.get("status") == "broken":
        out.append(f"scorer broken since {_clock(state.get('since'))}")
    return out


# --- the probe's judgement (pure) ----------------------------------------------------
def assess_health(code: int | None, body: str) -> list[str]:
    if code is None:
        return ["scorer /health: no answer"]
    if code == 200:
        return []
    try:
        reason = json.loads(body).get("reason") or json.loads(body).get("status")
    except (ValueError, AttributeError):
        reason = body[:200]
    return [f"scorer /health {code}: {reason}"]


# --- the outside world ---------------------------------------------------------------
_PROBE = (
    "import urllib.request, urllib.error\n"
    "try:\n"
    "    r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10)\n"
    "    print(r.status); print(r.read().decode())\n"
    "except urllib.error.HTTPError as e:\n"
    "    print(e.code); print(e.read().decode())\n"
)


def probe_health() -> list[str]:
    """Ask the scorer's own /health from inside its pod (no new network path needed)."""
    pod = subprocess.run(
        ["k3s", "kubectl", "get", "pods", "-n", NAMESPACE, "-l", "ray.io/node-type=head",
         "-o", "jsonpath={.items[0].metadata.name}"],
        capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip
    if pod.returncode != 0 or not pod.stdout.strip():
        return []  # no pod: k8s_health already reports it
    try:
        out = subprocess.run(
            ["k3s", "kubectl", "exec", "-n", NAMESPACE, pod.stdout.strip(), "--",
             "python", "-c", _PROBE],
            capture_output=True, text=True, check=False, timeout=60,
        )  # fmt: skip
    except subprocess.TimeoutExpired:
        return assess_health(None, "")
    first, _, rest = out.stdout.partition("\n")
    code = int(first) if out.returncode == 0 and first.strip().isdigit() else None
    return assess_health(code, rest)


def _env_file(path: Path) -> dict[str, str]:
    text = path.read_text()
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line and line[0] != "#")


def ses_client():
    import boto3

    env = _env_file(secrets_dir() / "alerts-aws.env")
    return boto3.client(
        "sesv2",
        region_name=env.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
    )


def addresses() -> tuple[str, str]:
    env = _env_file(secrets_dir() / "alerts-mail.env")
    return env["ALERT_FROM"], env["ALERT_TO"]


def send(ses, email: Email, sender: str, to: str) -> None:
    ses.send_email(
        FromEmailAddress=sender,
        Destination={"ToAddresses": [to]},
        Content={"Simple": {"Subject": {"Data": email.subject, "Charset": "UTF-8"},
                            "Body": {"Text": {"Data": email.body, "Charset": "UTF-8"}}}},
    )  # fmt: skip


def load_state() -> dict | None:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else None


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    tmp.replace(STATE_FILE)


def _deliver(email: Email) -> str | None:
    """Send; return the error text, or None on success."""
    try:
        sender, to = addresses()
        send(ses_client(), email, sender, to)
    except Exception as e:  # noqa: BLE001 -- any mail failure is retried, never fatal
        return f"{type(e).__name__}: {e}"[:300]
    return None


def check(now: dt.datetime) -> int:
    problems = k8s_health.collect_problems() + probe_health()
    state, email = step(load_state() or initial_state(), problems, now)
    if email:
        error = _deliver(email)
        state = mark_failed(state, error) if error else mark_sent(state, email, now)
        print(f"email {email.kind}: {'FAILED ' + error if error else 'sent'}")
    save_state(state)
    print(f"scorer {state['status']}" + (f": {'; '.join(problems)}" if problems else ""))
    return 0


def _parse_duration(text: str) -> dt.timedelta:
    m = re.fullmatch(r"(\d+)([mh])", text)
    if not m:
        raise SystemExit("duration like 30m or 2h")
    n = int(m.group(1))
    return dt.timedelta(minutes=n) if m.group(2) == "m" else dt.timedelta(hours=n)


def main(argv: list[str]) -> int:
    now = dt.datetime.now(dt.UTC)
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "check":
        return check(now)
    if cmd == "status":
        state = load_state()
        problems = status_problems(state, now)
        if state:
            paused = _clock(state.get("paused_until")) if _paused(state, now) else "-"
            print(f"scorer {state['status']}  last check {_clock(state['last_check'])}  "
                  f"last email {state.get('last_email')}  paused until {paused}")  # fmt: skip
        for p in problems:
            print(f"ALERT PROBLEM: {p}", file=sys.stderr)
        return 1 if problems else 0
    if cmd == "drill":
        for email in drill_emails(now):
            error = _deliver(email)
            print(f"drill {email.kind}: {'FAILED ' + error if error else 'sent'}")
            if error:
                return 1
        return 0
    if cmd in {"pause", "resume"}:
        state = load_state() or initial_state()
        until = now + _parse_duration(argv[2]) if cmd == "pause" else None
        state["paused_until"] = until.isoformat() if until else None
        save_state(state)
        print(f"alert emails paused until {_clock(state['paused_until'])}" if until else "resumed")
        return 0
    print(f"usage: {argv[0]} check|status|drill|pause <30m|2h>|resume")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
