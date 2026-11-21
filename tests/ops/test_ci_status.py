"""`just ci-wait`: the verdict waits for every job and fails on any red one."""

import pytest

from graphguard.ops import ci_status as ci

pytestmark = pytest.mark.unit


def _s(*states):
    return {"statuses": [{"context": f"job{i}", "status": s} for i, s in enumerate(states)]}


@pytest.mark.parametrize(("status", "want"), [
    ({"statuses": []}, "pending"),
    (_s("success", "pending"), "pending"),
    (_s("success", "success"), "success"),
    (_s("success", "failure"), "failure"),
    (_s("pending", "error"), "failure"),
])  # fmt: skip
def test_verdict(status, want):
    assert ci.verdict(status) == want


def test_failed_jobs_are_named():
    assert ci.failed_jobs(_s("success", "failure")) == ["job1"]
