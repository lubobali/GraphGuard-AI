"""Postgres access rules (S5b.1), checked without a server."""

import pytest

from graphguard.ops import pg_access as pga

pytestmark = pytest.mark.unit


def _rules():
    return [ln.split() for ln in pga.hba_lines() if ln and not ln.startswith("#")]


def test_nothing_is_trusted():
    assert all(r[-1] in ("scram-sha-256", "reject") for r in _rules())
    assert not any(
        "trust" in ln or " md5" in ln or "password" in ln.split() for ln in pga.hba_lines()
    )


def test_everything_not_listed_is_rejected_last():
    assert _rules()[-2:] == [
        ["host", "all", "all", "0.0.0.0/0", "reject"],
        ["host", "all", "all", "::/0", "reject"],
    ]


def test_each_service_reaches_only_its_own_database():
    host = [r for r in _rules() if r[0] == "host" and r[-1] != "reject"]
    for _, db, role, _src, _ in host:
        assert pga.SERVICES[db][0] == role
    assert all(r[1] != "all" for r in host)  # no role may reach every database


def test_the_superuser_has_no_network_access():
    host_roles = {r[2] for r in _rules() if r[0] == "host" and r[-1] != "reject"}
    assert "graphguard" not in host_roles and "postgres" not in host_roles


def test_only_the_rollback_catalog_and_the_stream_come_from_the_host():
    from_gateway = [r for r in _rules() if r[0] == "host" and r[3] == pga.GATEWAY]
    assert [r[1] for r in from_gateway] == ["lakehouse", "stream"]


def test_only_the_stream_is_reachable_from_pods_and_only_its_own_database():
    from_pods = [r for r in _rules() if r[0] == "host" and r[3] == pga.PODS]
    assert [(r[1], r[2]) for r in from_pods] == [("stream", "stream_app")]


def test_the_committed_file_matches_the_code():
    assert pga.HBA_FILE.read_text().splitlines() == pga.hba_lines()
