"""Backups (S5b.3): what is kept, how long, when, and when it raises the alarm."""

import configparser
import datetime as dt
import re

import pytest

from graphguard.config import REPO_ROOT
from graphguard.ops import backup as bk
from graphguard.ops.pg_access import SERVICES

pytestmark = pytest.mark.unit

UNITS = REPO_ROOT / "systemd"
NOW = dt.datetime(2026, 11, 19, 12, 0, tzinfo=dt.UTC)


def test_every_service_database_is_dumped():
    # The list comes from the access rules: a new service DB cannot be forgotten.
    assert bk.databases() == sorted(SERVICES)


def test_the_irreplaceable_paths_are_kept():
    assert {".secrets", "models/production", "private"} <= set(bk.PATHS)


def test_every_counted_database_is_also_dumped():
    assert set(bk.COUNTS) <= set(bk.databases())


def test_retention_is_time_based_never_count_based():
    # Count-based rules can be gamed: an attacker plants snapshots to push real ones out.
    args = bk.retention_args()
    assert "--keep-within" in args
    assert not any(
        a.startswith(("--keep-last", "--keep-daily", "--keep-weekly", "--keep-monthly"))
        for a in args
    )


def _status(backup_age_h=1, drill_age_h=24, backup_ok=True, drill_ok=True):
    return {
        "backup": {"ok": backup_ok, "at": (NOW - dt.timedelta(hours=backup_age_h)).isoformat()},
        "drill": {"ok": drill_ok, "at": (NOW - dt.timedelta(hours=drill_age_h)).isoformat()},
    }


def test_a_fresh_passing_status_raises_nothing():
    assert bk.assess(_status(), NOW) == []


@pytest.mark.parametrize(
    "status",
    [
        _status(backup_age_h=49),  # backup older than 2 days
        _status(drill_age_h=24 * 9),  # drill older than 8 days
        _status(backup_ok=False),
        _status(drill_ok=False),
        {},  # nothing ever recorded
    ],
)
def test_stale_failed_or_missing_raises_the_alarm(status):
    assert bk.assess(status, NOW)


def _unit(name):
    p = configparser.ConfigParser(strict=False, interpolation=None)
    p.read(UNITS / name)
    return p


LUBOT_WINDOWS = [("00:10", "00:50"), ("04:30", "04:31")]  # from the LuBot session


@pytest.mark.parametrize("timer", ["graphguard-backup.timer", "graphguard-restore-check.timer"])
def test_timers_stay_out_of_lubots_night_jobs(timer):
    cal = _unit(timer)["Timer"]["OnCalendar"]
    hhmm = re.search(r"(\d\d:\d\d):\d\d", cal).group(1)
    assert not any(a <= hhmm < b for a, b in LUBOT_WINDOWS), f"{timer} at {hhmm}"
    assert "UTC" in cal


@pytest.mark.parametrize("svc", ["graphguard-backup.service", "graphguard-restore-check.service"])
def test_services_are_capped_and_sandboxed(svc):
    s = _unit(svc)["Service"]
    assert s["MemoryMax"] == "512M" and s["ProtectSystem"] == "strict"
    assert s["NoNewPrivileges"] == "yes" and s["PrivateTmp"] == "yes"
    assert "--no-sync" in s["ExecStart"]  # never changes the environment at 3 am


def test_the_drill_postgres_is_powerless_and_offline():
    args = bk.drill_run_args("x")
    pairs = set(zip(args, args[1:], strict=False))  # neighbouring flag-value pairs
    assert {("--network", "none"), ("--cap-drop", "ALL"), ("--memory", "256m")} <= pairs
    assert ("--security-opt", "no-new-privileges") in pairs and ("--user", "70:70") in pairs
    assert args[-1] == bk.DRILL_IMAGE and "@sha256:" in bk.DRILL_IMAGE
