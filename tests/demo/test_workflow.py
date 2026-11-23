"""The case workflow (S7.15): states, who may do what, reasons, repeats, per-visitor cases."""

import datetime as dt

import pytest

from graphguard.demo import workflow as W

pytestmark = pytest.mark.unit

ME, OTHER = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
T0 = dt.datetime(2026, 11, 23, 12, 0, tzinfo=dt.UTC)


def row(action, role="investigator", actor=ME, owner=None, code=None, reason="seen it", at=T0):
    return {"actor": actor, "case_owner": owner or actor, "role": role, "action": action,
            "code": code, "reason": reason, "at": at}  # fmt: skip


def test_a_case_starts_new_and_a_decision_waits_for_review():
    assert W.case_state([])["state"] == "new"
    s = W.case_state([row("escalate")])
    assert (s["state"], s["decision"]) == ("awaiting_review", "escalate")


def test_approval_ends_the_case_and_an_escalation_gets_a_30_day_sar_due_date():
    s = W.case_state([row("escalate"), row("approve", role="reviewer", reason="", at=T0)])
    assert s["state"] == "escalated" and s["sar_due"] == T0 + dt.timedelta(days=30)
    c = W.case_state([row("close", code="explained"), row("approve", role="reviewer", reason="")])
    assert c["state"] == "closed" and c["sar_due"] is None


def test_send_back_reopens_the_decision_and_a_change_is_a_new_row():
    s = W.case_state(
        [row("close", code="other"), row("send_back", role="reviewer", reason="look again")]
    )
    assert s["state"] == "sent_back" and s["decision"] is None
    s = W.case_state([row("close", code="other"), row("escalate")])  # changed before review
    assert (s["state"], s["decision"], s["code"]) == ("awaiting_review", "escalate", None)


@pytest.mark.parametrize(
    ("state", "role", "allowed"),
    [
        ("new", "investigator", {"escalate", "close"}),
        ("new", "reviewer", set()),
        ("awaiting_review", "investigator", {"escalate", "close"}),
        ("awaiting_review", "reviewer", {"approve", "send_back"}),
        ("sent_back", "investigator", {"escalate", "close"}),
        ("sent_back", "reviewer", set()),
        ("escalated", "investigator", {"escalate", "close"}),  # a reopen, a new row
        ("closed", "reviewer", set()),
    ],
)
def test_who_may_do_what_in_each_state(state, role, allowed):
    assert W.allowed(state, role) == allowed


def test_reasons_codes_and_lengths_are_checked():
    assert W.problem("close", None, "fine") == "a close needs a code"
    assert W.problem("close", "nonsense", "fine") == "unknown close code"
    assert W.problem("escalate", "explained", "x") == "only a close has a code"
    assert W.problem("escalate", None, "  ") == "a reason is required"
    assert W.problem("send_back", None, "") == "a reason is required"
    assert W.problem("approve", None, "") is None  # approving needs no words
    assert W.problem("escalate", None, "x" * 501) == "the reason is longer than 500 characters"
    assert W.problem("escalate", None, "money split and gathered") is None


def test_a_repeat_of_the_actors_last_action_is_not_stored_again():
    history = [row("escalate", reason="ring")]
    assert W.is_repeat(history, ME, "escalate", None, "ring")
    assert not W.is_repeat(history, ME, "close", "other", "ring")
    assert not W.is_repeat(history, OTHER, "escalate", None, "ring")


def test_check_refuses_what_the_state_does_not_allow_and_whose_case_it_is():
    assert W.check([], ME, ME, "investigator", "approve", None, "") == "approve is not allowed now"
    assert W.check([], ME, OTHER, "investigator", "escalate", None, "x") == (
        "an investigator decides only their own cases"
    )
    assert W.check([], ME, W.DEMO, "investigator", "escalate", None, "x") == (
        "an investigator decides only their own cases"
    )
    sam = W.demo_history(W.DEMO_CASES[0][0])
    assert W.check(sam, ME, W.DEMO, "reviewer", "approve", None, "") is None
    assert W.check([], ME, ME, "investigator", "escalate", None, "ring") is None


