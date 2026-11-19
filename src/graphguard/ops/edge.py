"""The box's front door (S5b.4): k3s off the internet, and a daily read-only watchdog.

**The guard.** k3s listens on all interfaces for its API, the kubelet and flannel. On a
single node nobody outside should ever reach them, so a few DROP rules in GraphGuard's
OWN chain catch them — for traffic arriving on the public interface only. One jump from
INPUT, first in line, matches `-i eth0`: pods (cni0), Tailscale, localhost and Docker's
bridges never enter the chain, and Docker's published ports never pass INPUT at all.
Nothing is restarted. This module never runs `iptables-restore`, never flushes a chain
it does not own, never touches nft directly.

**The watchdog** (read-only): the cloud firewall attached to this server still allows
exactly what the private baseline says (via a read-only API token); the box's public
listeners still match the private baseline; our chain and jump are still in place.
The baseline and the status file live in `private/` — which ports are open is never
written anywhere public.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass

from graphguard.config import REPO_ROOT

CHAIN = "GRAPHGUARD-EDGE"
IFACE = "eth0"
COMMENT = "graphguard-edge"
FAMILIES = ("iptables", "ip6tables")
# k3s on one node: API server, kubelet, flannel VXLAN. All of them stay reachable from
# the box itself, the pods and the tailnet; only the internet side is dropped.
GUARDED = (("tcp", 6443), ("tcp", 10250), ("udp", 8472))

PRIVATE = REPO_ROOT / "private" / "edge"
BASELINE_FILE = PRIVATE / "baseline.json"
STATUS_FILE = PRIVATE / "status.json"
TOKEN_FILE = REPO_ROOT / ".secrets" / "hetzner-readonly.env"
HETZNER_API = "https://api.hetzner.cloud/v1"
EPHEMERAL = 32768  # ports at or above: randomly chosen at start, matched by process only


# --- the guard -----------------------------------------------------------------------
def rule_specs() -> list[list[str]]:
    """The body of each rule in our chain (after `-A CHAIN`)."""
    return [
        ["-p", proto, "-m", proto, "--dport", str(port), "-m", "comment",
         "--comment", COMMENT, "-j", "DROP"]
        for proto, port in GUARDED
    ]  # fmt: skip


def jump_spec() -> list[str]:
    return ["-i", IFACE, "-j", CHAIN]


def expected_chain_lines() -> list[str]:
    """What `iptables -S CHAIN` prints once the chain is right."""
    return [f"-N {CHAIN}"] + [f"-A {CHAIN} " + " ".join(s) for s in rule_specs()]


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _ok(cmd: list[str]) -> bool:
    return _run(cmd, check=False).returncode == 0


def apply_commands(binary: str, current_chain: list[str] | None, has_jump: bool) -> list[list[str]]:
    """The exact commands that bring one family to the wanted state (pure, tested).

    `current_chain` is `-S CHAIN` output (None if the chain is missing). The chain is
    rebuilt only when it differs; the jump is inserted first in INPUT only when absent.
    """
    cmds: list[list[str]] = []
    if current_chain is None:
        cmds.append([binary, "-N", CHAIN])
    if current_chain != expected_chain_lines():
        if current_chain is not None:
            cmds.append([binary, "-F", CHAIN])  # our own chain only
        cmds += [[binary, "-A", CHAIN, *s] for s in rule_specs()]
    if not has_jump:
        cmds.append([binary, "-I", "INPUT", "1", *jump_spec()])
    return cmds


def _chain_lines(binary: str) -> list[str] | None:
    r = _run([binary, "-S", CHAIN], check=False)
    return r.stdout.strip().splitlines() if r.returncode == 0 else None


def _jump_count(binary: str) -> int:
    want = "-A INPUT " + " ".join(jump_spec())
    return _run([binary, "-S", "INPUT"]).stdout.splitlines().count(want)


def apply() -> None:
    for b in FAMILIES:
        for cmd in apply_commands(b, _chain_lines(b), _jump_count(b) > 0):
            _run(cmd)
        while _jump_count(b) > 1:  # never leave duplicates behind
            _run([b, "-D", "INPUT", *jump_spec()])
    print("edge guard applied:", ", ".join(f"{p}/{n}" for p, n in GUARDED), f"on {IFACE}")


def remove() -> None:
    for b in FAMILIES:
        while _jump_count(b) > 0:
            _run([b, "-D", "INPUT", *jump_spec()])
        if _chain_lines(b) is not None:
            _run([b, "-F", CHAIN])
            _run([b, "-X", CHAIN])
    print("edge guard removed")


def guard_problems() -> list[str]:
    problems = []
    for b in FAMILIES:
        if _chain_lines(b) != expected_chain_lines():
            problems.append(f"{b}: chain {CHAIN} missing or changed")
        if (n := _jump_count(b)) != 1:
            problems.append(f"{b}: INPUT jump to {CHAIN} present {n} times, want 1")
    return problems


def counters() -> dict[str, dict[str, int]]:
    """Packets dropped so far per family and rule (proof the guard bites)."""
    out: dict[str, dict[str, int]] = {}
    for b in FAMILIES:
        r = _run([b, "-L", CHAIN, "-v", "-n", "-x"], check=False)
        proto_of = {str(n): p for p, n in GUARDED}
        rows = {}
        for line in r.stdout.splitlines()[2:]:
            if (m := re.search(r"dpt:(\d+)", line)) and m.group(1) in proto_of:
                rows[f"{proto_of[m.group(1)]}/{m.group(1)}"] = int(line.split()[0])
        out[b] = rows
    return out


# --- the watchdog: public listeners ------------------------------------------------------
@dataclass(frozen=True, order=True)
class Listener:
    proto: str
    port: int
    process: str


_PUBLIC_HOSTS = {"0.0.0.0", "*", "[::]", "::"}


def parse_ss(text: str, public_ips: set[str]) -> set[Listener]:
    """Sockets listening on a public address, from `ss -lntupH` output (pure, tested)."""
    found = set()
    for line in text.splitlines():
        f = line.split()
        if len(f) < 5:
            continue
        proto, local = f[0], f[4]
        host, _, port = local.rpartition(":")
        host = host.split("%")[0].strip("[]") if host not in _PUBLIC_HOSTS else host
        if host not in _PUBLIC_HOSTS and host not in public_ips:
            continue
        m = re.search(r'\(\("([^"]+)"', line)
        found.add(Listener(proto, int(port), m.group(1) if m else "?"))
    return found


def matches(listener: Listener, entry: dict) -> bool:
    return (
        entry["proto"] == listener.proto
        and entry["process"] == listener.process
        and (entry["port"] == "*" or entry["port"] == listener.port)
    )


def baseline_from(listeners: set[Listener]) -> list[dict]:
    """A baseline entry per listener; random high ports are matched by process only."""
    entries = {
        (lst.proto, "*" if lst.port >= EPHEMERAL else lst.port, lst.process) for lst in listeners
    }
    return [
        {"proto": p, "port": port, "process": proc}
        for p, port, proc in sorted(entries, key=lambda e: (e[0], str(e[1]), e[2]))
    ]


def new_listeners(listeners: set[Listener], baseline: list[dict]) -> list[Listener]:
    guarded = {(p, n) for p, n in GUARDED}
    return sorted(
        lst
        for lst in listeners
        if (lst.proto, lst.port) not in guarded  # dropped by our chain anyway
        and not any(matches(lst, e) for e in baseline)
    )


def _public_ips() -> set[str]:
    out = _run(["ip", "-j", "addr", "show", "dev", IFACE]).stdout
    return {a["local"] for i in json.loads(out) for a in i.get("addr_info", [])
            if a.get("scope") == "global"}  # fmt: skip


def current_listeners() -> set[Listener]:
    return parse_ss(_run(["ss", "-lntupH"]).stdout, _public_ips())


# --- the watchdog: the cloud firewall ------------------------------------------------------
def normalise_rules(rules: list[dict]) -> list[dict]:
    """Inbound rules in a comparable form (pure, tested)."""
    return sorted(
        (
            {
                "protocol": r["protocol"],
                "port": r.get("port"),
                "source_ips": sorted(r.get("source_ips") or []),
            }
            for r in rules
            if r.get("direction") == "in"
        ),
        key=lambda r: (r["protocol"], str(r["port"]), r["source_ips"]),
    )


def firewall_problems(server: dict, firewalls: list[dict], expected: list[dict]) -> list[str]:
    """Compare what the cloud says with the private baseline (pure, tested)."""
    attached = server.get("public_net", {}).get("firewalls", [])
    if not attached:
        return ["cloud firewall: none attached to this server"]
    problems = [
        f"cloud firewall {a['id']}: status {a.get('status')}, want applied"
        for a in attached
        if a.get("status") != "applied"
    ]
    rules = normalise_rules([r for fw in firewalls for r in fw.get("rules", [])])
    want = normalise_rules([{"direction": "in", **r} for r in expected])
    problems += [f"cloud firewall: unexpected inbound rule {r}" for r in rules if r not in want]
    problems += [f"cloud firewall: expected rule missing {r}" for r in want if r not in rules]
    return problems


def _hetzner(path: str, token: str) -> dict:
    req = urllib.request.Request(
        f"{HETZNER_API}{path}", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 (fixed https host)
        return json.load(r)


def _token() -> str:
    for line in TOKEN_FILE.read_text().splitlines():
        if line.startswith("HETZNER_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise KeyError("HETZNER_TOKEN missing in .secrets/hetzner-readonly.env")


def find_server(servers: list[dict], ipv4: str) -> dict:
    """The one cloud server whose public IPv4 is this box's (pure, tested)."""
    hits = [x for x in servers if x.get("public_net", {}).get("ipv4", {}).get("ip") == ipv4]
    if len(hits) != 1:
        raise LookupError(f"cloud: {len(hits)} servers with this box's IPv4")
    return hits[0]


