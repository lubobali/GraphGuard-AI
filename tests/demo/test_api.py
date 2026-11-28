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
        self.actions = []

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

    # S7.15: the case workflow (rows as the database keeps them)
    def case_rows(self, event_id):
        return [r for r in self.actions if r["event_id"] == event_id]

    def visitor_actions_last_day(self):  # S8b.2: the daily cap's count
        return len(self.actions)

    def add_action(self, event_id, owner, actor, role, action, code, reason):
        self.actions.append({"event_id": event_id, "case_owner": owner, "actor": actor,
                             "role": role, "action": action, "code": code, "reason": reason,
                             "at": T})  # fmt: skip

    def decisions(self, viewer):
        return [{"event_id": 7, "owner": viewer, "state": "awaiting_review",
                 "decision": "escalate", "is_laundering": True}]  # fmt: skip

    def manager(self, viewer, scope, k):
        return {"scope": scope, "decided": 1, "qa": [], "backlog": {"total": k}}

    def next_undecided(self, viewer, after, k):
        return {"event_id": 8, "rank": after + 1}


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


ME = "11111111-1111-4111-8111-111111111111"
ESC = {"visitor": ME, "role": "investigator", "action": "escalate", "reason": "ring with 4 hops"}


def test_an_action_is_json_only_validated_and_saved(client):
    url = "/api/alerts/7/actions"
    assert client.post(url, data=ESC).status_code == 415  # a form cannot post
    assert client.post(url, json={**ESC, "action": "delete everything"}).status_code == 422
    assert client.post(url, json={**ESC, "reason": "x" * 501}).status_code == 422
    assert client.post(url, json={**ESC, "visitor": "not-a-uuid"}).status_code == 422
    assert client.post("/api/alerts/999/actions", json=ESC).status_code == 404
    client.app.state.limiter = A.RateLimiter()  # 5 writes so far = the burst; limits: own test
    r = client.post(url, json=ESC)
    assert r.status_code == 201 and r.json()["case"]["state"] == "awaiting_review"
    assert [a["action"] for a in client.repo.actions] == ["escalate"]


def test_the_workflow_refuses_what_it_does_not_allow(client):
    url = "/api/alerts/7/actions"
    r = client.post(url, json={**ESC, "role": "reviewer", "action": "approve", "reason": ""})
    assert r.status_code == 409 and "not allowed" in r.json()["detail"]
    r = client.post(url, json={**ESC, "action": "close", "reason": "fine"})  # no code
    assert r.status_code == 409 and "code" in r.json()["detail"]
    r = client.post(url, json={**ESC, "owner": "demo"})  # Sam's case is not mine to decide
    assert r.status_code == 409
    assert client.repo.actions == []


def test_a_repeated_click_stores_one_row(client):
    url = "/api/alerts/7/actions"
    codes = [client.post(url, json=ESC).status_code for _ in range(3)]
    assert codes == [201, 200, 200] and len(client.repo.actions) == 1
    assert client.post(url, json=ESC).json()["repeat"] is True


def test_a_reviewer_approves_and_an_escalation_gets_a_sar_due_date(client):
    url = "/api/alerts/7/actions"
    client.post(url, json=ESC)
    r = client.post(url, json={**ESC, "role": "reviewer", "action": "approve", "reason": ""})
    case = r.json()["case"]
    assert r.status_code == 201 and case["state"] == "escalated" and case["sar_due"]


def test_the_case_endpoint_shows_my_case_and_sams_and_never_another_visitor(client):
    other = "22222222-2222-4222-8222-222222222222"
    client.post("/api/alerts/7/actions", json={**ESC, "visitor": other})
    mine = client.get(f"/api/alerts/7/case?visitor={ME}").json()
    assert mine["mine"]["state"] == "new" and mine["mine"]["history"] == []
    assert other not in str(mine)
    assert client.get("/api/alerts/7/case?visitor=bad").status_code == 422


def test_decisions_and_next_need_a_visitor_id(client):
    assert client.get(f"/api/decisions?visitor={ME}").json()["cases"][0]["event_id"] == 7
    assert client.get("/api/decisions").status_code == 422
    assert client.get(f"/api/next?visitor={ME}&after=3").json()["event_id"] == 8


def test_reads_and_writes_are_rate_limited_per_client():
    clock = {"t": 0.0}
    c = TestClient(A.create_app(repo=FakeRepo(), limiter=A.RateLimiter(lambda: clock["t"])))
    codes = [c.get("/api/health").status_code for _ in range(int(A.READ_BURST) + 5)]
    assert codes.count(429) == 5
    clock["t"] += 10  # tokens refill with time
    assert c.get("/api/health").status_code == 200
    writes = [c.post("/api/alerts/7/actions", json=ESC).status_code
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


def test_the_manager_page_takes_a_scope_and_a_visitor(client):
    assert client.get(f"/api/manager?visitor={ME}").json()["scope"] == "me"
    assert client.get(f"/api/manager?visitor={ME}&scope=all").json()["scope"] == "all"
    assert client.get(f"/api/manager?visitor={ME}&scope=everyone").status_code == 422
    assert client.get("/api/manager").status_code == 422


# ---- S8b.4d: strict JSON (a browser refuses NaN; Python's own reader accepts it) -----------


def _strict(text):
    import json

    def refuse(name):
        raise ValueError(f"not JSON: {name}")

    return json.loads(text, parse_constant=refuse)


def test_the_api_json_has_no_nan_or_infinity_anywhere():
    from graphguard.demo.queries import to_json

    nan, inf = float("nan"), float("inf")
    obj = {"v": nan, "w": [1.5, -inf, {"x": inf}], "t": (nan,), "ok": 2.0, "s": "NaN", "d": T}
    assert _strict(to_json(obj)) == {"v": None, "w": [1.5, None, {"x": None}], "t": [None],
                                     "ok": 2.0, "s": "NaN", "d": str(T)}  # fmt: skip


def test_an_alert_whose_sender_never_paid_before_opens_in_a_browser():
    class NeverPaid(FakeRepo):
        def alert(self, event_id):
            a = super().alert(event_id)
            return a and {**a, "contributions": [
                {"feature": "sender_seconds_since_last_send", "value": float("nan"),
                 "contribution": -0.79}]}  # fmt: skip

    r = TestClient(A.create_app(repo=NeverPaid())).get("/api/alerts/7")
    assert r.status_code == 200
    assert _strict(r.text)["contributions"][0]["value"] is None
