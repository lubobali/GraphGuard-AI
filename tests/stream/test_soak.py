"""The soak report's own arithmetic (S6.11)."""

from decimal import Decimal

import pytest

from graphguard.stream import soak

pytestmark = pytest.mark.unit


def test_percentiles_accept_postgres_decimals():
    # extract(epoch ...) comes back from Postgres as Decimal
    got = soak._percentiles([Decimal("0.5"), Decimal("1.5"), Decimal("2.5")])
    assert got["p50"] == 1.5 and got["max"] == 2.5


def test_percentiles_of_nothing_are_empty():
    assert soak._percentiles([]) == {}
