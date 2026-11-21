"""Late labels (S6.9): who learns the truth about a transaction, and when.

Pure simulation with a seed; the live part (topic, consumer table, gold) is checked live.
"""

import datetime as dt

import pytest

from graphguard.stream import labels as L

pytestmark = pytest.mark.unit

T0 = dt.datetime(2022, 9, 6, 13, 34)
POLICY = L.Policy(capacity_per_day=3, investigation_days=(1, 14), external_days=(30, 60), seed=1)


def _tx(i, hours, laundering, alert, priority=0.5):
    return L.Tx(event_id=i, event_time=T0 + dt.timedelta(hours=hours), laundering=laundering,
                alert=alert, priority=priority)  # fmt: skip


def test_only_investigated_alerts_and_externally_reported_laundering_get_labels():
    txs = [_tx(1, 0, True, True), _tx(2, 0, False, True), _tx(3, 0, True, False),
           _tx(4, 0, False, False)]  # fmt: skip
    got = {lab.event_id: lab for lab in L.simulate(txs, POLICY)}
    assert set(got) == {1, 2, 3}  # 4: clean and never alerted -> unknown, not "innocent"
    assert got[1].channel == got[2].channel == "investigation"
    assert got[3].channel == "external report"
    assert got[1].label is True and got[2].label is False and got[3].label is True


def test_delays_stay_inside_the_stated_ranges():
    txs = [_tx(i, i, i % 2 == 0, i % 3 == 0) for i in range(300)]
    for lab in L.simulate(txs, L.Policy(capacity_per_day=1000, seed=3)):
        days = (lab.label_known_at - lab.event_time).total_seconds() / 86400
        lo, hi = (1, 14) if lab.channel == "investigation" else (30, 60)
        assert lo <= days <= hi


def test_capacity_limits_how_many_alerts_are_investigated_each_day_highest_priority_first():
    txs = [_tx(i, 1, False, True, priority=i / 10) for i in range(10)]  # one day, 10 alerts
    investigated = [lab for lab in L.simulate(txs, POLICY) if lab.channel == "investigation"]
    assert sorted(lab.event_id for lab in investigated) == [7, 8, 9]  # top 3 by priority


def test_the_same_seed_gives_the_same_labels():
    txs = [_tx(i, i, i % 5 == 0, i % 4 == 0) for i in range(100)]
    assert L.simulate(txs, POLICY) == L.simulate(txs, POLICY)


def test_known_as_of_hides_labels_from_the_future():
    txs = [_tx(1, 0, True, True), _tx(2, 0, True, False)]
    labels = L.simulate(txs, L.Policy(capacity_per_day=10, seed=0))
    early = L.known_as_of(labels, T0 + dt.timedelta(hours=1))
    assert early == []  # nothing is known an hour later
    late = L.known_as_of(labels, T0 + dt.timedelta(days=61))
    assert {lab.event_id for lab in late} == {1, 2}


def test_inside_a_50_hour_window_almost_nothing_is_known():
    # ~50 h of traffic, alerts on 10%: with >= 1 day delays only a sliver arrives in time.
    txs = [_tx(i, i * 50 / 1000, i % 10 == 0, i % 10 == 0, priority=1.0) for i in range(1000)]
    labels = L.simulate(txs, L.Policy(capacity_per_day=100, seed=5))
    end = T0 + dt.timedelta(hours=50)
    known = L.known_as_of(labels, end)
    assert len(known) < 0.3 * len(labels)
    assert all(lab.channel == "investigation" for lab in known)  # external reports take >= 30 days
