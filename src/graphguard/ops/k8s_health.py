"""Is the scorer on k3s actually up, and is its image safe from GC?

Exists because the scorer pod sat in ImagePullBackOff for 18 days and nothing
noticed: k3s image GC deleted the image during a disk-full period, and with no
registry, ``imagePullPolicy: IfNotPresent`` had nowhere to pull from.

Run with ``just k8s-check``, which passes the image from the justfile's
``IMAGE_TAG`` so the version lives in one place. Exit code 0 means healthy; 1 means at least one
problem, each printed on its own line, so it can sit in cron or a timer.

The judgement (``assess_pods`` / ``assess_image``) is pure and unit tested.
Only ``main`` shells out to k3s.
"""

from __future__ import annotations

import json
import subprocess
import sys

NAMESPACE = "graphguard"
DEFAULT_IMAGE = "docker.io/graphguard/serving:0.1.3"

# Without these the Ray dashboard -- unauthenticated job submission, i.e. code
# execution -- is reachable from every Docker container on the box (S5.3).
# Ingress (S5.3) and egress (S5b.1): if any is missing the scorer is reachable from, or
# can reach, more than it should.
REQUIRED_POLICIES = (
    "default-deny-ingress",
    "allow-scoring-port",
    "default-deny-egress",
    "allow-scorer-egress",
)

# Pods in these phases have finished; they are leftovers, not the service.
_FINISHED = {"Succeeded", "Failed"}


def _is_ready(pod: dict) -> bool:
    for cond in pod.get("status", {}).get("conditions", []):
        if cond.get("type") == "Ready":
            return cond.get("status") == "True"
    return False


def _waiting_reasons(pod: dict) -> list[str]:
    reasons = []
    for cs in pod.get("status", {}).get("containerStatuses", []):
        waiting = cs.get("state", {}).get("waiting")
        if waiting and waiting.get("reason"):
            reasons.append(waiting["reason"])
    return reasons


def assess_pods(pods: dict) -> list[str]:
    """Problems with the live pods in ``kubectl get pods -o json`` output."""
    live = [p for p in pods.get("items", []) if p.get("status", {}).get("phase") not in _FINISHED]
    if not live:
        return [f"no pods running in namespace {NAMESPACE!r}"]

    problems = []
    for pod in live:
        if _is_ready(pod):
            continue
        name = pod.get("metadata", {}).get("name", "?")
        reasons = _waiting_reasons(pod)
        detail = ", ".join(reasons) if reasons else pod.get("status", {}).get("phase", "unknown")
        problems.append(f"pod {name} not ready: {detail}")
    return problems


def assess_image(image: str, inspect: dict | None) -> list[str]:
    """Problems with the serving image, given ``crictl inspecti`` output or None."""
    if inspect is None:
        return [f"image {image} missing from k3s containerd"]
    if not inspect.get("status", {}).get("pinned", False):
        return [f"image {image} not pinned: kubelet image GC may delete it"]
    return []


def assess_network_policies(policies: dict, required: tuple[str, ...]) -> list[str]:
    """Problems with ``kubectl get networkpolicy -o json`` output: any required one missing."""
    present = {p.get("metadata", {}).get("name") for p in policies.get("items", [])}
    return [
        f"network policy {name!r} missing: the scorer may be reachable or reach out too widely"
        for name in required
        if name not in present
    ]


def _run_json(cmd: list[str]) -> dict | None:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    image = argv[0] if argv else DEFAULT_IMAGE
    pods = _run_json(["k3s", "kubectl", "get", "pods", "-n", NAMESPACE, "-o", "json"])
    problems = ["could not query k3s for pods"] if pods is None else assess_pods(pods)
    policies = _run_json(["k3s", "kubectl", "get", "networkpolicy", "-n", NAMESPACE, "-o", "json"])
    problems += (
        ["could not query k3s for network policies"]
        if policies is None
        else assess_network_policies(policies, REQUIRED_POLICIES)
    )
    problems += assess_image(image, _run_json(["k3s", "crictl", "inspecti", "-o", "json", image]))

    if problems:
        for problem in problems:
            print(f"GRAPHGUARD K8S UNHEALTHY: {problem}", file=sys.stderr)
        return 1
    print(
        "graphguard k8s healthy: all pods ready, network policies in place, "
        f"{image} present and pinned"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
