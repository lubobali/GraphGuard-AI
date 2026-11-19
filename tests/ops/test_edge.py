"""The front door (S5b.4): the guard touches only what it owns; the watchdog sees drift."""

import configparser
import datetime as dt
import re

import pytest

from graphguard.config import REPO_ROOT
from graphguard.ops import edge

pytestmark = pytest.mark.unit

UNITS = REPO_ROOT / "systemd"
NOW = dt.datetime(2026, 11, 19, 12, 0, tzinfo=dt.UTC)


# --- the guard only ever touches its own chain, for the public interface only ----------
def _all_cmds():
    fresh = edge.apply_commands("iptables", None, has_jump=False)
    drifted = edge.apply_commands("ip6tables", ["-N " + edge.CHAIN, "-A x"], has_jump=True)
    return fresh + drifted


def test_rules_match_only_the_guarded_ports_and_drop():
    for spec, (proto, port) in zip(edge.rule_specs(), edge.GUARDED, strict=True):
        assert spec[spec.index("-p") + 1] == proto
        assert spec[spec.index("--dport") + 1] == str(port)
        assert spec[-2:] == ["-j", "DROP"]


def test_the_jump_matches_the_public_interface_only_and_goes_first():
    (jump,) = [c for c in _all_cmds() if "INPUT" in c]
    assert jump[1:4] == ["-I", "INPUT", "1"]
    assert jump[jump.index("-i") + 1] == "eth0" and jump[-1] == edge.CHAIN


def test_flush_and_append_only_ever_name_our_chain():
    for c in _all_cmds():
        if c[1] in {"-F", "-X", "-N", "-A"}:
            assert c[2] == edge.CHAIN, c
        assert c[1] in {"-N", "-F", "-A", "-I"}, c  # no -P, no -X here, no table switch


def test_nothing_dangerous_anywhere_in_the_module():
    src = (REPO_ROOT / "src/graphguard/ops/edge.py").read_text()
    code = "\n".join(line.split("#")[0] for line in src.splitlines())
    doc_end = code.index('"""', code.index('"""') + 3)  # skip the docstring
    body = code[doc_end:]
    for bad in ("iptables-restore", '"nft"', "killall", '"-P"', "--flush", '"-t"'):
        assert bad not in body, bad


def test_a_correct_family_needs_no_commands():
    assert edge.apply_commands("iptables", edge.expected_chain_lines(), has_jump=True) == []


def test_a_drifted_chain_is_rebuilt_and_the_jump_kept():
    cmds = edge.apply_commands("iptables", [f"-N {edge.CHAIN}"], has_jump=True)
    assert cmds[0] == ["iptables", "-F", edge.CHAIN]
    assert not any("INPUT" in c for c in cmds)


# --- listeners ------------------------------------------------------------------------
SS = """\
tcp LISTEN 0 4096 *:6443 *:* users:(("k3s-server",pid=1,fd=1))
tcp LISTEN 0 511 0.0.0.0:443 0.0.0.0:* users:(("nginx",pid=2,fd=2))
tcp LISTEN 0 511 127.0.0.1:5010 0.0.0.0:* users:(("docker-proxy",pid=3,fd=3))
tcp LISTEN 0 128 100.115.173.71:8110 0.0.0.0:* users:(("docker-proxy",pid=4,fd=4))
tcp LISTEN 0 128 [::]:22 [::]:* users:(("sshd",pid=5,fd=5))
tcp LISTEN 0 128 *:41277 *:* users:(("forgejo-runner",pid=6,fd=6))
udp UNCONN 0 0 0.0.0.0:8472 0.0.0.0:*
tcp LISTEN 0 128 178.156.214.8:9999 0.0.0.0:* users:(("thing",pid=7,fd=7))
"""
PUBLIC = {"178.156.214.8"}


def test_only_public_addresses_count():
    got = edge.parse_ss(SS, PUBLIC)
    ports = {lst.port for lst in got}
    assert {6443, 443, 22, 41277, 8472, 9999} == ports  # not localhost, not the tailnet


def test_random_high_ports_are_matched_by_process_only():
    base = edge.baseline_from(edge.parse_ss(SS, PUBLIC))
    assert {"proto": "tcp", "port": "*", "process": "forgejo-runner"} in base
    later = {edge.Listener("tcp", 45001, "forgejo-runner")}
    assert edge.new_listeners(later, base) == []


