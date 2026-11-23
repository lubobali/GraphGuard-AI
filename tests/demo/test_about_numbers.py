"""The About page's fixed numbers (S7.9) equal their committed sources."""

import json
import re

import pytest

from graphguard.config import REPO_ROOT

pytestmark = pytest.mark.unit

N = json.loads((REPO_ROOT / "web" / "lib" / "aboutNumbers.json").read_text())
RULES = json.loads((REPO_ROOT / "docs" / "analysis" / "s6.8-rules.json").read_text())
CAP = json.loads((REPO_ROOT / "docs" / "analysis" / "s7.3-capacity.json").read_text())["rankings"]
CAL = json.loads((REPO_ROOT / "docs" / "analysis" / "finding-018-calendar.json").read_text())


def test_numbers_from_the_analysis_files():
    p = N["pr_auc"]
    assert p["model"]["value"] == RULES["model_only"]["pr_auc"]
    assert p["rules"]["value"] == RULES["rules_only"]["pr_auc"]
    assert p["model_without_weekday"]["value"] == CAL["variants"]["without weekday"]["pr_auc"]
    for k in ("model", "rules", "random"):
        assert N["caught_at_5000"][k]["value"] == CAP[k]["5000"]["caught"]
    assert N["rings_caught_at_5000"]["value"] == CAP["model"]["5000"]["rings_caught"]
    assert N["rings_caught_at_5000"]["of"] == CAP["model"]["5000"]["rings_total"]
    assert N["laundering_in_window"]["value"] == RULES["laundering"]
    assert N["transactions_in_window"]["value"] == RULES["validation_rows"]


def test_numbers_quoted_in_the_findings_and_the_comparison():
    findings = (REPO_ROOT / "docs" / "findings.md").read_text()
    comparison = (REPO_ROOT / "docs" / "model_comparison.md").read_text()
    for key in ("by_amount", "random"):
        assert f"{N['pr_auc'][key]['value']:.5f}" in findings
    assert re.search(r"0\.0447", comparison)


def test_where_the_numbers_come_from_matches_the_frozen_split():
    """S7.12: the home page's "where the numbers come from" panel (counts only, no data read)."""
    split = json.loads((REPO_ROOT / "data" / "splits" / "frozen_split.json").read_text())
    s = N["split"]
    assert s["tail_rows_dropped"]["value"] == split["tail_rows_dropped"]
    for part, key in (("learn", "train"), ("shown", "validation"), ("locked", "test")):
        assert s[part]["transactions"] == split["splits"][key]["transactions"], part
        assert s[part]["laundering"] == split["splits"][key]["laundering"], part
    assert s["shown"]["transactions"] == N["transactions_in_window"]["value"]
    assert s["shown"]["laundering"] == N["laundering_in_window"]["value"]
    assert f"{s['file_rows']['value']:,}" in (REPO_ROOT / "CLAUDE.md").read_text()
