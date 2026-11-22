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


# --- the lakehouse's sealed namespace (S5.6a) --------------------------------
# Test-window rows live in the Iceberg namespace "sealed". Naming it is how code
# reads it, so outside the allowlisted writer, naming it counts as a test load.

from test_set_touch_check import find_sealed_refs  # noqa: E402


@pytest.mark.unit
def test_sealed_table_literal_is_found():
    hits = find_sealed_refs("src/graphguard/m.py", 'cat.load_table("sealed.transactions")\n')
    assert len(hits) == 1


@pytest.mark.unit
def test_bare_sealed_namespace_is_found():
    hits = find_sealed_refs("src/graphguard/m.py", 'NS = "sealed"\n')
    assert len(hits) == 1


@pytest.mark.unit
def test_other_namespaces_are_ignored():
    src = 'cat.load_table("silver.transactions")\ncat.load_table("gold.labels")\n'
    assert find_sealed_refs("src/graphguard/m.py", src) == []


@pytest.mark.unit
def test_words_containing_sealed_are_ignored():
    assert find_sealed_refs("src/graphguard/m.py", 'msg = "the envelope was unsealed"\n') == []


# --- S7.2: raw files hold every window; naming them must be a listed decision --------------
@pytest.mark.unit
def test_features_for_split_on_the_test_window_counts_as_a_test_load():
    hits = find_test_loads("src/graphguard/m.py", 'features_for_split(lf, "test", b)\n')
    assert len(hits) == 1


@pytest.mark.unit
@pytest.mark.parametrize("name", ["TRANSACTIONS_FILE", "PATTERNS_FILE"])
def test_naming_a_raw_file_is_found(name):
    from test_set_touch_check import find_raw_refs

    src = f"from graphguard.config import {name}\nx = load({name})\n"
    assert len(find_raw_refs("src/graphguard/m.py", src)) >= 1


@pytest.mark.unit
def test_the_accounts_file_is_not_a_raw_window_file():
    from test_set_touch_check import find_raw_refs

    # account names carry no time window (S7.1 reads them)
    src = "from graphguard.config import ACCOUNTS_FILE\n"
    assert find_raw_refs("src/graphguard/m.py", src) == []


@pytest.mark.unit
def test_every_raw_reader_in_the_tree_is_listed_with_a_reason():
    import test_set_touch_check as g

    for rel, reason in g.RAW_ALLOWLIST.items():
        assert (g.REPO_ROOT / rel).exists(), rel
        assert len(reason) > 20, rel
    assert "src/graphguard/demo/build.py" not in g.RAW_ALLOWLIST  # the screens never do
    assert g.main() == 0
