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


def test_a_verdict_lands_in_the_audit_table(client):
    from graphguard.demo import db

    q = client.get("/api/queue?per_day=100").json()
    eid = q["groups"][0]["event_id"]
    note = "live test, S7.6"
    assert client.post(f"/api/alerts/{eid}/verdict",
                       json={"verdict": "close", "note": note}).status_code == 201  # fmt: skip
    with db.connect(db.OWNER, secrets_dir=SECRETS) as c, c.cursor() as cur:
        cur.execute("DELETE FROM verdicts WHERE event_id = %s AND note = %s", (eid, note))
        assert cur.rowcount == 1
