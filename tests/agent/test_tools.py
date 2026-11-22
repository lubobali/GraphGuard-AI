"""The agent's tools never reach the answer key (S7.10)."""

import os

import pytest

from graphguard.agent import template, tools
from graphguard.config import REPO_ROOT


@pytest.mark.unit
def test_no_tool_can_reach_the_answer_key(code_words):
    for mod in (tools, template):
        code = " ".join(code_words(mod)).lower()
        for forbidden in ("truth", "answer", "is_laundering", "pattern_type"):
            assert forbidden not in code, (mod.__name__, forbidden)
    assert tools.TOOLS == ("get_alert", "get_reasons", "get_ring", "get_history")


class Spy:
    """Records which repo methods the tools call: only `alert` is allowed."""

    def __init__(self, real):
        self.real, self.calls = real, []

    def __getattr__(self, name):
        self.calls.append(name)
        return getattr(self.real, name)


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1"
    or not (REPO_ROOT / ".secrets" / "demo-api.env").exists(),
    reason="no demo database here",
)
def test_tools_use_only_the_alert_view_and_the_template_is_fully_supported():
    import json

    from graphguard.agent import checker
    from graphguard.demo.queries import PgRepo

    spy = Spy(PgRepo())
    cases = json.loads((REPO_ROOT / "docs/analysis/s7.10-evalset.json").read_text())["cases"]
    for c in cases[:16]:
        for name in tools.TOOLS:
            getattr(tools, name)(spy, c["event_id"])
        out = checker.check_report(template.report(spy, c["event_id"]),
                                   tools.evidence(spy, c["event_id"]))  # fmt: skip
        assert out["n_unsupported"] == 0, out["dropped"]
    assert set(spy.calls) == {"alert"}