def cloud_state(ipv4: str) -> tuple[dict, list[dict]]:
    token = _token()
    server = find_server(_hetzner("/servers?per_page=50", token)["servers"], ipv4)
    fws = [_hetzner(f"/firewalls/{a['id']}", token)["firewall"]
           for a in server.get("public_net", {}).get("firewalls", [])]  # fmt: skip
    return server, fws


def box_ipv4() -> str:
    (ip,) = [a for a in _public_ips() if ":" not in a]
    return ip


# --- the check ------------------------------------------------------------------------------
def _load_baseline() -> dict:
    return json.loads(BASELINE_FILE.read_text())


def check() -> list[str]:
    base = _load_baseline()
    problems = guard_problems()
    problems += [f"new public listener: {lst.proto} {lst.port} ({lst.process})"
                 for lst in new_listeners(current_listeners(), base["listeners"])]  # fmt: skip
    try:
        server, fws = cloud_state(box_ipv4())
        problems += firewall_problems(server, fws, base["cloud_inbound"])
    except Exception as e:  # an unreadable cloud is a failed check, never a pass
        problems.append(f"cloud firewall: could not check ({type(e).__name__}: {e})")
    return problems


def write_status(problems: list[str], now: dt.datetime | None = None) -> None:
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    now = now or dt.datetime.now(dt.UTC)
    STATUS_FILE.write_text(json.dumps(
        {"at": now.isoformat(), "ok": not problems, "problems": problems,
         "dropped": counters()}, indent=2))  # fmt: skip
    STATUS_FILE.chmod(0o600)


