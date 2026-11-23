"""The live demo database (S7.1): each role does only its job; the data is the whole window.

Needs GraphGuard's Postgres and `.secrets/demo-db.env` (after `just demo-setup` and
`just demo-build`); skips elsewhere (CI), reason printed.
"""

import os

import pytest

from graphguard.config import REPO_ROOT
from graphguard.demo import db

SECRETS = REPO_ROOT / ".secrets"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1"
        or not (SECRETS / db.ENV_FILE).exists(),
        reason="no GraphGuard Postgres / demo database in this environment",
    ),
]


def _conn(role):
    c = db.connect(role, secrets_dir=SECRETS)
    c.autocommit = True
    return c


def _refused(role, sql):
    import psycopg2

    with _conn(role) as c, c.cursor() as cur:
        try:
            cur.execute(sql)
        except psycopg2.errors.InsufficientPrivilege:
            return True
    return False


def test_the_reader_sees_the_whole_validation_window():
    with _conn(db.READER) as c, c.cursor() as cur:
        cur.execute("SELECT count(*), min(rank), max(rank) FROM transactions")
        assert cur.fetchone() == (1_015_300, 1, 1_015_300)
        cur.execute("SELECT count(*) FILTER (WHERE is_laundering), count(*) FROM truth")
        assert cur.fetchone() == (1_083, 1_015_300)  # s6.8-rules.json: 1,083 laundering
        cur.execute("SELECT priority FROM transactions ORDER BY rank LIMIT 1")
        top = cur.fetchone()[0]
        cur.execute("SELECT max(priority) FROM transactions")
        assert cur.fetchone()[0] == top


def test_the_queue_order_matches_the_streams_alerts():
    # the stream flagged exactly the top 5,000 by priority (ADR 0007's alert line)
    with _conn(db.READER) as c, c.cursor() as cur:
        cur.execute("SELECT count(*), max(rank) FROM transactions WHERE alert")
        assert cur.fetchone() == (5_000, 5_000)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO verdicts (event_id, verdict) VALUES (1, 'close')",
        "UPDATE transactions SET score = 0 WHERE rank = 1",
        "DELETE FROM truth WHERE event_id = 1",
        "CREATE TABLE x (i int)",
    ],
)
def test_the_reader_cannot_change_anything(sql):
    assert _refused(db.READER, sql)


def test_the_writer_can_only_add_a_verdict():
    with _conn(db.WRITER) as c, c.cursor() as cur:
        cur.execute("INSERT INTO verdicts (event_id, verdict, note) VALUES (-1, 'close', 'test')")
    assert _refused(db.WRITER, "SELECT * FROM transactions LIMIT 1")
    assert _refused(db.WRITER, "UPDATE verdicts SET verdict = 'escalate'")
    assert _refused(db.WRITER, "DELETE FROM verdicts")
    with _conn(db.OWNER) as c, c.cursor() as cur:  # tidy up our own test row
        cur.execute("DELETE FROM verdicts WHERE event_id = -1 AND note = 'test'")


def test_a_bad_verdict_is_rejected_by_the_table_itself():
    import psycopg2

    with _conn(db.WRITER) as c, c.cursor() as cur, pytest.raises(psycopg2.errors.CheckViolation):
        cur.execute("INSERT INTO verdicts (event_id, verdict) VALUES (-1, 'delete everything')")


def test_the_stream_login_cannot_even_connect_to_the_demo():
    # so no stream reset (db.reset) can ever reach these tables
    import psycopg2

    from graphguard.stream import db as sdb

    dsn = sdb.dsn(secrets_dir=SECRETS).rsplit("/", 1)[0] + "/demo"
    with pytest.raises(psycopg2.OperationalError):
        psycopg2.connect(dsn, connect_timeout=5)


def test_the_build_is_recorded():
    with _conn(db.READER) as c, c.cursor() as cur:
        cur.execute("SELECT info FROM build_info")
        info = cur.fetchone()[0]
    assert info["rows"]["transactions"] == 1_015_300
    assert set(info["fingerprints"]) == set(db.LOADED)  # every loaded table


