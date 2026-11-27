"""The scorer alert (S6.1): one email when it breaks, one when it heals, nothing in between.

Everything here is the pure judgement (`step`, the messages, the status verdict) with a
fake clock. Only `alert.main` talks to k3s and SES.
"""

import configparser
import datetime as dt

import pytest

from graphguard.config import REPO_ROOT
from graphguard.ops import alert

pytestmark = pytest.mark.unit

T0 = dt.datetime(2026, 11, 21, 12, 0, tzinfo=dt.UTC)
STEP = dt.timedelta(minutes=5)
BAD = ["scorer pod not ready"]


def run(checks, start=None, paused_until=None, mail_ok=True):
    """Feed a list of problem-lists through step(), one per 5 minutes; deliver each email."""
    state = start or alert.initial_state()
    if paused_until:
        state["paused_until"] = paused_until.isoformat()
    sent = []
    # a continued run picks up 5 minutes after the last check, like the timer would
    now = dt.datetime.fromisoformat(state["last_check"]) + STEP if start else T0
    for problems in checks:
        state, email = alert.step(state, problems, now)
        if email:
            if mail_ok:
                state = alert.mark_sent(state, email, now)
                sent.append(email)
            else:
                state = alert.mark_failed(state, "SES unreachable")
        now += STEP
    return state, sent


# --- the state machine ---------------------------------------------------------------
def test_healthy_sends_nothing():
    state, sent = run([[], [], []])
    assert sent == [] and state["status"] == "healthy"


def test_one_bad_check_is_a_blip_not_an_outage():
    state, sent = run([[], BAD, [], []])
    assert sent == [] and state["status"] == "healthy"


def test_two_bad_checks_in_a_row_send_exactly_one_down_email():
    state, sent = run([[], BAD, BAD, BAD, BAD])
    assert [e.kind for e in sent] == ["down"]
    assert state["status"] == "broken"
    assert state["since"] == (T0 + STEP).isoformat()  # the first failing check, not the second
    assert "scorer pod not ready" in sent[0].body


def test_recovery_needs_two_good_checks_and_reports_the_downtime():
    state, sent = run([BAD, BAD, BAD, [], BAD, BAD, [], []])
    assert [e.kind for e in sent] == ["down", "recovered"]
    # down since T0 (first check), healthy again from the 7th check (T0 + 30 min)
    assert "30 min" in sent[1].body and state["status"] == "healthy"


def test_still_broken_reminds_once_a_day_not_every_check():
    checks = [BAD] * (2 + 24 * 12 + 1)  # two to confirm, then a day and one more check
    _, sent = run(checks)
    assert [e.kind for e in sent] == ["down", "reminder"]


def test_a_failed_email_is_retried_on_the_next_check():
    state, _ = run([BAD, BAD], mail_ok=False)
    assert state["pending_email"] == "down" and state["mail_error"] == "SES unreachable"
    state, sent = run([BAD], start=state)
    assert [e.kind for e in sent] == ["down"]
    assert state["pending_email"] is None and state["mail_error"] is None


def test_recovery_before_the_down_email_got_out_sends_nothing():
    # mail failed for the whole outage: no "recovered" for an outage nobody heard about
    # (mail is still down at the first good check, so the retry of "down" fails too)
    state, _ = run([BAD, BAD, BAD, []], mail_ok=False)
    state, sent = run([[]], start=state)
    assert sent == [] and state["pending_email"] is None and state["status"] == "healthy"


def test_pause_silences_but_still_tracks_state():
    state, sent = run([BAD, BAD, BAD], paused_until=T0 + dt.timedelta(hours=2))
    assert sent == [] and state["status"] == "broken"


def test_outage_still_on_when_the_pause_ends_is_reported_then():
    start, _ = run([BAD, BAD], paused_until=T0 + 2 * STEP)
    _, sent = run([BAD], start=start)
    assert [e.kind for e in sent] == ["down"]


def test_outage_entirely_inside_a_pause_stays_silent():
    start, _ = run([BAD, BAD, [], []], paused_until=T0 + dt.timedelta(hours=1))
    _, sent = run([[], []], start=start)
    assert sent == []


def test_every_check_is_timestamped():
    state, _ = run([[]])
    assert state["last_check"] == T0.isoformat()


# --- the messages --------------------------------------------------------------------
def test_down_email_says_what_since_when_and_what_to_run():
    _, (email,) = run([BAD, BAD])
    assert email.subject.startswith("[GraphGuard] scorer DOWN")
    for must in ("scorer pod not ready", "12:00 UTC", "just k8s-check", "scorer-down.md"):
        assert must in email.body


def test_drill_emails_are_marked_and_never_change_state():
    emails = alert.drill_emails(T0)
    assert [e.kind for e in emails] == ["down", "recovered"]
    assert all(e.subject.startswith("[GraphGuard][DRILL]") for e in emails)
    assert "scorer untouched" in emails[0].body


# --- the status verdict (for `just alert-status`) -----------------------------------
def test_status_is_ok_when_recent_and_mail_works():
    state, _ = run([[]])
    assert alert.status_problems(state, T0 + dt.timedelta(minutes=10)) == []


