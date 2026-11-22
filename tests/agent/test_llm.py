"""The LLM investigator's loop (S7.10), against a fake OpenRouter: tools are bound to the one
alert, the hard caps hold, and whatever the model says goes through the checker."""

import inspect
import json

import pytest

from graphguard.agent import checker, llm, tools

pytestmark = pytest.mark.unit

ALERT = {
    "event_id": 10, "event_time": "2022-09-07 12:00:00", "from_bank": 1, "from_account": "A",
    "to_bank": 2, "to_account": "B", "from_name": "Corp A",
    "from_bank_name": "Bank 1", "to_name": "Corp B", "to_bank_name": "Bank 2",
    "amount_paid": 9500.0, "payment_currency": "Euro", "amount_received": 9500.0,
    "receiving_currency": "Euro", "payment_format": "ACH", "rank": 3, "percentile": 99.9,
    "cold_policy": "warm", "rules": [], "rule_text": [], "reasons": ["Sent at 12:00."],
    "contributions": [],
    "ring": {"nodes": [{"id": "1:A", "seed": "sender"}, {"id": "2:B", "seed": "receiver"},
                       {"id": "3:U", "seed": None}],
             "edges": [{"id": 2, "from": "3:U", "to": "1:A", "t": "2022-09-07 11:00:00",
                        "amount": 9612.34, "currency": "Euro", "format": "ACH",
                        "role": "upstream"}], "more": []},
    "history": {"from": [], "to": []},
}  # fmt: skip


class Repo:
    def __init__(self):
        self.asked = []

    def alert(self, event_id):
        self.asked.append(event_id)
        return dict(ALERT) if event_id == 10 else None


def tool_call(name, i=0):
    return {"id": f"c{i}", "type": "function", "function": {"name": name, "arguments": "{}"}}


