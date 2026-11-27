"""S8b.1: the public site never shows a named bank; the file is the database's (live test)."""

import re

import pytest

from graphguard.demo import banks

pytestmark = pytest.mark.unit


def test_named_banks_get_a_neutral_name_and_country_banks_stay():
    m = banks.mapping(["Russia Bank #21", "Bank of the West", "Acme Bancorp", "UK Bank #3"])
    assert m == {"Acme Bancorp": "USA Bank #1", "Bank of the West": "USA Bank #2"}


def test_the_committed_file_covers_only_named_banks_with_unique_neutral_names():
    m = banks.read()
    assert len(m) == 468 and len(set(m.values())) == len(m)
    assert not any(banks.GENERIC.match(k) for k in m)
    assert all(re.fullmatch(r"USA Bank #\d+", v) for v in m.values())
