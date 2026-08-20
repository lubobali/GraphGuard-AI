"""The leakage guard must catch the mistakes it exists to catch.

These are behaviour tests: they check that specific bad code is rejected and
specific good code is accepted. If the guard ever stops catching these, the
leakage contract is unenforced and the suite says so.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "guards"))

from leakage_guard import check_source  # noqa: E402


@pytest.mark.unit
def test_builder_without_cutoff_is_rejected():
    source = """
def build_account_features(df):
    return df.group_by("account").len()
"""
    problems = check_source("src/graphguard/features/x.py", source)
    assert len(problems) == 1
    assert "no time cutoff" in problems[0]


@pytest.mark.unit
def test_builder_with_cutoff_is_accepted():
    source = """
def build_account_features(df, as_of):
    return df.filter(df["ts"] < as_of).group_by("account").len()
"""
    assert check_source("src/graphguard/features/x.py", source) == []


@pytest.mark.unit
@pytest.mark.parametrize("param", ["as_of", "cutoff", "as_of_ts", "cutoff_ts"])
def test_any_recognised_cutoff_name_is_accepted(param):
    source = f"def compute_degree(df, {param}):\n    return df\n"
    assert check_source("src/graphguard/features/x.py", source) == []


@pytest.mark.unit
def test_keyword_only_cutoff_is_accepted():
    source = "def build_x(df, *, as_of):\n    return df\n"
    assert check_source("src/graphguard/features/x.py", source) == []


@pytest.mark.unit
def test_label_column_is_rejected():
    source = """
def build_x(df, as_of):
    return df.select("is_laundering")
"""
    problems = check_source("src/graphguard/features/x.py", source)
    assert len(problems) == 1
    assert "forbidden column" in problems[0]


@pytest.mark.unit
def test_non_builder_function_is_not_required_to_have_cutoff():
    source = "def helper(df):\n    return df\n"
    assert check_source("src/graphguard/features/x.py", source) == []


@pytest.mark.unit
def test_allowlisted_file_is_skipped(monkeypatch):
    import leakage_guard

    monkeypatch.setitem(leakage_guard.ALLOWLIST, "src/graphguard/features/x.py", "reason")
    source = "def build_x(df):\n    return df\n"
    assert check_source("src/graphguard/features/x.py", source) == []


@pytest.mark.unit
def test_allowlisting_one_function_leaves_the_rest_of_the_file_guarded(monkeypatch):
    """Per-function exemptions must not disarm the whole file."""
    import leakage_guard

    rel = "src/graphguard/features/x.py"
    monkeypatch.setitem(leakage_guard.ALLOWLIST, f"{rel}::build_safe", "row-level only")

    source = """
def build_safe(df):
    return df

def build_unsafe(df):
    return df.group_by("account").len()
"""
    problems = check_source(rel, source)
    assert len(problems) == 1
    assert "build_unsafe" in problems[0]


@pytest.mark.unit
def test_label_reference_inside_a_function_is_still_rejected():
    """Scoping the check to function bodies must not let real leakage through."""
    source = """
def helper(df, as_of):
    return df.select("is_laundering")
"""
    problems = check_source("src/graphguard/features/x.py", source)
    assert len(problems) == 1
    assert "forbidden column" in problems[0]


@pytest.mark.unit
def test_module_level_schema_declaration_is_not_a_violation():
    """A contract saying the label must be 0 or 1 is not feature code."""
    source = """
SCHEMA = {"is_laundering": "int in {0,1}"}
"""
    assert check_source("src/graphguard/features/x.py", source) == []
