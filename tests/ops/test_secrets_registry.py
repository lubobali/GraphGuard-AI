"""The secrets registry and its check (S5b.6)."""

import datetime as dt

import pytest

from graphguard.ops import secrets_registry as sr

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 11, 19)


def _all_good():
    files = {n: (0o600, s.owner_uid) for n, s in sr.REGISTRY.items()}
    ledger = {n: "2026-11-01" for n in sr.REGISTRY}
    return files, ledger


def test_a_complete_fresh_correct_set_has_no_problems():
    assert sr.problems(*_all_good(), TODAY) == []


def test_an_untracked_secret_is_a_problem():
    files, ledger = _all_good()
    files["mystery.env"] = (0o600, 0)
    assert any("untracked" in p and "mystery.env" in p for p in sr.problems(files, ledger, TODAY))


def test_a_missing_secret_is_a_problem():
    files, ledger = _all_good()
    del files["redis.env"]
    assert "missing: redis.env" in sr.problems(files, ledger, TODAY)


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o660])
def test_a_loose_mode_is_a_problem(mode):
    files, ledger = _all_good()
    files["dex.env"] = (mode, 0)
    assert any("dex.env: mode" in p for p in sr.problems(files, ledger, TODAY))


def test_a_file_a_container_reads_must_be_owned_by_that_container():
    files, ledger = _all_good()
    files["mlflow-pgpass"] = (0o600, 0)
    assert any("mlflow-pgpass: owner" in p for p in sr.problems(files, ledger, TODAY))


def test_overdue_and_undated_secrets_are_problems():
    files, ledger = _all_good()
    ledger["redis.env"] = "2026-01-01"  # > 180 d
    del ledger["dex.env"]
    found = sr.problems(files, ledger, TODAY)
    assert any("redis.env: last rotated" in p for p in found)
    assert any("dex.env: no rotation date" in p for p in found)


def test_every_box_secret_names_its_rotation_command():
    for name, s in sr.REGISTRY.items():
        assert s.rotation and s.holder, name
        if s.max_age_days == sr.BOX_DAYS:
            assert "just rotate-" in s.rotation, name


def test_set_env_values_keeps_other_lines_mode_and_inode(tmp_path):
    f = tmp_path / "x.env"
    f.write_text("# comment\nA=1\nB=2\n")
    f.chmod(0o600)
    inode = f.stat().st_ino
    sr.set_env_values(f, {"B": "new", "C": "3"})
    assert f.read_text() == "# comment\nA=1\nB=new\nC=3\n"
    assert f.stat().st_ino == inode  # a bind-mounted file stays the same file
    assert f.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("pattern", "good", "bad"),
    [
        (sr.AWS_ID, "AKIA" + "A" * 16, "AKIA123"),
        (sr.AWS_SECRET, "a" * 40, "a" * 39),
        (sr.HETZNER, "a" * 64, "a b" * 10),
    ],
)
def test_typed_keys_are_validated_before_anything_is_written(pattern, good, bad):
    assert pattern.match(good) and not pattern.match(bad)
