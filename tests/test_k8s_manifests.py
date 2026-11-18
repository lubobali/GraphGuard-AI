"""The scorer's Kubernetes manifests stay locked down (S5b.1)."""

import pytest
import yaml

from graphguard.config import REPO_ROOT

pytestmark = pytest.mark.unit

K8S = REPO_ROOT / "k8s"


def _docs(name):
    return [d for d in yaml.safe_load_all((K8S / name).read_text()) if d]


def _head_pod():
    (rs,) = _docs("rayservice.yaml")
    return rs["spec"]["rayClusterConfig"]["headGroupSpec"]["template"]["spec"]


def test_the_namespace_enforces_pod_security_restricted():
    (ns,) = _docs("namespace.yaml")
    labels = ns["metadata"]["labels"]
    for mode in ("enforce", "warn", "audit"):
        assert labels[f"pod-security.kubernetes.io/{mode}"] == "restricted"


def test_the_scorer_pod_is_restricted():
    pod = _head_pod()
    assert pod["automountServiceAccountToken"] is False
    sc = pod["securityContext"]
    assert sc["runAsNonRoot"] is True and sc["runAsUser"] != 0
    assert sc["seccompProfile"]["type"] == "RuntimeDefault"
    for c in pod["containers"]:
        csc = c["securityContext"]
        assert csc["allowPrivilegeEscalation"] is False
        assert csc["readOnlyRootFilesystem"] is True
        assert csc["capabilities"]["drop"] == ["ALL"]


def test_the_redis_password_never_sits_in_the_manifest():
    for c in _head_pod()["containers"]:
        env = {e["name"]: e for e in c.get("env", [])}
        url = env["GRAPHGUARD_REDIS_URL"]
        assert "value" not in url and url["valueFrom"]["secretKeyRef"]["name"] == "graphguard-redis"


def test_egress_is_denied_by_default_and_opened_only_for_dns_redis_and_ray():
    policies = {d["metadata"]["name"]: d for d in _docs("networkpolicy.yaml")}
    deny = policies["default-deny-egress"]["spec"]
    assert deny["podSelector"] == {} and deny["policyTypes"] == ["Egress"] and "egress" not in deny
    rules = policies["allow-scorer-egress"]["spec"]["egress"]
    ports = sorted(p["port"] for r in rules for p in r.get("ports", []))
    assert ports == [53, 53, 6379]  # DNS (udp+tcp) and Redis; nothing else by port
    cidrs = [b["ipBlock"]["cidr"] for r in rules for b in r["to"] if "ipBlock" in b]
    assert cidrs == ["172.25.0.0/16"] and "0.0.0.0/0" not in cidrs