def reply(content=None, calls=None, cost=0.001):
    return {
        "choices": [{"message": {"role": "assistant", "content": content, "tool_calls": calls}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": cost},
    }


class FakeRouter:
    def __init__(self, script):
        self.script, self.bodies = list(script), []

    def __call__(self, body):
        self.bodies.append(body)
        return self.script.pop(0)


GOOD = {
    "summary": "Corp A paid Corp B.",
    "typology": "none evident",
    "claims": [
        {"text": "Corp A paid Corp B 9,500.00 Euro.", "cites": [10],
         "amount": {"value": 9500, "currency": "Euro"},
         "relation": {"from": "Corp A", "to": "Corp B"}},
        {"text": "Corp A received 12,000.00 Euro first.", "cites": [2]},  # invented number
    ],
}  # fmt: skip


def test_the_loop_runs_tools_for_this_alert_only_and_the_checker_drops_the_invention():
    repo = Repo()
    router = FakeRouter(
        [
            reply(calls=[tool_call("get_alert", 0), tool_call("get_ring", 1)]),
            reply(content="```json\n" + json.dumps(GOOD) + "\n```"),
        ]
    )
    inv = llm.Investigator("m", router, spend_cap=1.0)
    raw, trace = inv.report(repo, 10)
    assert trace["tool_calls"] == ["get_alert", "get_ring"] and trace["turns"] == 2
    assert set(repo.asked) == {10}  # nothing but this alert
    tool_msgs = [m for m in router.bodies[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c0", "c1"]
    assert all(b["temperature"] == 0 for b in router.bodies)
    out = checker.check_report(raw, tools.evidence(repo, 10))
    assert out["n_claims"] == 2 and out["n_unsupported"] == 1
    assert "12,000.00" in out["dropped"][0]["text"]
    assert inv.usage.calls == 2 and inv.usage.cost == pytest.approx(0.002)


def test_no_tool_takes_an_id_so_the_model_cannot_ask_for_another_alert():
    for spec in llm.TOOL_SPECS:
        assert spec["function"]["parameters"]["properties"] == {}
    assert [s["function"]["name"] for s in llm.TOOL_SPECS] == list(tools.TOOLS)


def test_an_unknown_tool_is_refused_not_run():
    router = FakeRouter([reply(calls=[tool_call("get_truth")]), reply(content=json.dumps(GOOD))])
    _, trace = llm.Investigator("m", router).report(Repo(), 10)
    refused = [m for m in router.bodies[1]["messages"] if m["role"] == "tool"][0]
    assert "no tool get_truth" in refused["content"]
    assert trace["tool_calls"] == ["get_truth"]


def test_the_turn_cap_holds_and_the_last_turn_offers_no_tools():
    router = FakeRouter([reply(calls=[tool_call("get_alert", i)]) for i in range(llm.MAX_TURNS)])
    raw, trace = llm.Investigator("m", router).report(Repo(), 10)
    assert len(router.bodies) == llm.MAX_TURNS
    assert "tools" not in router.bodies[-1]
    assert trace.get("no_report") and raw["claims"] == []


def test_a_non_json_answer_gets_one_repair_request():
    router = FakeRouter([reply(content="Here is my view."), reply(content=json.dumps(GOOD))])
    raw, trace = llm.Investigator("m", router).report(Repo(), 10)
    assert trace["repaired"] and raw["summary"] == GOOD["summary"]


def test_the_spend_cap_stops_before_the_next_call():
    router = FakeRouter([reply(calls=[tool_call("get_alert")], cost=0.6), reply(content="{}")])
    inv = llm.Investigator("m", router, spend_cap=0.5)
    with pytest.raises(llm.SpendCapReached):
        inv.report(Repo(), 10)
    assert len(router.bodies) == 1


def test_parse_report():
    assert llm.parse_report('noise {"a": 1} tail') == {"a": 1}
    assert llm.parse_report("no json") is None
    assert llm.parse_report("{broken") is None


def test_summarize_counts_and_intervals():
    rows = [
        {"expected": "CYCLE", "trace": {"seconds": 2.0},
         "checked": {"typology": "CYCLE", "n_claims": 4, "n_unsupported": 1,
                     "dropped": [{"why": "number 5 in the text is in no cited payment"}]}},
        {"expected": "none evident", "trace": {"seconds": 3.0},
         "checked": {"typology": "FAN-OUT", "n_claims": 2, "n_unsupported": 0, "dropped": []}},
    ]  # fmt: skip
    s = llm.summarize({"model": "m", "usage": llm.Usage(3, 10, 5, 0.01).__dict__, "cases": rows})
    assert s["claims"] == 6 and s["unsupported_before_checker"] == 1
    assert s["ring_type_recall"] == "1 of 1" and s["none_evident_correct"] == "0 of 1"
    assert s["dropped_by_reason"] == {"number": 1}
    assert s["unsupported_rate_95ci"][0] < 1 / 6 < s["unsupported_rate_95ci"][1]


def test_the_runner_never_names_the_answer_key(code_words):
    code = " ".join(code_words(llm)).lower()
    for forbidden in ("truth", "answer", "is_laundering", "pattern_type"):
        assert forbidden not in code, forbidden
    assert "repo" in inspect.signature(llm.Investigator.report).parameters


def test_the_stored_report_is_the_checked_one_without_the_expected_type():
    run_out = {
        "model": "m",
        "cases": [
            {"event_id": 10, "expected": "CYCLE", "trace": {"seconds": 1.5},
             "checked": {"summary": "s", "typology": "none evident", "kept": [{"text": "k"}],
                         "dropped": [{"text": "d", "why": "w"}], "n_claims": 2,
                         "n_unsupported": 1}},
        ],
    }  # fmt: skip
    [(eid, model, report)] = llm.stored_rows(run_out)
    stored = json.loads(report)
    assert (eid, model) == (10, "m")
    assert stored["kept"] == [{"text": "k"}] and stored["dropped"][0]["why"] == "w"
    assert "CYCLE" not in report and "expected" not in stored