def test_each_visitor_sees_only_their_own_rows_and_their_own_reviews_of_sam():
    rows = [row("escalate", actor=ME), row("close", actor=OTHER, code="other"),
            row("approve", role="reviewer", actor=OTHER, owner=W.DEMO, reason=""),
            row("send_back", role="reviewer", actor=ME, owner=W.DEMO, reason="why?")]  # fmt: skip
    assert [r["actor"] for r in W.visible(rows, ME, ME)] == [ME]
    mine_of_sam = W.visible(rows, W.DEMO, ME)
    assert [r["action"] for r in mine_of_sam] == ["send_back"]


def test_sam_has_eight_seeded_decisions_three_of_them_wrong_on_purpose():
    assert len(W.DEMO_CASES) == 8 and len({c[0] for c in W.DEMO_CASES}) == 8
    assert sum(1 for c in W.DEMO_CASES if not c[4]) == 3  # c[4]: matches the answer key
    for eid, action, code, reason, _ in W.DEMO_CASES:
        assert W.problem(action, code, reason) is None
        assert W.case_state(W.demo_history(eid))["state"] == "awaiting_review"


def test_the_score_counts_decisions_that_match_the_answer_key():
    cases = [{"decision": "escalate", "is_laundering": True},
             {"decision": "close", "is_laundering": True},
             {"decision": "close", "is_laundering": False},
             {"decision": None, "is_laundering": True}]  # fmt: skip
    assert W.score(cases) == {"decided": 3, "right": 2, "model_right": 2}


# ---- S7.16: the manager's numbers --------------------------------------------------------


def case(state, decision, laundering, ai=None, eid=1):
    return {"event_id": eid, "state": state, "decision": decision, "is_laundering": laundering,
            "ai_leans_suspicious": ai}  # fmt: skip


def test_metrics_count_every_state_and_the_answer_key():
    cases = [case("awaiting_review", "escalate", True, ai=True, eid=1),
             case("escalated", "escalate", False, ai=True, eid=2),
             case("closed", "close", False, ai=False, eid=3),
             case("sent_back", None, True, eid=4),
             case("awaiting_review", "close", True, ai=True, eid=5)]  # fmt: skip
    m = W.metrics(cases, reviews_done=3)
    assert (m["decided"], m["escalated"], m["closed"]) == (4, 2, 2)
    assert (m["waiting_review"], m["sent_back"]) == (2, 1)
    assert (m["final_escalated"], m["final_closed"], m["reviews_done"]) == (1, 1, 3)
    assert (m["matched"], m["model_right"]) == (2, 2)  # 1 and 3 right; 1 and 5 laundering
    assert m["ai_agreement"] == {"cases": 4, "agree": 3}  # only 5 disagrees (AI yes, closed)


def test_metrics_with_nothing_decided_are_all_zero():
    m = W.metrics([], reviews_done=0)
    assert m["decided"] == 0 and m["ai_agreement"] == {"cases": 0, "agree": 0}


def test_backlog_by_age_at_the_window_end():
    end = dt.datetime(2022, 9, 8, 16, 9)
    rows = [{"event_time": end - dt.timedelta(hours=h)} for h in (1, 23, 30, 47, 49, 50)]
    b = W.backlog(rows, end)
    assert (b["total"], b["under_24h"], b["h24_48"], b["over_48h"]) == (6, 2, 2, 2)
    assert b["oldest"] == end - dt.timedelta(hours=50)
    assert W.backlog([], end) == {"total": 0, "under_24h": 0, "h24_48": 0, "over_48h": 0,
                                  "oldest": None}  # fmt: skip


def test_the_qa_sample_is_fixed_by_its_seed_and_checked_blind_against_the_key():
    closed = [case("closed", "close", eid % 3 == 0, eid=eid) for eid in range(1, 21)]
    a, b = W.qa_sample(closed, seed="me"), W.qa_sample(closed, seed="me")
    assert [c["event_id"] for c in a] == [c["event_id"] for c in b] and len(a) == 5
    assert all(c["ok"] == (not c["is_laundering"]) for c in a)
    assert W.qa_sample(closed[:2], seed="x") and len(W.qa_sample(closed[:2], seed="x")) == 2
