"""The scorer's Kubernetes manifests stay locked down (S5b.1)."""

import json

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


def test_the_load_generator_pod_is_restricted_capped_and_reaches_only_the_scorer():
    from graphguard.serving.perf_k8s import LABEL, job_manifest

    job = job_manifest("x", [10], 1, 1, 1)
    pod = job["spec"]["template"]["spec"]
    (c,) = pod["containers"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    assert c["securityContext"] == {
        "allowPrivilegeEscalation": False,
        "readOnlyRootFilesystem": True,
        "capabilities": {"drop": ["ALL"]},
    }
    assert c["resources"]["limits"] == {"cpu": "1", "memory": "256Mi"}
    (np,) = _docs("loadgen-networkpolicy.yaml")
    assert np["spec"]["podSelector"]["matchLabels"] == {"app": LABEL}
    assert np["spec"]["policyTypes"] == ["Egress"]
    ports = [p["port"] for rule in np["spec"]["egress"] for p in rule["ports"]]
    assert sorted(ports) == [53, 53, 8000]  # DNS and the scorer, nothing else


def test_the_scorer_reaches_only_s3_on_443():
    import ipaddress

    from graphguard.serving.model_k8s import POLICY_FILE

    (np,) = [d for d in yaml.safe_load_all(POLICY_FILE.read_text()) if d]
    assert np["spec"]["podSelector"]["matchLabels"] == {"ray.io/is-ray-node": "yes"}
    (rule,) = np["spec"]["egress"]
    assert rule["ports"] == [{"protocol": "TCP", "port": 443}]
    nets = [ipaddress.ip_network(t["ipBlock"]["cidr"]) for t in rule["to"]]
    assert nets and all(n.is_global for n in nets)  # never the box, the pods or a LAN
    assert not any(n.prefixlen < 8 for n in nets)  # nothing like 0.0.0.0/0


def test_s3_prefixes_take_only_s3_in_the_region():
    from graphguard.serving.model_k8s import s3_prefixes

    ranges = {"prefixes": [
        {"ip_prefix": "52.216.0.0/15", "service": "S3", "region": "us-east-1"},
        {"ip_prefix": "52.216.0.0/15", "service": "S3", "region": "us-east-1"},
        {"ip_prefix": "3.5.0.0/16", "service": "S3", "region": "eu-west-1"},
        {"ip_prefix": "3.80.0.0/12", "service": "EC2", "region": "us-east-1"},
    ]}  # fmt: skip
    assert s3_prefixes(ranges) == ["52.216.0.0/15"]


def test_the_model_secret_carries_only_the_reader_key():
    import base64
    import json

    from graphguard.serving.model_k8s import secret_manifest

    m = json.loads(secret_manifest({"AWS_ACCESS_KEY_ID": "id", "AWS_SECRET_ACCESS_KEY": "s",
                                    "AWS_REGION": "us-east-1", "OTHER": "x"}))  # fmt: skip
    assert set(m["data"]) == {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"}
    assert base64.b64decode(m["data"]["AWS_ACCESS_KEY_ID"]) == b"id"


def test_the_scorer_pins_its_model_by_version_and_hash_and_takes_the_key_from_a_secret():
    import re

    (rs,) = _docs("rayservice.yaml")
    (c,) = rs["spec"]["rayClusterConfig"]["headGroupSpec"]["template"]["spec"]["containers"]
    env = {e["name"]: e for e in c["env"]}
    assert re.fullmatch(r"xgb-[0-9a-f]{12}", env["GRAPHGUARD_MODEL_VERSION"]["value"])
    assert re.fullmatch(r"[0-9a-f]{64}", env["GRAPHGUARD_MODEL_SHA256"]["value"])
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        assert "value" not in env[k]
        assert env[k]["valueFrom"]["secretKeyRef"]["name"] == "graphguard-model"
    assert "GRAPHGUARD_BUNDLE" not in env


def test_the_image_carries_no_model():
    from graphguard.config import REPO_ROOT

    assert "models/production" not in (REPO_ROOT / "Dockerfile").read_text().split("# No model")[1]


# --- the stream consumer (S6.6) --------------------------------------------------------
def _consumer():
    docs = _docs("consumer.yaml")
    (dep,) = [d for d in docs if d["kind"] == "Deployment"]
    (np,) = [d for d in docs if d["kind"] == "NetworkPolicy"]
    return dep, np


def test_the_consumer_is_one_writer_never_two():
    dep, _ = _consumer()
    assert dep["spec"]["replicas"] == 1
    assert dep["spec"]["strategy"]["type"] == "Recreate"  # a rolling update would overlap


def test_the_consumer_pod_is_restricted_and_capped():
    dep, _ = _consumer()
    pod = dep["spec"]["template"]["spec"]
    assert pod["automountServiceAccountToken"] is False
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    (c,) = pod["containers"]
    assert c["securityContext"] == {"allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": True,
                                    "capabilities": {"drop": ["ALL"]}}  # fmt: skip
    assert c["resources"]["limits"]["memory"]


def test_the_consumer_takes_no_secret_from_the_manifest_and_the_same_model_as_the_scorer():
    dep, _ = _consumer()
    (c,) = dep["spec"]["template"]["spec"]["containers"]
    env = {e["name"]: e for e in c["env"]}
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        assert "valueFrom" in env[name]
    scorer = _docs("rayservice.yaml")[0]
    text = yaml.safe_dump(scorer)
    for pin in ("GRAPHGUARD_MODEL_VERSION", "GRAPHGUARD_MODEL_SHA256"):
        assert env[pin]["value"] in text
    assert not any("password" in e["name"].lower() for e in c["env"])


def test_the_consumer_reaches_only_dns_redis_kafka_and_postgres():
    _, np = _consumer()
    ports = sorted(p["port"] for rule in np["spec"]["egress"] for p in rule.get("ports", [])
                   if p["protocol"] == "TCP" and p["port"] != 53)  # fmt: skip
    assert ports == [5432, 6379, 19094]
    cidrs = {t["ipBlock"]["cidr"] for r in np["spec"]["egress"] for t in r["to"] if "ipBlock" in t}
    assert cidrs == {"172.25.0.0/16"}


def test_the_consumer_s3_policy_has_the_same_ranges_as_the_scorers():
    def nets(name):
        (doc,) = [d for d in yaml.safe_load_all((K8S / name).read_text()) if d]
        return doc["spec"]["egress"][0]["to"], doc["spec"]["podSelector"]

    scorer, _ = nets("networkpolicy-s3.yaml")
    consumer, sel = nets("networkpolicy-s3-consumer.yaml")
    assert consumer == scorer and sel == {"matchLabels": {"app": "graphguard-consumer"}}


def test_the_stream_secret_holds_exactly_the_consumers_three_files(tmp_path):
    from graphguard.stream import k8s as sk

    for src in sk.FILES.values():
        (tmp_path / src).write_text(f"X={src}\n")
    doc = json.loads(sk.secret_manifest(tmp_path))
    assert set(doc["data"]) == {"kafka-consumer.env", "redis.env", "stream-db.env"}


# --- the shadow consumer (S6.10) -------------------------------------------------------
def test_the_shadow_pod_is_restricted_reaches_only_kafka_and_postgres_and_pins_its_model():
    docs = _docs("shadow.yaml")
    (dep,) = [d for d in docs if d["kind"] == "Deployment"]
    (np_,) = [d for d in docs if d["kind"] == "NetworkPolicy"]
    pod = dep["spec"]["template"]["spec"]
    assert dep["spec"]["replicas"] == 1 and dep["spec"]["strategy"]["type"] == "Recreate"
    assert pod["automountServiceAccountToken"] is False
    (c,) = pod["containers"]
    assert c["securityContext"]["readOnlyRootFilesystem"] is True
    env = {e["name"]: e for e in c["env"]}
    assert env["GRAPHGUARD_SHADOW_MODEL_VERSION"]["value"].startswith("xgb-")
    assert len(env["GRAPHGUARD_SHADOW_MODEL_SHA256"]["value"]) == 64
    assert "GRAPHGUARD_REDIS_BASE" not in env  # the shadow never touches the feature store
    ports = sorted(p["port"] for r in np_["spec"]["egress"] for p in r.get("ports", [])
                   if p["protocol"] == "TCP" and p["port"] != 53)  # fmt: skip
    assert ports == [5432, 19094]


def test_the_shadow_s3_policy_has_the_same_ranges_as_the_scorers():
    def doc(name):
        (d,) = [x for x in yaml.safe_load_all((K8S / name).read_text()) if x]
        return d

    assert (
        doc("networkpolicy-s3-shadow.yaml")["spec"]["egress"]
        == doc("networkpolicy-s3.yaml")["spec"]["egress"]
    )
