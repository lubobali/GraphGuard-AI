"""The demo copy (S7.1): its order, its names, its answer key kept apart, its fingerprint."""

import datetime as dt

import polars as pl
import pytest

from graphguard.demo import build as b

pytestmark = pytest.mark.unit

T = dt.datetime(2022, 9, 6, 13, 34)


def _decisions():
    return pl.DataFrame(
        {
            "event_id": [10, 11, 12, 13],
            "event_time": [T, T, T + dt.timedelta(minutes=1), T + dt.timedelta(minutes=2)],
            "score": [0.2, 0.9, 0.9, 0.1],
            "rules": [[], [], [], ["fan_in", "structuring"]],  # two rules -> above all (ADR 0007)
        }
    )


def test_rank_follows_the_queue_order_ties_by_event_order():
    out = b.ranked(_decisions())
    order = out.sort("rank")["event_id"].to_list()
    assert order == [13, 11, 12, 10]  # two rules first; 0.9 tie -> earlier event first
    assert out.filter(pl.col("event_id") == 13)["priority"].item() == pytest.approx(1.1)


def test_percentile_is_the_share_ranked_below():
    out = b.ranked(_decisions()).sort("rank")
    assert out["percentile"].to_list() == [75.0, 50.0, 25.0, 0.0]


def test_account_names_join_on_bank_and_account_together():
    accounts = pl.DataFrame(
        {
            "Bank Name": ["Bank A", "Bank B"],
            "Bank ID": [28248, 27755],
            "Account Number": ["80A7FD400", "80A7FD400"],  # same number, two banks
            "Entity ID": ["e1", "e2"],
            "Entity Name": ["Partnership #1", "Corporation #2"],
        }
    )
    acc = b.accounts_table(accounts)
    tx = pl.DataFrame({"from_bank": ["027755"], "from_account": ["80A7FD400"],
                       "to_bank": ["028248"], "to_account": ["80A7FD400"]})  # fmt: skip
    named = b.with_names(tx, acc)
    assert named["from_name"].item() == "Corporation #2"
    assert named["to_name"].item() == "Partnership #1"
    assert named["from_bank_name"].item() == "Bank B"


def test_an_unknown_account_gets_no_name_rather_than_a_wrong_one():
    acc = b.accounts_table(pl.DataFrame({"Bank Name": ["A"], "Bank ID": [1],
        "Account Number": ["X"], "Entity ID": ["e"], "Entity Name": ["N"]}))  # fmt: skip
    tx = pl.DataFrame({"from_bank": ["2"], "from_account": ["X"], "to_bank": ["1"],
                       "to_account": ["X"]})  # fmt: skip
    named = b.with_names(tx, acc)
    assert named["from_name"].item() is None and named["to_name"].item() == "N"


def test_the_answer_key_is_split_out_of_the_queue_table():
    df = pl.DataFrame({"event_id": [1, 2], "score": [0.1, 0.2], "is_laundering": [0, 1]})
    tx, truth = b.split_truth(df)
    assert "is_laundering" not in tx.columns
    assert truth.to_dicts() == [{"event_id": 1, "is_laundering": False},
                                {"event_id": 2, "is_laundering": True}]  # fmt: skip


def test_the_fingerprint_is_stable_and_order_independent():
    df = pl.DataFrame({"event_id": [2, 1], "x": [0.5, 0.25]})
    assert b.fingerprint(df) == b.fingerprint(df.reverse())
    assert b.fingerprint(df) != b.fingerprint(df.with_columns(pl.col("x") + 1))


def test_refuses_an_incomplete_or_mixed_stream():
    with pytest.raises(b.DemoBuildError, match="incomplete"):
        b.check_complete(decided=1000, expected=1015300, versions=["m1"])
    with pytest.raises(b.DemoBuildError, match="model version"):
        b.check_complete(decided=5, expected=5, versions=["m1", "m2"])
    b.check_complete(decided=5, expected=5, versions=["m1"])  # fine


def test_the_fingerprint_covers_list_columns():
    df = pl.DataFrame({"event_id": [1], "rules": [["fan_in"]], "features": [[0.1, 0.2]]})
    changed = pl.DataFrame({"event_id": [1], "rules": [["fan_in"]], "features": [[0.1, 0.3]]})
    assert b.fingerprint(df) != b.fingerprint(changed)


def test_the_fast_priority_is_exactly_the_streams_priority():
    from graphguard.stream.rules import RULES, priority

    cases = [[], ["fan_in"], ["both_new"], ["fan_in", "structuring"], list(RULES)]
    df = pl.DataFrame({"event_id": list(range(len(cases))), "event_time": [T] * len(cases),
                       "score": [0.3] * len(cases), "rules": cases})  # fmt: skip
    got = b.ranked(df).sort("event_id")["priority"].to_list()
    assert got == [priority(0.3, tuple(r)) for r in cases]
