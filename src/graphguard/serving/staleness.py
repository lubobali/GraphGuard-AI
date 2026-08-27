"""Scheduling for the online store, and the staleness it introduces.

The online store is refreshed on a schedule, not per request -- refreshing per
request would mean recomputing the history the store exists to avoid. So a
transaction reads a snapshot taken some time before it arrived, and its view of
the account is that much out of date.

How much that costs is measured (`measure_staleness.py`), not assumed. The
answer is the refresh interval the system runs at.
"""

from __future__ import annotations

import bisect
import datetime as dt


def materialisation_points(
    start: dt.datetime, end: dt.datetime, interval: dt.timedelta
) -> list[dt.datetime]:
    """Every instant the store is rebuilt, across a window."""
    if interval <= dt.timedelta(0):
        raise ValueError("refresh interval must be positive")

    points, at = [], start
    while at < end:
        points.append(at)
        at += interval
    return points


def snapshot_for(at: dt.datetime, points: list[dt.datetime]) -> dt.datetime | None:
    """The most recent snapshot at or before `at`.

    Never a later one: a snapshot taken after the transaction contains the
    transaction's own future, which is the leakage this whole project is
    organised against.
    """
    index = bisect.bisect_right(points, at)
    return points[index - 1] if index else None