def test_a_new_public_listener_is_reported_and_guarded_ports_are_not():
    base = edge.baseline_from(edge.parse_ss(SS, PUBLIC))
    now = {edge.Listener("tcp", 5432, "postgres"), edge.Listener("tcp", 10250, "k3s-server")}
    assert edge.new_listeners(now, base) == [edge.Listener("tcp", 5432, "postgres")]


# --- the cloud firewall -------------------------------------------------------------------
WEB = [
    {"protocol": "tcp", "port": "80", "source_ips": ["0.0.0.0/0", "::/0"]},
    {"protocol": "tcp", "port": "443", "source_ips": ["::/0", "0.0.0.0/0"]},
]
SERVER = {"public_net": {"firewalls": [{"id": 1, "status": "applied"}]}}


def _fw(rules):
    return [{"rules": [{"direction": "in", **r} for r in rules]}]


def test_the_expected_cloud_rules_pass():
    assert edge.firewall_problems(SERVER, _fw(WEB), WEB) == []


@pytest.mark.parametrize(
    ("server", "rules"),
    [
        ({"public_net": {"firewalls": []}}, WEB),  # firewall detached
        ({"public_net": {"firewalls": [{"id": 1, "status": "pending"}]}}, WEB),
        (SERVER, [*WEB, {"protocol": "tcp", "port": "6443", "source_ips": ["0.0.0.0/0"]}]),
        (SERVER, [WEB[0]]),  # a rule went missing
        (SERVER, [WEB[0], {**WEB[1], "source_ips": ["0.0.0.0/0"]}]),  # IPv6 dropped
    ],
    ids=["detached", "not-applied", "extra-port", "missing", "source-changed"],
)
def test_any_cloud_drift_is_a_problem(server, rules):
    assert edge.firewall_problems(server, _fw(rules), WEB)


def test_the_server_is_found_by_this_boxs_ip_and_only_once():
    a = {"name": "a", "public_net": {"ipv4": {"ip": "1.2.3.4"}}}
    b = {"name": "b", "public_net": {"ipv4": {"ip": "5.6.7.8"}}}
    assert edge.find_server([a, b], "5.6.7.8") is b
    with pytest.raises(LookupError):
        edge.find_server([a], "5.6.7.8")


def test_outbound_rules_are_not_inbound_rules():
    out = [{"direction": "out", "protocol": "tcp", "port": "1", "source_ips": []}]
    assert edge.normalise_rules(out) == []


# --- status -------------------------------------------------------------------------------
def test_status_fresh_ok_raises_nothing_and_stale_or_failed_does():
    ok = {"at": (NOW - dt.timedelta(hours=3)).isoformat(), "ok": True, "problems": []}
    assert edge.assess(ok, NOW) == []
    assert edge.assess({**ok, "at": (NOW - dt.timedelta(days=3)).isoformat()}, NOW)
    assert edge.assess({**ok, "ok": False, "problems": ["x"]}, NOW) == ["x"]
    assert edge.assess({}, NOW)


# --- units ------------------------------------------------------------------------------------
def _unit(name):
    p = configparser.ConfigParser(strict=False, interpolation=None)
    p.read(UNITS / name)
    return p


def test_the_guard_unit_runs_after_k3s_and_docker_at_boot():
    u = _unit("graphguard-edge.service")
    after = u["Unit"]["After"]
    assert "k3s.service" in after and "docker.service" in after
    assert u["Service"]["RemainAfterExit"] == "yes"
    assert "edge apply" in u["Service"]["ExecStart"]
    assert "edge remove" in u["Service"]["ExecStop"]


def test_the_check_timer_stays_out_of_lubots_night_jobs():
    cal = _unit("graphguard-edge-check.timer")["Timer"]["OnCalendar"]
    hhmm = re.search(r"(\d\d:\d\d):\d\d", cal).group(1)
    assert not ("00:10" <= hhmm < "00:50" or "04:30" <= hhmm < "04:31") and "UTC" in cal


def test_the_check_service_is_capped_and_sandboxed():
    s = _unit("graphguard-edge-check.service")["Service"]
    assert s["MemoryMax"] == "256M" and s["ProtectSystem"] == "strict"
    assert s["NoNewPrivileges"] == "yes" and "--no-sync" in s["ExecStart"]