def test_status_fails_when_the_check_is_stale():
    state, _ = run([[]])
    (problem,) = alert.status_problems(state, T0 + dt.timedelta(minutes=30))
    assert "stale" in problem


def test_status_fails_when_mail_is_failing():
    state, _ = run([BAD, BAD], mail_ok=False)
    assert any("mail" in p for p in alert.status_problems(state, T0 + STEP))


def test_status_fails_when_never_run():
    assert alert.status_problems(None, T0) == ["the alert check has never run"]


def test_state_survives_a_json_round_trip():
    import json

    state, _ = run([BAD, BAD, BAD])
    assert json.loads(json.dumps(state)) == state


# --- the health probe's judgement ----------------------------------------------------
@pytest.mark.parametrize(
    ("code", "body", "expected"),
    [
        (200, '{"status": "ok"}', []),
        (503, '{"status": "unavailable", "reason": "store not loaded"}',
         ["scorer /health 503: store not loaded"]),
        (None, "", ["scorer /health: no answer"]),
    ],
)  # fmt: skip
def test_health_answer_is_judged(code, body, expected):
    assert alert.assess_health(code, body) == expected


# --- the public demo (S8b.3) ---------------------------------------------------------
@pytest.mark.parametrize(
    ("code", "error", "days", "expected"),
    [
        (200, None, 80, []),
        (502, None, 80, ["public demo https://graphguard.lubobali.com: answered 502"]),
        (None, "certificate has expired", None,
         ["public demo https://graphguard.lubobali.com: no answer (certificate has expired)"]),
        (200, None, 10, ["public demo certificate expires in 10 days (renewal not working?)"]),
    ],
)  # fmt: skip
def test_the_public_demo_is_judged(code, error, days, expected):
    assert alert.assess_public(code, error, days) == expected


def test_the_check_includes_the_public_demo():
    import inspect

    assert "public_problems()" in inspect.getsource(alert.check)


# --- the SES call --------------------------------------------------------------------
class FakeSes:
    def __init__(self):
        self.calls = []

    def send_email(self, **kw):
        self.calls.append(kw)
        return {"MessageId": "x"}


def test_ses_call_sends_from_and_to_the_configured_addresses_only():
    ses = FakeSes()
    email = alert.drill_emails(T0)[0]
    alert.send(ses, email, sender="from@example.org", to="to@example.org")
    (call,) = ses.calls
    assert call["FromEmailAddress"] == "from@example.org"
    assert call["Destination"] == {"ToAddresses": ["to@example.org"]}
    assert call["Content"]["Simple"]["Subject"]["Data"] == email.subject


# --- the systemd unit is sandboxed ---------------------------------------------------
def _unit(name):
    p = configparser.ConfigParser(strict=False, interpolation=None)
    p.optionxform = str
    p.read(REPO_ROOT / "systemd" / name)
    return p


def test_unit_is_sandboxed_and_gets_its_keys_as_credentials():
    svc = _unit("graphguard-alert.service")["Service"]
    for key, value in {
        "ProtectSystem": "strict",
        "ProtectHome": "yes",
        "PrivateTmp": "yes",
        "NoNewPrivileges": "yes",
    }.items():
        assert svc[key] == value
    assert "MemoryMax" in svc
    assert "/srv/graphguard/.secrets" in svc["InaccessiblePaths"]
    text = (REPO_ROOT / "systemd" / "graphguard-alert.service").read_text()
    creds = [line for line in text.splitlines() if line.startswith("LoadCredential=")]
    names = {c.split("=", 1)[1].split(":", 1)[0] for c in creds}
    assert names == {"alerts-aws.env", "alerts-mail.env", "kafka-monitor.env", "stream-db.env"}


def test_timer_runs_every_five_minutes():
    timer = _unit("graphguard-alert.timer")["Timer"]
    assert timer["OnUnitActiveSec"] == "5min"


# --- the stream (S6.11) ------------------------------------------------------------------
def _stream(seq, start=None):
    """Feed (hwm, committed) pairs every 5 minutes; return the problems of each check."""
    state, out, now = start, [], T0
    for hwm, committed in seq:
        problems, state = alert.stream_problems(state, hwm, committed, now)
        out.append(problems)
        now += STEP
    return out


def test_an_idle_stream_is_fine():
    assert _stream([(1000, 1000)] * 10) == [[]] * 10


def test_a_consumer_that_keeps_moving_is_fine_even_with_lag():
    assert all(p == [] for p in _stream([(5000, 1000 + 100 * i) for i in range(10)]))


def test_a_stuck_consumer_with_work_waiting_is_reported_after_ten_minutes():
    out = _stream([(5000, 1000)] * 4)
    assert out[:2] == [[], []] and "stalled" in out[2][0]


def test_lag_that_keeps_growing_past_the_limit_is_reported():
    seq = [(300_000 + 10_000 * i, 50_000 + 1000 * i) for i in range(4)]
    out = _stream(seq)
    assert any("falling behind" in p for p in out[-1])


def test_kafka_unreadable_is_a_problem():
    (problems,) = _stream([(None, None)])
    assert "cannot read Kafka" in problems[0]
