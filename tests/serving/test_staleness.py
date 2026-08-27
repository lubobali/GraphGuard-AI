"""Which materialisation a transaction gets, given a refresh schedule.

In production the online store is refreshed on a schedule, not per request. A
transaction therefore reads a snapshot taken some time before it arrived, and
how much that costs is a measurement, not an assumption.
"""

import datetime as dt

import pytest

from graphguard.serving.staleness import materialisation_points, snapshot_for

T0 = dt.datetime(2022, 9, 6, 0, 0)
END = dt.datetime(2022, 9, 7, 0, 0)


@pytest.mark.unit
def test_points_cover_the_window_at_the_refresh_interval():
    pts = materialisation_points(T0, END, dt.timedelta(hours=6))
    assert pts == [
        T0,
        T0 + dt.timedelta(hours=6),
        T0 + dt.timedelta(hours=12),
        T0 + dt.timedelta(hours=18),
    ]


@pytest.mark.unit
def test_a_transaction_reads_the_most_recent_earlier_snapshot():
    pts = materialisation_points(T0, END, dt.timedelta(hours=6))
    at = T0 + dt.timedelta(hours=7)
    assert snapshot_for(at, pts) == T0 + dt.timedelta(hours=6)


@pytest.mark.unit
def test_a_transaction_exactly_on_a_boundary_reads_that_snapshot():
    pts = materialisation_points(T0, END, dt.timedelta(hours=6))
    at = T0 + dt.timedelta(hours=6)
    assert snapshot_for(at, pts) == at


@pytest.mark.unit
def test_a_transaction_never_reads_a_future_snapshot():
    """The whole point. A snapshot taken after the transaction cannot be used."""
    pts = materialisation_points(T0, END, dt.timedelta(hours=6))
    at = T0 + dt.timedelta(hours=5)
    assert snapshot_for(at, pts) <= at


@pytest.mark.unit
def test_a_transaction_before_every_snapshot_gets_none():
    pts = materialisation_points(T0, END, dt.timedelta(hours=6))
    assert snapshot_for(T0 - dt.timedelta(hours=1), pts) is None


@pytest.mark.unit
def test_a_shorter_interval_gives_more_snapshots():
    six = materialisation_points(T0, END, dt.timedelta(hours=6))
    one = materialisation_points(T0, END, dt.timedelta(hours=1))
    assert len(one) > len(six)
