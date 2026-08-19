"""The test-set guard must count real load sites and ignore the rest."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "guards"))

from test_set_touch_check import find_test_loads  # noqa: E402


@pytest.mark.unit
def test_positional_test_load_is_found():
    hits = find_test_loads("src/graphguard/m.py", 'load_split("test")\n')
    assert len(hits) == 1


@pytest.mark.unit
def test_keyword_test_load_is_found():
    hits = find_test_loads("src/graphguard/m.py", 'load_split(name="test")\n')
    assert len(hits) == 1


@pytest.mark.unit
def test_method_call_is_found():
    hits = find_test_loads("src/graphguard/m.py", 'data.load_split("test")\n')
    assert len(hits) == 1


@pytest.mark.unit
@pytest.mark.parametrize("split", ["train", "validation"])
def test_other_splits_are_ignored(split):
    assert find_test_loads("src/graphguard/m.py", f'load_split("{split}")\n') == []


@pytest.mark.unit
def test_unrelated_call_is_ignored():
    assert find_test_loads("src/graphguard/m.py", 'print("test")\n') == []


@pytest.mark.unit
def test_multiple_sites_are_all_reported():
    source = 'load_split("test")\nload_split("test")\n'
    assert len(find_test_loads("src/graphguard/m.py", source)) == 2
