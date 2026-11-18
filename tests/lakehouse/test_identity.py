"""Job identities (S5.6d): secrets made safely, logins that never leak them, and
configs that agree with each other -- checked without Dex running."""

import base64
import http.server
import re
import stat
import threading
import urllib.parse
from pathlib import Path

import pytest
import yaml

from graphguard.config import REPO_ROOT
from graphguard.lakehouse import identity as idm

pytestmark = pytest.mark.unit

DEX_CONFIG = REPO_ROOT / "docker" / "dex" / "config.yaml"
COMPOSE = REPO_ROOT / "docker-compose.yml"


def test_generated_secrets_are_private_and_never_overwritten(tmp_path):
    made = idm.generate_secrets(tmp_path)
    assert {p.name for p in made} == {
        *(f"identity-{n}.env" for n in idm.IDENTITIES),
        "governance.env",
        "dex.env",
        "openfga.env",
        "lakekeeper-authz.env",
    }
    for p in made:
        assert stat.S_IMODE(p.stat().st_mode) == 0o600, p.name
    before = {p.name: p.read_text() for p in made}
    assert idm.generate_secrets(tmp_path) == []  # second run creates nothing
    assert {p.name: p.read_text() for p in made} == before


def test_dex_knows_exactly_the_secrets_each_job_holds(tmp_path):
    idm.generate_secrets(tmp_path)
    dex = (tmp_path / "dex.env").read_text()
    secrets = [idm.read_identity(n, tmp_path).secret for n in idm.IDENTITIES]
    for name, secret in zip(idm.IDENTITIES, secrets, strict=True):
        assert f"GG_{name.upper()}_SECRET={secret}\n" in dex
    assert len(set(secrets)) == len(secrets)  # no two jobs share a secret


def test_lakekeeper_gets_only_the_openfga_key(tmp_path):
    idm.generate_secrets(tmp_path)
    keys = [
        line.split("=")[0]
        for line in (tmp_path / "lakekeeper-authz.env").read_text().splitlines()
        if "=" in line
    ]
    assert keys == ["LAKEKEEPER__OPENFGA__API_KEY"]


def test_an_identity_never_shows_its_secret():
    ident = idm.Identity("trainer", "gg-trainer", "s3cr3t-value")
    assert "s3cr3t-value" not in repr(ident) and "s3cr3t-value" not in str(ident)


def test_unknown_identities_are_refused():
    with pytest.raises(ValueError):
        idm.client_id("root")


class _FakeDex(http.server.BaseHTTPRequestHandler):
    seen: dict = {}

    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers["Content-Length"])).decode()
        _FakeDex.seen = {"auth": self.headers["Authorization"], "form": urllib.parse.parse_qs(body)}
        user, _, pw = base64.b64decode(self.headers["Authorization"][6:]).decode().partition(":")
        if pw == "right":
            payload = b'{"access_token": "tok-123", "token_type": "bearer"}'
            self.send_response(200)
        else:
            payload = b'{"error": "invalid_client"}'
            self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_dex():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _FakeDex)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/dex/token"
    srv.shutdown()


def test_login_uses_client_credentials_with_basic_auth(fake_dex):
    tok = idm.fetch_token(idm.Identity("trainer", "gg-trainer", "right"), fake_dex)
    assert tok == "tok-123"
    assert _FakeDex.seen["form"]["grant_type"] == ["client_credentials"]
    assert _FakeDex.seen["auth"].startswith("Basic ")


def test_a_refused_login_does_not_put_the_secret_in_the_error(fake_dex):
    with pytest.raises(idm.TokenError) as e:
        idm.fetch_token(idm.Identity("trainer", "gg-trainer", "wrong-secret-xyz"), fake_dex)
    assert "wrong-secret-xyz" not in str(e.value) and "401" in str(e.value)


# --- the configs agree with each other ---------------------------------------


def _dex_config() -> dict:
    # Render the gomplate template the way Dex's entrypoint would, with dummy values.
    text = re.sub(r"\{\{-?\s*/\*.*?\*/\s*-?\}\}", "", DEX_CONFIG.read_text(), flags=re.S)
    text = re.sub(r'\{\{\s*getenv "(\w+)"[^}]*\}\}', r"dummy-\1", text)
    assert "{{" not in text, "unrendered template left in the Dex config"
    return yaml.safe_load(text)


def test_dex_has_one_client_per_identity_and_no_secret_in_the_file():
    cfg = _dex_config()
    clients = {c["id"]: c for c in cfg["staticClients"]}
    assert set(clients) == {idm.client_id(n) for n in idm.IDENTITIES}
    for name in idm.IDENTITIES:
        assert clients[idm.client_id(name)]["secret"] == f"dummy-GG_{name.upper()}_SECRET"
    assert cfg["storage"]["config"]["password"] == "dummy-DEX_DB_PASSWORD"


def test_dex_allows_machine_logins_only():
    cfg = _dex_config()
    assert cfg["oauth2"]["grantTypes"] == ["client_credentials"]
    # Dex needs a connector to start; the password DB is it, with no users in it.
    assert cfg["staticPasswords"] == []
    assert not cfg.get("connectors")  # in particular never `mockCallback`


def test_issuer_matches_what_lakekeeper_trusts():
    compose = yaml.safe_load(COMPOSE.read_text())
    lk = compose["services"]["lakekeeper"]["environment"]
    assert _dex_config()["issuer"] == idm.ISSUER == lk["LAKEKEEPER__OPENID_PROVIDER_URI"]
    assert set(lk["LAKEKEEPER__OPENID_AUDIENCE"].split(",")) == {
        idm.client_id(n) for n in idm.IDENTITIES
    }
    assert lk["LAKEKEEPER__AUTHZ_BACKEND"] == "openfga"


def test_openfga_is_unreachable_from_the_host_and_dex_only_from_localhost():
    services = yaml.safe_load(COMPOSE.read_text())["services"]
    assert "ports" not in services["openfga"]
    assert all(p.startswith("127.0.0.1:") for p in services["dex"]["ports"])
    assert all(p.startswith("127.0.0.1:") for p in services["lakekeeper"]["ports"])


@pytest.mark.parametrize("name", ["dex", "openfga", "openfga-migrate"])
def test_new_services_are_capped_hardened_and_digest_pinned(name):
    svc = yaml.safe_load(COMPOSE.read_text())["services"][name]
    assert "@sha256:" in svc["image"]
    assert svc["read_only"] is True and svc["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in svc["security_opt"]
    assert svc["mem_limit"] in ("64m", "128m") and svc["pids_limit"] <= 128
    assert not str(svc["user"]).startswith("0")


def test_no_secret_file_is_referenced_outside_dot_secrets():
    for svc in yaml.safe_load(COMPOSE.read_text())["services"].values():
        files = svc.get("env_file", [])
        for f in [files] if isinstance(files, str) else files:
            assert Path(f).parts[0] == ".secrets", f
