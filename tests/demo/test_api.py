"""The demo API (S7.6) on a fake query layer: shapes, headers, limits, the one write."""

import datetime as dt
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from graphguard.demo import api as A
from graphguard.demo.queries import k_for

pytestmark = pytest.mark.unit

T = dt.datetime(2022, 9, 7, 12)


class FakeRepo:
    def __init__(self):
        self.verdicts = []

    def meta(self):
        return {"banner": "Synthetic data", "window_days": 2.107, "build": {"rows": {}}}

    def capacity(self, k):
        return {"system": {"k": k, "caught": 167}, "rules": {"k": k, "caught": 1}}

    def capacity_curve(self):
        return {"system": [[1, 0, 0], [25, 10, 2]]}

    def queue(self, k, page):
        return {"k": k, "page": page, "alerts": k, "accounts": 3, "groups": [{"rank": 1}]}

    def alert(self, event_id):
        if event_id != 7:
            return None
        return {"event_id": 7, "event_time": T, "reasons": ["a", "b", "c"], "ring": {}}

    def answer(self, event_id):
        return {"is_laundering": True, "ring_hops": [7, 8]} if event_id == 7 else None

    def performance(self, k):
        return {"measured_offline": {"k": k}, "confirmed_so_far": {"known": 5}}

    def live(self, after, limit):
        return [] if after[1] >= 0 else [{"event_id": 1, "event_time": T}]

    def add_verdict(self, event_id, verdict, note):
        self.verdicts.append((event_id, verdict, note))


@pytest.fixture
def client():
    repo = FakeRepo()
    c = TestClient(A.create_app(repo=repo))
    c.repo = repo
    return c


def test_k_from_a_daily_workload_is_clamped():
    assert k_for(100) == 211 and k_for(0.01) == 1 and k_for(100_000) == 5_000


@pytest.mark.parametrize("path", ["/api/health", "/api/meta", "/api/capacity?per_day=100",
                                  "/api/capacity/curve", "/api/queue", "/api/alerts/7",
                                  "/api/alerts/7/answer", "/api/performance"])  # fmt: skip
def test_every_read_answers_with_the_security_headers(client, path):
    r = client.get(path)
    assert r.status_code == 200
    for header in A.SECURITY_HEADERS:
        assert header in r.headers
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert "server" not in {h.lower() for h in r.headers if h.lower() == "x-powered-by"}


def test_capacity_and_queue_speak_in_the_daily_workload(client):
    assert client.get("/api/capacity?per_day=100").json()["k"] == 211
    assert client.get("/api/queue?per_day=100&page=2").json()["page"] == 2


def test_unknown_alerts_and_bad_inputs_are_refused(client):
    assert client.get("/api/alerts/999").status_code == 404
    assert client.get("/api/alerts/999/answer").status_code == 404
    assert client.get("/api/alerts/notanumber").status_code == 422
    assert client.get("/api/capacity?per_day=-5").status_code == 422
    assert client.get("/api/queue?page=0").status_code == 422


def test_a_verdict_is_json_only_validated_and_saved(client):
    url = "/api/alerts/7/verdict"
    assert client.post(url, data={"verdict": "close"}).status_code == 415  # a form cannot post
    assert client.post(url, json={"verdict": "delete everything"}).status_code == 422
    assert client.post(url, json={"verdict": "close", "note": "x" * 2001}).status_code == 422
    assert client.post("/api/alerts/999/verdict", json={"verdict": "close"}).status_code == 404
    r = client.post(url, json={"verdict": "escalate", "note": "ring with 4 hops"})
    assert r.status_code == 201 and client.repo.verdicts == [(7, "escalate", "ring with 4 hops")]


def test_reads_and_writes_are_rate_limited_per_client():
    clock = {"t": 0.0}
    c = TestClient(A.create_app(repo=FakeRepo(), limiter=A.RateLimiter(lambda: clock["t"])))
    codes = [c.get("/api/health").status_code for _ in range(int(A.READ_BURST) + 5)]
    assert codes.count(429) == 5
    clock["t"] += 10  # tokens refill with time
    assert c.get("/api/health").status_code == 200
    writes = [c.post("/api/alerts/7/verdict", json={"verdict": "close"}).status_code
              for _ in range(int(A.WRITE_BURST) + 2)]  # fmt: skip
    assert writes.count(429) == 2


def test_the_live_stream_sends_transactions_and_a_full_server_says_busy(client):
    r = client.get("/api/live")
    assert r.status_code == 200 and "event: transaction" in r.text
    client.app.state.live_open["n"] = A.MAX_LIVE  # as if four streams were open
    busy = client.get("/api/live")
    assert "event: busy" in busy.text and "event: transaction" not in busy.text
    assert client.app.state.live_open["n"] == A.MAX_LIVE  # a refused stream takes no slot


def test_the_api_imports_nothing_heavy():
    heavy = "('polars', 'numpy', 'xgboost', 'pyarrow')"
    code = f"import sys, graphguard.demo.api; print(sorted(m for m in {heavy} if m in sys.modules))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "[]"


def test_the_static_site_is_served_and_survives_its_folder_being_recreated(tmp_path):
    out = tmp_path / "out"
    c = TestClient(A.create_app(repo=FakeRepo(), web_dir=str(out)))  # not there yet
    out.mkdir()
    (out / "index.html").write_text("<h1>queue</h1>")
    r = c.get("/")
    assert r.status_code == 200 and "queue" in r.text
    assert "Content-Security-Policy" in r.headers
    assert c.get("/api/health").json() == {"status": "ok"}  # the API still wins on /api
