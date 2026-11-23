"""The AI second reviewer (S7.17), against a fake OpenRouter: it argues against the person's
decision with claims the frozen checker judges, from tools bound to one alert, never the
answer key."""

import inspect
import json

import pytest

from graphguard.agent import checker, reviewer, tools

pytestmark = pytest.mark.unit

ALERT = {
    "event_id": 10, "event_time": "2022-09-07 12:00:00", "from_bank": 1, "from_account": "A",
    "to_bank": 2, "to_account": "B", "from_name": "Corp A", "from_bank_name": "Bank 1",
    "to_name": "Corp B", "to_bank_name": "Bank 2", "amount_paid": 9500.0,
    "payment_currency": "Euro", "amount_received": 9500.0, "receiving_currency": "Euro",
    "payment_format": "ACH", "rank": 3, "percentile": 99.9, "cold_policy": "warm", "rules": [],
    "rule_text": [], "reasons": ["Sent at 12:00."], "contributions": [],
    "ring": {"nodes": [{"id": "1:A", "seed": "sender"}, {"id": "2:B", "seed": "receiver"}],
             "edges": [], "more": []},
    "history": {"from": [], "to": []},
}  # fmt: skip


class Repo:
    def __init__(self):
        self.asked = []

    def alert(self, event_id):
        self.asked.append(event_id)
        return dict(ALERT) if event_id == 10 else None


class FakeRouter:
    def __init__(self, script):
        self.script, self.bodies = list(script), []

    def __call__(self, body):
        self.bodies.append(body)
        return self.script.pop(0)


def reply(content=None, calls=None, cost=0.001):
    msg = {"role": "assistant", "content": content, "tool_calls": calls}
    usage = {"prompt_tokens": 50, "completion_tokens": 10, "cost": cost}
    return {"choices": [{"message": msg}], "usage": usage}


AGAINST = {
    "strength": "strong",
    "summary": "Corp A paid Corp B the full amount at once.",
    "claims": [
        {"text": "Corp A paid Corp B 9,500.00 Euro.", "cites": [10],
         "amount": {"value": 9500, "currency": "Euro"},
         "relation": {"from": "Corp A", "to": "Corp B"}},
        {"text": "Corp B forwarded 20,000.00 Euro.", "cites": [10]},  # invented
    ],
}  # fmt: skip


def test_the_prompt_states_the_decision_and_asks_for_the_case_against_it():
    esc, close = reviewer.ask(10, "escalate"), reviewer.ask(10, "close")
    assert "escalate" in esc and "AGAINST" in esc and "10" in esc
    assert "close" in close and "AGAINST" in close
    with pytest.raises(ValueError):
        reviewer.ask(10, "approve")


def test_a_review_runs_the_tools_for_this_alert_only_and_the_checker_drops_the_invention():
    repo = Repo()
    router = FakeRouter([
        reply(calls=[{"id": "c0", "type": "function",
                      "function": {"name": "get_alert", "arguments": "{}"}}]),
        reply(content=json.dumps(AGAINST)),
    ])  # fmt: skip
    rv = reviewer.Reviewer("m", router, spend_cap=1.0)
    out, trace = rv.review(repo, 10, "close")
    assert set(repo.asked) == {10} and trace["tool_calls"] == ["get_alert"]
    assert router.bodies[0]["messages"][0]["content"] == reviewer.SYSTEM
    assert "close" in router.bodies[0]["messages"][1]["content"]
    assert out["strength"] == "strong" and out["n_unsupported"] == 1
    assert "20,000.00" in out["dropped"][0]["text"]
    assert out == reviewer.checked(AGAINST, tools.evidence(repo, 10))


@pytest.mark.parametrize(("given", "kept"), [("strong", "strong"), ("SOME", "some"),
                                             ("maybe", "none"), (None, "none")])  # fmt: skip
def test_an_unknown_strength_becomes_none(given, kept):
    assert reviewer.checked({"strength": given, "claims": []}, {})["strength"] == kept


def test_the_spend_cap_stops_a_review():
    router = FakeRouter([reply(calls=[{"id": "c0", "type": "function",
                                       "function": {"name": "get_alert", "arguments": "{}"}}],
                               cost=2.0), reply(content="{}")])  # fmt: skip
    with pytest.raises(reviewer.SpendCapReached):
        reviewer.Reviewer("m", router, spend_cap=1.0).review(Repo(), 10, "escalate")


def test_the_reviewer_never_names_the_answer_key(code_words):
    code = " ".join(code_words(reviewer)).lower()
    for forbidden in ("truth", "answer", "is_laundering", "pattern_type"):
        assert forbidden not in code, forbidden
    assert "repo" in inspect.signature(reviewer.Reviewer.review).parameters