def test_the_answer_key_holds_the_168_validation_rings_and_no_other():
    with _conn(db.READER) as c, c.cursor() as cur:
        cur.execute("SELECT count(DISTINCT pattern_id) FROM truth WHERE pattern_id IS NOT NULL")
        assert cur.fetchone()[0] == 168
        # every ring row is a validation transaction (truth only holds the window's rows)
        cur.execute("SELECT count(*) FROM truth t LEFT JOIN transactions x USING (event_id) "
                    "WHERE x.event_id IS NULL")  # fmt: skip
        assert cur.fetchone()[0] == 0


def test_the_capacity_numbers_match_the_evaluation():
    with _conn(db.READER) as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM capacity")
        assert cur.fetchone()[0] == 20_000
        cur.execute("SELECT ranking, caught, rings_caught, rings_total FROM capacity "
                    "WHERE k = 5000 ORDER BY ranking")  # fmt: skip
        got = {r[0]: r[1:] for r in cur.fetchall()}
    assert got["model"][:2] == (542, 127)  # s6.8-rules.json; the leakage audit's 127 / 168
    assert got["rules"][0] == 21  # FINDING-016
    assert {v[2] for v in got.values()} == {168}


def test_the_top_of_the_queue_is_explained_in_three_plain_reasons():
    with _conn(db.READER) as c, c.cursor() as cur:
        cur.execute("SELECT count(*), min(cardinality(reasons)), max(cardinality(reasons)), "
                    "min(cardinality(contribs)) FROM explanations")  # fmt: skip
        n, lo, hi, nf = cur.fetchone()
        assert (n, nf) == (20_000, 15) and 0 <= lo and hi == 3
        # S7.13 (changed on purpose): weekday is never a reason, so an alert whose only upward
        # push was the weekday has no model reason -- allowed only when a rule (ADR 0007's
        # priority: both accounts new, or two rules) is what put it in the queue.
        cur.execute("SELECT t.rules FROM explanations e JOIN transactions t USING (event_id) "
                    "WHERE cardinality(e.reasons) = 0")  # fmt: skip
        assert all("both_new" in r or len(r) >= 2 for (r,) in cur.fetchall())
        cur.execute("SELECT count(*) FROM explanations e JOIN transactions t USING (event_id) "
                    "WHERE t.rank > 20000")  # fmt: skip
        assert cur.fetchone()[0] == 0
        # contributions + base = the model's margin: sigmoid gives back the stored score
        cur.execute("SELECT max(abs(1 / (1 + exp(-(e.base + (SELECT sum(x) FROM "
                    "unnest(e.contribs) x)))) - t.score)) FROM explanations e "
                    "JOIN transactions t USING (event_id)")  # fmt: skip
        assert cur.fetchone()[0] < 1e-5


def test_every_stored_ring_is_strictly_before_its_alert_and_carries_no_label():
    with _conn(db.READER) as c, c.cursor() as cur:
        cur.execute("SELECT count(*) FROM subgraphs")
        assert cur.fetchone()[0] == 20_000
        # (time, source_row) of every edge vs its alert's: the alert edge itself, or before
        cur.execute("""
            SELECT count(*) FROM subgraphs s
            JOIN transactions a ON a.event_id = s.event_id,
            LATERAL jsonb_array_elements(s.graph->'edges') e
            WHERE (e->>'id')::bigint <> a.event_id
              AND ((e->>'t')::timestamp > a.event_time
                   OR ((e->>'t')::timestamp = a.event_time AND (e->>'id')::bigint > a.event_id))
        """)  # fmt: skip
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM subgraphs WHERE graph::text ~ '(laundering|pattern)'")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT max(jsonb_array_length(graph->'edges')) FROM subgraphs")
        assert cur.fetchone()[0] <= 1 + 6 * (1 + 6) * 2 + 6 * 2  # the cap's ceiling
