"""Redis users (S5b.1): least privilege, checked without a server."""

import hashlib
import stat

import pytest

from graphguard.serving import redis_acl as acl
from graphguard.serving import store

pytestmark = pytest.mark.unit

PW = {u: f"pw-{u}-0123456789" for u in acl.USERS}


def _user(name: str) -> str:
    (line,) = [ln for ln in acl.acl_lines(PW) if ln.startswith(f"user {name} ")]
    return line


def _allowed(line: str) -> set[str]:
    return {t[1:] for t in line.split() if t.startswith("+")}


def test_an_unauthenticated_client_can_do_nothing():
    line = _user("default")
    assert " off " in f" {line} " and "-@all" in line and not _allowed(line)


def test_the_scorer_can_only_read_accounts():
    line = _user("scorer")
    assert _allowed(line) == {"ping", "hgetall", "client|setinfo"}
    assert "~gg:acct:*" in line.split()


def test_the_loader_gets_exactly_what_store_load_uses():
    # S6.3: it also seeds the stream's edge sets and 24 h windows
    assert _allowed(_user("loader")) == {
        "ping",
        "hgetall",
        "hset",
        "scan",
        "del",
        "client|setinfo",
        "sadd",
        "zadd",
    }
    for pattern in ("~gg:acct:*", "~gg:edge:*", "~gg:win:*", "~gg:ev:*"):
        assert pattern in _user("loader").split()


def test_the_stream_writer_gets_only_plain_commands_on_its_keys():
    line = _user("stream")
    assert _allowed(line) == {
        "ping",
        "client|setinfo",
        "hgetall",
        "hset",
        "smismember",
        "sadd",
        "zcount",
        "zadd",
        "zremrangebyscore",
        "get",
        "set",
        "del",
        "multi",
        "exec",
        "discard",
    }
    patterns = {t for t in line.split() if t.startswith("~")}
    assert patterns == {"~gg:acct:*", "~gg:edge:*", "~gg:win:*", "~gg:ev:*"}


def test_the_scorer_still_reads_accounts_only():
    patterns = {t for t in _user("scorer").split() if t.startswith("~")}
    assert patterns == {"~gg:acct:*"}


def test_tests_are_confined_to_test_keys():
    line = _user("tests")
    assert "~test-*" in line.split() and "~gg:acct:*" not in line
    assert "select" in _allowed(line)


@pytest.mark.parametrize("user", list(acl.USERS))
def test_no_user_can_script_or_administer(user):
    line = _user(user)
    assert "-@all" in line  # starts from nothing, so only explicit + commands exist
    assert not _allowed(line) & set(acl.NEVER)
    assert "@" not in " ".join(t for t in line.split() if t.startswith("+"))  # no +@category


def test_the_acl_file_holds_hashes_never_passwords():
    text = "\n".join(acl.acl_lines(PW))
    for user, pw in PW.items():
        assert pw not in text
        assert f"#{hashlib.sha256(pw.encode()).hexdigest()}" in _user(user)


def test_generate_makes_private_files_and_never_rotates_by_accident(tmp_path):
    acl.generate(tmp_path, chown=False)
    env, aclf = tmp_path / "redis.env", tmp_path / "redis-users.acl"
    for f in (env, aclf):
        assert stat.S_IMODE(f.stat().st_mode) == 0o600
    first = env.read_text()
    acl.generate(tmp_path, chown=False)
    assert env.read_text() == first  # passwords kept; the ACL file is just rewritten


def test_a_url_with_a_user_carries_its_password(tmp_path, monkeypatch):
    acl.generate(tmp_path, chown=False)
    monkeypatch.setattr(acl, "SECRETS_DIR", tmp_path)
    monkeypatch.setattr(acl.password, "__defaults__", (tmp_path,))
    url = store.redis_url(0, "scorer")
    assert url.startswith("redis://scorer:") and url.endswith("@127.0.0.1:6380/0")
    assert acl.password("scorer", tmp_path) in url


def test_a_missing_password_fails_loudly_instead_of_connecting_without(tmp_path, monkeypatch):
    monkeypatch.setattr(acl.password, "__defaults__", (tmp_path,))
    with pytest.raises(FileNotFoundError):
        store.redis_url(0, "loader")


def test_unknown_users_are_refused():
    with pytest.raises(ValueError):
        acl.password_var("admin")
