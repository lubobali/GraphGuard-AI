"""The rules layer (S6.8): as-of inputs only, training-fitted thresholds, a written policy."""

import datetime as dt

import polars as pl
import pytest

from graphguard.stream import rules as R

pytestmark = pytest.mark.unit

TH = R.Thresholds(velocity_24h=10, fan_out=20, fan_in=30, large_amount=50_000.0)


def _f(sent24=0, out=0, inn=0):
    return {"sender_sent_last_24h": sent24, "sender_distinct_out_before": out,
            "receiver_distinct_in_before": inn}  # fmt: skip


def test_quiet_transactions_fire_nothing():
    assert R.fire(_f(), 100.0, False, False, TH) == ()


@pytest.mark.parametrize(("f", "amount", "cold", "want"), [
    (_f(sent24=11), 1.0, (False, False), ("velocity",)),
    (_f(sent24=10), 1.0, (False, False), ()),  # at the threshold: not above it
    (_f(out=21), 1.0, (False, False), ("fan_out",)),
    (_f(inn=31), 1.0, (False, False), ("fan_in",)),
    (_f(), 9_000.0, (False, False), ("structuring",)),
    (_f(), 9_999.99, (False, False), ("structuring",)),
    (_f(), 10_000.0, (False, False), ()),
    (_f(), 50_000.0, (True, False), ("new_account_large",)),
    (_f(), 49_999.0, (True, False), ()),
    (_f(), 1.0, (True, True), ("both_new",)),
])  # fmt: skip
def test_each_rule_fires_exactly_at_its_threshold(f, amount, cold, want):
    assert R.fire(f, amount, *cold, TH) == want


def test_a_hard_rule_or_two_rules_jump_the_queue_otherwise_the_score_decides():
    assert R.priority(0.01, ("both_new",)) > R.priority(0.99, ())
    assert R.priority(0.01, ("velocity", "fan_out")) > R.priority(0.99, ("velocity",))
    assert R.priority(0.3, ("velocity",)) == 0.3


def test_rules_only_ranks_more_rules_first_then_larger_amounts():
    assert R.rules_only_rank(("a", "b"), 1.0) > R.rules_only_rank(("a",), 1e11)
    assert R.rules_only_rank(("a",), 200.0) > R.rules_only_rank(("a",), 100.0)


def test_thresholds_are_quantiles_of_the_frame_given():
    train = pl.DataFrame({"sender_sent_last_24h": list(range(1000)),
                          "sender_distinct_out_before": list(range(1000)),
                          "receiver_distinct_in_before": list(range(1000)),
                          "amount_paid": [float(x) for x in range(1000)]})  # fmt: skip
    th = R.thresholds_from(train)
    assert th.velocity_24h == 999 and th.large_amount == 990.0


def test_cold_means_never_seen_in_either_role_before():
    t = dt.datetime(2022, 9, 1)
    frame = pl.DataFrame({"source_row": [0, 1, 2, 3],
                          "from_account": ["A", "B", "A", "C"],
                          "to_account": ["B", "C", "C", "C"]})  # fmt: skip
    got = R.cold_flags(frame).select("sender_cold", "receiver_cold").rows()
    # A new, B new | B seen (as receiver), C new | A seen, C seen | C seen (both sides)
    assert got == [(True, True), (False, True), (False, False), (False, False)]
    assert t  # keeps the datetime import meaningful for readers of the fixture


def test_the_shipped_thresholds_load_and_came_from_training():
    th = R.load()
    assert th.fitted_on == "train window"
    assert th.velocity_24h > 0 and th.large_amount > 0
