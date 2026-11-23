"""S7.18: the three "try one case" alerts are picked by a rule, and the static tour file is
exactly what the database says (no drift, no other alert's answer)."""

import json

import pytest

from graphguard.demo import tour
from graphguard.demo import workflow as W

pytestmark = pytest.mark.unit


def cand(eid, rank, laundering, ptype=None, payments=7, reasons=3, reviews=2):
    return {"event_id": eid, "rank": rank, "is_laundering": laundering, "pattern_type": ptype,
            "payments": payments, "reasons": reasons, "reviews": reviews}  # fmt: skip


def test_the_rule_picks_two_ring_types_and_one_clean_lowest_rank_first():
    cs = [cand(1, 1, False), cand(2, 2, True, "STACK"), cand(3, 3, True, "STACK"),
          cand(4, 4, False), cand(5, 5, True, "FAN-IN")]  # fmt: skip
    assert [c["event_id"] for c in tour.pick(cs)] == [2, 1, 5]  # laundering, clean, laundering


@pytest.mark.parametrize("bad", [
    cand(9, 61, True, "CYCLE"),              # outside the top 60
    cand(9, 1, True, "CYCLE", payments=13),  # picture too big
    cand(9, 1, True, "CYCLE", payments=2),   # too small to show anything
    cand(9, 1, True, "CYCLE", reasons=0),    # rules only, no model reason
    cand(9, 1, True, "CYCLE", reviews=1),    # no second opinion both ways
    cand(9, 1, True, None),                  # laundering outside a ring: no type to teach
    cand(W.DEMO_CASES[0][0], 1, True, "CYCLE"),  # Sam's case
])  # fmt: skip
def test_what_the_rule_refuses(bad):
    assert not tour.eligible(bad)


def test_too_few_candidates_is_an_error_not_a_shorter_tour():
    with pytest.raises(ValueError):
        tour.pick([cand(1, 1, False), cand(2, 2, True, "STACK")])


def test_the_committed_tour_file_has_three_cases_and_no_other_answers():
    data = json.loads(tour.OUT.read_text())
    cases = data["cases"]
    assert len(cases) == 3 and [c["answer"]["is_laundering"] for c in cases] == [True, False, True]
    assert len({c["answer"]["pattern_type"] for c in cases if c["answer"]["is_laundering"]}) == 2
    for c in cases:
        assert c["rank"] <= tour.TOP and 3 <= len(c["ring"]["edges"]) <= tour.MAX_PAYMENTS
        shown = {e["id"] for e in c["ring"]["edges"]}
        assert set(c["answer"]["ring_tx"]) <= shown  # only answers for payments in the picture
        assert {r["direction"] for r in c["reviews"]} == {"escalate", "close"}
        assert "laundering" not in json.dumps(c["ring"]) and "pattern" not in json.dumps(c["ring"])


def test_the_limit_line_is_the_home_pages_numbers():
    lim = json.loads(tour.OUT.read_text())["limits"]
    assert lim == {"checked": 211, "found": 167, "false_alarms": 44, "total": 1083}