def test_the_summary_measures_strong_when_wrong_against_strong_when_right():
    def row(laundering, direction, strength, n=2, bad=0):
        return {"laundering": laundering, "direction": direction,
                "checked": {"strength": strength, "n_claims": n, "n_unsupported": bad}}  # fmt: skip

    rows = [
        row(True, "close", "strong"),  # wrong decision, reviewer pushes: good
        row(True, "close", "none"),  # wrong decision, reviewer silent: miss
        row(False, "escalate", "strong"),  # wrong decision, pushes: good
        row(True, "escalate", "strong", bad=1),  # right decision, still "strong": nag
        row(False, "close", "some"),
    ]  # right decision, not strong
    s = reviewer.summarize({"model": "m", "usage": {"cost": 0.01}, "rows": rows})
    assert s["strong_when_wrong"] == "2 of 3" and s["strong_when_right"] == "1 of 2"
    assert s["claims"] == 10 and s["unsupported_before_checker"] == 1
    assert s["strong_by_direction"]["close"] == {"when_wrong": "1 of 2", "when_right": "0 of 1"}
    assert s["strong_by_direction"]["escalate"] == {"when_wrong": "1 of 1", "when_right": "1 of 1"}
    lo, hi = s["unsupported_rate_95ci"]
    assert lo < 0.1 < hi


def test_stored_reviews_carry_no_expected_label():
    out = {"model": "m", "rows": [{"event_id": 10, "direction": "close", "laundering": True,
                                   "checked": {"strength": "some", "summary": "s", "kept": [],
                                               "dropped": [], "n_claims": 0, "n_unsupported": 0},
                                   "trace": {"seconds": 1.0}}]}  # fmt: skip
    [(eid, direction, model, review)] = reviewer.stored_rows(out)
    assert (eid, direction, model) == (10, "close", "m")
    assert "laundering" not in review and json.loads(review)["strength"] == "some"


def test_checker_is_the_frozen_one():
    assert reviewer.checker is checker


@pytest.mark.parametrize("bad", [
    {"text": "x", "cites": [10], "amount": 9500.0},  # a bare number, not {value, currency}
    {"text": "x", "cites": [10], "amount": {"currency": "Euro"}},
    {"text": "x", "cites": [10], "relation": "Corp A to Corp B"},
    {"text": "x", "cites": "10"},
    {"text": "x", "cites": [10], "count": "many"},
    "a claim that is only a string",
])  # fmt: skip
def test_a_claim_in_the_wrong_shape_is_dropped_never_a_crash(bad):
    # Sonnet wrote "amount": 9500.0 once and the checker raised; 115 reviews were lost
    out = reviewer.checked({"strength": "some", "claims": [bad, AGAINST["claims"][0]]},
                           tools.evidence(Repo(), 10))  # fmt: skip
    assert out["n_claims"] == 2 and out["n_unsupported"] == 1
    assert out["dropped"][0]["why"].startswith("malformed")
    assert out["kept"] == [AGAINST["claims"][0]]


def test_a_run_saves_after_every_review_and_stops_cleanly_on_an_error():
    saved = []
    router = FakeRouter([reply(content=json.dumps(AGAINST)), RuntimeError("boom")])

    def post(body):
        r = router(body)
        if isinstance(r, Exception):
            raise r
        return r

    out = reviewer.run("m", [{"event_id": 10, "laundering": True}], repo=Repo(), post=post,
                       cap=1.0, save=lambda o: saved.append(len(o["rows"])))  # fmt: skip
    assert len(out["rows"]) == 1 and "boom" in out["stopped"] and saved[0] == 1


def test_a_resumed_run_skips_reviews_already_done():
    seen = {"strength": "some", "n_claims": 0, "n_unsupported": 0}
    done = {"model": "m", "usage": {"cost": 0.5, "prompt_tokens": 0, "completion_tokens": 0},
            "rows": [{"event_id": 10, "laundering": True, "direction": "escalate",
                      "checked": seen}]}  # fmt: skip
    router = FakeRouter([reply(content=json.dumps(AGAINST))])
    out = reviewer.run("m", [{"event_id": 10, "laundering": True}], repo=Repo(), post=router,
                       cap=1.0, resume=done)  # fmt: skip
    assert [r["direction"] for r in out["rows"]] == ["escalate", "close"]
    assert len(router.bodies) == 1 and out["usage"]["cost"] == pytest.approx(0.501)


def test_rows_rebuilt_from_a_log_are_measured_but_never_stored_for_the_site():
    row = {"event_id": 10, "direction": "close", "laundering": True, "from_log": True,
           "checked": {"strength": "some", "summary": "", "kept": [], "dropped": [],
                       "n_claims": 3, "n_unsupported": 0}, "trace": {"seconds": None}}  # fmt: skip
    assert reviewer.stored_rows({"model": "m", "rows": [row]}) == []
    assert reviewer.summarize({"model": "m", "usage": {"cost": 1}, "rows": [row]})["claims"] == 3