def assess(status: dict, now: dt.datetime) -> list[str]:
    """Problems with the last recorded check: missing, failed, or older than 2 days."""
    if not status:
        return ["no edge check recorded yet"]
    out = list(status.get("problems", [])) if not status.get("ok") else []
    if now - dt.datetime.fromisoformat(status["at"]) > dt.timedelta(days=2):
        out.append(f"last edge check is old: {status['at']}")
    return out


def record_baseline() -> None:
    """Record today's public listeners and cloud rules as the accepted state (private)."""
    server, fws = cloud_state(box_ipv4())
    inbound = normalise_rules([r for fw in fws for r in fw.get("rules", [])])
    PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(
        {"server": server.get("name"), "recorded": dt.datetime.now(dt.UTC).isoformat(),
         "cloud_inbound": inbound, "listeners": baseline_from(current_listeners())},
        indent=2))  # fmt: skip
    BASELINE_FILE.chmod(0o600)
    print(f"baseline: {len(inbound)} cloud rules, listeners recorded (private)")


def _dry_run() -> int:
    for b in FAMILIES:
        for c in apply_commands(b, _chain_lines(b), _jump_count(b) > 0):
            print(" ".join(c))
    return 0


def _check() -> int:
    problems = check()
    write_status(problems)
    for p in problems:
        print("PROBLEM:", p)
    print("edge check ok" if not problems else f"edge check FAILED ({len(problems)})")
    return 1 if problems else 0


def _status() -> int:
    status = json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else {}
    problems = assess(status, dt.datetime.now(dt.UTC)) + guard_problems()
    print(f"edge check  {'ok' if status.get('ok') else 'FAIL'}  {status.get('at', '-')}")
    for b, rows in counters().items():
        print(f"  {b}: dropped " + ", ".join(f"{k} {v}" for k, v in rows.items()))
    for p in problems:
        print("  PROBLEM:", p)
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "status"
    actions = {
        "apply": lambda: apply() or 0,
        "remove": lambda: remove() or 0,
        "dry-run": _dry_run,
        "baseline": lambda: record_baseline() or 0,
        "check": _check,
        "status": _status,
    }
    if cmd not in actions:
        print(f"usage: {argv[0]} apply|remove|dry-run|baseline|check|status")
        return 2
    return actions[cmd]()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
