"""The claim checker (S7.10): only what the evidence says is supported."""

import pytest

from graphguard.agent import checker as C

pytestmark = pytest.mark.unit

EVIDENCE = {
    10: {"id": 10, "from": "Corp A", "to": "Corp B", "amount": 9500.0, "currency": "Euro",
         "t": "2022-09-07 12:00"},
    2: {"id": 2, "from": "Corp U", "to": "Corp A", "amount": 9612.34, "currency": "Euro",
        "t": "2022-09-07 11:00"},
}  # fmt: skip


def check(**claim):
    return C.check_claim({"text": "x", "cites": [10], **claim}, EVIDENCE)


def test_a_cited_amount_time_and_relation_that_match_are_supported():
    assert check(amount={"value": 9500, "currency": "Euro"}).supported
    assert check(time="2022-09-07 12:00").supported
    assert check(relation={"from": "Corp A", "to": "Corp B"}).supported


@pytest.mark.parametrize(
    "claim",
    [
        {"cites": [999]},  # not in the evidence
        {"cites": []},  # cites nothing
        {"amount": {"value": 9600, "currency": "Euro"}},  # wrong amount
        {"amount": {"value": 9500, "currency": "US Dollar"}},  # wrong currency
        {"time": "2022-09-07 13:00"},  # wrong time
        {"relation": {"from": "Corp B", "to": "Corp A"}},  # wrong direction
        {"count": 3},  # counts 1 cited payment, says 3
    ],
)
def test_anything_the_evidence_does_not_say_is_unsupported(claim):
    assert not check(**claim).supported


def test_a_made_up_number_in_the_prose_is_caught():
    assert not C.check_claim({"text": "It moved 12,000 Euro.", "cites": [10]}, EVIDENCE).supported
    assert C.check_claim({"text": "It moved 9,500 Euro.", "cites": [10]}, EVIDENCE).supported
    assert C.check_claim(
        {"text": "Two payments 1 hour apart.", "cites": [10, 2]}, EVIDENCE
    ).supported


def test_the_report_keeps_only_supported_claims_and_counts_the_rest():
    report = {"summary": "s", "typology": "FAN-OUT", "claims": [
        {"text": "ok", "cites": [10]}, {"text": "bad", "cites": [999]}]}  # fmt: skip
    out = C.check_report(report, EVIDENCE)
    assert out["n_claims"] == 2 and out["n_unsupported"] == 1
    assert [c["text"] for c in out["kept"]] == ["ok"]
    assert out["dropped"][0]["why"]


def test_wilson_interval():
    lo, hi = C.wilson(0, 50)
    assert lo == 0.0 and 0.06 < hi < 0.08
    lo, hi = C.wilson(5, 100)
    assert lo < 0.05 < hi


def test_numbers_that_are_part_of_a_cited_name_are_not_invented_amounts():
    ev = {7: {"id": 7, "from": "Corporation #35871", "to": "Partnership #2", "amount": 10.0,
              "currency": "Euro", "t": "2022-09-07 12:00"}}  # fmt: skip
    assert C.check_claim({"text": "Corporation #35871 paid 10 Euro.", "cites": [7]}, ev).supported
    # ...but a name number from an UNcited payment is still not evidence
    assert not C.check_claim(
        {"text": "Corporation #99999 paid 10 Euro.", "cites": [7]}, ev
    ).supported
