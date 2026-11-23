"""The demo API on the real demo database (S7.6), through the same query layer the
container uses. Skips where there is no demo database (CI)."""

import os

import pytest
from fastapi.testclient import TestClient

from graphguard.config import REPO_ROOT

SECRETS = REPO_ROOT / ".secrets"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1"
        or not (SECRETS / "demo-api.env").exists(),
        reason="no demo database in this environment",
    ),
]


@pytest.fixture(scope="module")
def client():
    from graphguard.demo.api import create_app
    from graphguard.demo.queries import PgRepo

    return TestClient(create_app(repo=PgRepo()))


def test_the_api_holds_only_the_reader_and_writer_logins():
    keys = {ln.split("=", 1)[0] for ln in (SECRETS / "demo-api.env").read_text().splitlines()
            if "=" in ln and not ln.startswith("#")}  # fmt: skip
    assert keys == {"DEMO_READER_PASSWORD", "DEMO_WRITER_PASSWORD"}


def test_a_100_a_day_queue_groups_its_211_alerts_by_account_in_rank_order(client):
    q = client.get("/api/queue?per_day=100").json()
    assert q["k"] == 211 and q["alerts"] == 211
    ranks = [g["rank"] for g in q["groups"]]
    assert ranks == sorted(ranks) and ranks[0] == 1
    assert all(g["alerts"] >= 1 for g in q["groups"])


def test_capacity_at_5000_says_542_and_127(client):
    r = client.get("/api/capacity?per_day=2373").json()  # k = 5,000
    assert r["k"] == 5_000 and (r["rankings"]["model"]["caught"],
                                r["rankings"]["model"]["rings_caught"]) == (542, 127)  # fmt: skip


def test_an_alert_has_its_reasons_its_ring_and_never_a_label(client):
    q = client.get("/api/queue?per_day=100").json()
    a = client.get(f"/api/alerts/{q['groups'][0]['event_id']}").json()
    assert len(a["reasons"]) == 3 and a["ring"]["alert"] == a["event_id"]
    assert len(a["contributions"]) == 15
    assert "is_laundering" not in a and "pattern_id" not in str(a)


def test_no_weekday_reason_in_the_top_of_the_queue_and_groups_add_up(client):
    """S7.13: the simulator's weekday is never a shown reason; an alert's behaviour groups
    add up to its per-feature contributions (nothing hidden, nothing double-counted)."""
    rows = []
    for page in range(1, 6):
        rows += client.get(f"/api/queue?per_day=100&page={page}").json()["groups"]
    assert len(rows) == 190  # the 211 alerts, grouped by sender
    assert not [r for r in rows if r["top_reason"] and "Wednesday" in r["top_reason"]]
    assert not [r for r in rows if r["top_reason"] and "simulator" in r["top_reason"]]
    for r in rows[:20]:
        a = client.get(f"/api/alerts/{r['event_id']}").json()
        total = sum(c["contribution"] for c in a["contributions"])
        assert sum(g["contribution"] for g in a["groups"]) == pytest.approx(total, abs=1e-9)
        assert a["groups"][-1]["key"] == "calendar"


def test_the_answer_key_agrees_with_truth(client):
    from graphguard.demo import db

    with db.connect(db.READER, secrets_dir=SECRETS) as c, c.cursor() as cur:
        cur.execute("SELECT event_id, is_laundering FROM truth WHERE pattern_id IS NOT NULL "
                    "ORDER BY event_id LIMIT 1")  # fmt: skip
        eid, label = cur.fetchone()
    ans = client.get(f"/api/alerts/{eid}/answer").json()
    assert ans["is_laundering"] == label and eid in ans["ring_hops"]


def test_a_case_goes_from_decision_to_review_through_the_api(client):
    """S7.15 live: decide, a double click stores one row, change, approve, SAR due; another
    visitor sees none of it; the next alert skips what was decided."""
    from graphguard.demo import db

    me, other = "00000000-0000-4000-8000-0000000000a1", "00000000-0000-4000-8000-0000000000b2"
    eid = client.get("/api/queue?per_day=100").json()["groups"][0]["event_id"]
    url = f"/api/alerts/{eid}/actions"
    base = {"visitor": me, "role": "investigator", "reason": "live test, S7.15"}
    try:
        assert (
            client.post(url, json={**base, "action": "close", "code": "other"}).status_code == 201
        )
        assert (
            client.post(url, json={**base, "action": "close", "code": "other"}).status_code == 200
        )
        assert client.post(url, json={**base, "action": "escalate"}).status_code == 201
        r = client.post(url, json={**base, "role": "reviewer", "action": "approve", "reason": ""})
        assert r.status_code == 201 and r.json()["case"]["state"] == "escalated"
        assert r.json()["case"]["sar_due"]
        case = client.get(f"/api/alerts/{eid}/case?visitor={me}").json()["mine"]
        assert [h["action"] for h in case["history"]] == ["close", "escalate", "approve"]
        assert client.get(f"/api/alerts/{eid}/case?visitor={other}").json()["mine"]["history"] == []
        d = client.get(f"/api/decisions?visitor={me}").json()
        mine = [c for c in d["cases"] if c["owner"] == me]
        assert mine[0]["event_id"] == eid and mine[0]["is_laundering"] is not None
        assert d["score"]["decided"] == 1
        sam = [c for c in d["cases"] if c["owner"] == "demo"]
        assert len(sam) == 8 and all(c["is_laundering"] is None for c in sam)  # not reviewed yet
        nxt = client.get(f"/api/next?visitor={me}&after=0").json()
        assert nxt["event_id"] != eid
    finally:
        with db.connect(db.OWNER, secrets_dir=SECRETS) as c, c.cursor() as cur:
            cur.execute("DELETE FROM case_actions WHERE actor IN (%s, %s)", (me, other))


def test_the_manager_numbers_equal_a_direct_count_and_never_leak_ids(client):
    """S7.16 live: one visitor's decisions show up in "me" and in "all"; "all" carries no
    visitor id and no other visitor's words."""
    from graphguard.demo import db
    from graphguard.demo.api import RateLimiter

    client.app.state.limiter = RateLimiter()  # the module's client shares one write budget
    me = "00000000-0000-4000-8000-0000000000d4"
    q = client.get("/api/queue?per_day=100").json()["groups"]
    try:
        for g, (action, code) in zip(q[:3], [("escalate", None), ("close", "explained"),
                                             ("close", "other")], strict=True):  # fmt: skip
            r = client.post(f"/api/alerts/{g['event_id']}/actions", json={
                "visitor": me, "role": "investigator", "action": action, "code": code,
                "reason": "live test, S7.16"})  # fmt: skip
            assert r.status_code == 201
        m = client.get(f"/api/manager?visitor={me}").json()
        assert (m["decided"], m["escalated"], m["closed"], m["waiting_review"]) == (3, 1, 2, 3)
        assert m["backlog"]["total"] == 211 - 3 and len(m["qa"]) == 2
        everyone = client.get(f"/api/manager?visitor={me}&scope=all")
        with db.connect(db.READER, secrets_dir=SECRETS) as c, c.cursor() as cur:
            cur.execute("SELECT count(DISTINCT (event_id, case_owner)) FROM case_actions "
                        "WHERE case_owner <> 'demo' AND role = 'investigator'")  # fmt: skip
            assert everyone.json()["decided"] <= cur.fetchone()[0]
        assert me not in everyone.text and "live test, S7.16" not in everyone.text
    finally:
        with db.connect(db.OWNER, secrets_dir=SECRETS) as c, c.cursor() as cur:
            cur.execute("DELETE FROM case_actions WHERE actor = %s", (me,))
