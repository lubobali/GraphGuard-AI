"""The k8s health check must make a dead scorer impossible to miss.

The scorer sat in ImagePullBackOff for 18 days because nothing looked. These
tests feed the check the JSON kubectl and crictl return, so only the external
command is faked; the judgement is the real code.
"""

import pytest

from graphguard.ops.k8s_health import assess_image, assess_pods

pytestmark = pytest.mark.unit

IMAGE = "docker.io/graphguard/serving:0.1.2"


def _pod(name="scorer-head-abc", phase="Running", ready=True, state=None):
    state = state or {"running": {"startedAt": "2026-11-18T02:13:43Z"}}
    return {
        "metadata": {"name": name, "namespace": "graphguard"},
        "status": {
            "phase": phase,
            "conditions": [{"type": "Ready", "status": "True" if ready else "False"}],
            "containerStatuses": [
                {"name": "ray-head", "image": IMAGE, "ready": ready, "state": state}
            ],
        },
    }


def _pods(*items):
    return {"items": list(items)}


def test_a_ready_pod_is_healthy():
    assert assess_pods(_pods(_pod())) == []


def test_no_pods_at_all_is_a_problem():
    # A deleted deployment must not read as "nothing wrong".
    problems = assess_pods(_pods())
    assert len(problems) == 1
    assert "no pods" in problems[0].lower()


@pytest.mark.regression
def test_image_pull_backoff_is_reported_with_its_reason():
    # The exact failure that went unnoticed for 18 days.
    pod = _pod(
        phase="Pending",
        ready=False,
        state={"waiting": {"reason": "ImagePullBackOff", "message": "pull access denied"}},
    )
    problems = assess_pods(_pods(pod))
    assert len(problems) == 1
    assert "ImagePullBackOff" in problems[0]
    assert "scorer-head-abc" in problems[0]


def test_crash_loop_is_reported():
    pod = _pod(ready=False, state={"waiting": {"reason": "CrashLoopBackOff"}})
    assert "CrashLoopBackOff" in assess_pods(_pods(pod))[0]


def test_running_but_not_ready_is_a_problem():
    # Running is not serving: a pod that never passes readiness is down.
    problems = assess_pods(_pods(_pod(ready=False)))
    assert len(problems) == 1
    assert "not ready" in problems[0].lower()


def test_finished_pods_are_ignored():
    # Evicted / completed leftovers are noise, not an outage, as long as a
    # healthy pod exists alongside them.
    evicted = _pod(name="old", phase="Failed", ready=False, state={"terminated": {}})
    assert assess_pods(_pods(_pod(), evicted)) == []


def test_only_finished_pods_counts_as_no_pods():
    evicted = _pod(name="old", phase="Failed", ready=False, state={"terminated": {}})
    assert "no pods" in assess_pods(_pods(evicted))[0].lower()


def test_a_pinned_image_is_fine():
    assert assess_image(IMAGE, {"status": {"pinned": True}}) == []


@pytest.mark.regression
def test_an_unpinned_image_is_a_problem():
    # Unpinned, kubelet's image GC may delete it under disk pressure; with no
    # registry, IfNotPresent then has nowhere to pull from.
    problems = assess_image(IMAGE, {"status": {"pinned": False}})
    assert len(problems) == 1
    assert "not pinned" in problems[0]


def test_a_missing_image_is_a_problem():
    problems = assess_image(IMAGE, None)
    assert len(problems) == 1
    assert "missing" in problems[0]
