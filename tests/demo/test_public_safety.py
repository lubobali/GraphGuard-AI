"""S8b.2: safe to open to the internet -- the real address behind nginx, bounded memory, write
caps, one live stream per address, a linear manager view, query time limits, plain errors."""

import threading
import time

import pytest
from fastapi.testclient import TestClient
from test_api import FakeRepo  # tests/demo is on the path (no __init__)

from graphguard.demo import api as A
from graphguard.demo import workflow as W

pytestmark = pytest.mark.unit

GW = A.TRUSTED_PROXY
V = "11111111-1111-4111-8111-111111111111"


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class CountingRepo(FakeRepo):
    def __init__(self, last_day=0):
        super().__init__()
        self.last_day = last_day

    def visitor_actions_last_day(self):
        return self.last_day


def act(c, ip="203.0.113.9", **kw):
    body = {"visitor": V, "role": "investigator", "action": "escalate", "reason": "x", **kw}
    return c.post("/api/alerts/7/actions", json=body, headers={"X-Real-IP": ip})


def app(repo=None, **kw):
    c = TestClient(A.create_app(repo=repo or CountingRepo(), **kw), client=(GW, 5000),
                   raise_server_exceptions=False)  # fmt: skip
    return c


# ---- the real address ----------------------------------------------------------------------


def test_the_real_address_is_taken_only_from_the_proxy_and_only_if_it_is_an_address():
    assert A.client_ip(GW, "203.0.113.9", GW) == "203.0.113.9"
    assert A.client_ip(GW, "2001:db8::1", GW) == "2001:db8::1"
    assert A.client_ip("198.51.100.7", "203.0.113.9", GW) == "198.51.100.7"  # spoofed: ignored
    assert A.client_ip(GW, "not-an-ip", GW) == GW
    assert A.client_ip(GW, None, GW) == GW
    assert A.client_ip(GW, "203.0.113.9, 10.0.0.1", GW) == GW  # nginx sends exactly one


def test_two_visitors_behind_nginx_have_their_own_limits():
    c = app()
    for _ in range(int(A.WRITE_BURST)):
        assert act(c, ip="203.0.113.1").status_code in (201, 200)
    assert act(c, ip="203.0.113.1").status_code == 429
    assert act(c, ip="203.0.113.2").status_code in (201, 200)  # another person is not blocked


def test_a_spoofed_header_from_elsewhere_does_not_escape_the_limit():
    c = TestClient(A.create_app(repo=CountingRepo()), client=("198.51.100.7", 5000))
    codes = [act(c, ip=f"203.0.113.{i}").status_code for i in range(int(A.WRITE_BURST) + 1)]
    assert codes[-1] == 429


# ---- bounded memory --------------------------------------------------------------------------


def test_the_limiter_forgets_idle_addresses_so_its_memory_is_bounded():
    clock = Clock()
    lim = A.RateLimiter(clock=clock, max_entries=1_000)
    for i in range(100_000):
        lim.allow(f"ip{i}", "read", 20, 40)
        clock.t += 0.02  # 100,000 addresses over ~33 minutes
    assert len(lim.state) <= 1_000


# ---- write caps ------------------------------------------------------------------------------


def test_an_address_may_save_at_most_the_daily_cap():
    clock = Clock()
    c = TestClient(A.create_app(repo=CountingRepo(), limiter=A.RateLimiter(clock=clock),
                                clock=clock), client=(GW, 5000))  # fmt: skip
    saved = 0
    for i in range(A.WRITES_PER_IP_DAY + 5):
        clock.t += 2  # slower than the rate limit
        r = act(c, reason=f"r{i}")
        saved += r.status_code == 201
        if r.status_code == 503:
            assert "full" in r.json()["detail"]
    assert saved == A.WRITES_PER_IP_DAY
    clock.t += 86_400  # the next day
    assert act(c, reason="tomorrow").status_code == 201


def test_the_whole_demo_stops_saving_at_the_total_daily_cap():
    c = app(repo=CountingRepo(last_day=A.WRITES_TOTAL_DAY))
    r = act(c)
    assert r.status_code == 503 and "full" in r.json()["detail"]
    assert c.get("/api/health").status_code == 200  # reading still works


# ---- live streams ----------------------------------------------------------------------------


def test_one_address_holds_at_most_one_live_stream():
    st = A.create_app(repo=CountingRepo()).state
    assert A._take_live_slot(st, "203.0.113.1")
    assert not A._take_live_slot(st, "203.0.113.1")
    assert A._take_live_slot(st, "203.0.113.2")
    A._give_live_slot(st, "203.0.113.1")
    assert A._take_live_slot(st, "203.0.113.1")


# ---- the manager's all-visitors view ---------------------------------------------------------


def test_the_all_visitors_view_is_linear_in_saved_rows():
    rows = [{"event_id": i % 5_000, "case_owner": f"{i % 4_000:036d}", "actor": "a",
             "role": "investigator", "action": "escalate", "code": None, "reason": "x",
             "at": None} for i in range(20_000)]  # fmt: skip
    t0 = time.perf_counter()
    cases = W.cases_by_owner(rows, {i: i % 2 == 0 for i in range(5_000)})
    assert time.perf_counter() - t0 < 1.0
    assert len(cases) == len({(r["event_id"], r["case_owner"]) for r in rows})
    assert all(c["state"] == "awaiting_review" for c in cases)


def test_the_all_visitors_view_is_cached_briefly():
    class Counting(CountingRepo):
        calls = 0

        def manager(self, viewer, scope, k):
            Counting.calls += scope == "all"
            return super().manager(viewer, scope, k)

    clock = Clock()
    c = TestClient(A.create_app(repo=Counting(), clock=clock), client=(GW, 5000))
    for _ in range(3):
        assert c.get(f"/api/manager?visitor={V}&scope=all").status_code == 200
    assert Counting.calls == 1
    clock.t += A.MANAGER_CACHE_SECONDS + 1
    c.get(f"/api/manager?visitor={V}&scope=all")
    assert Counting.calls == 2


# ---- time limits and errors ------------------------------------------------------------------


def test_every_database_login_carries_a_statement_time_limit():
    from graphguard.demo.queries import dsn

    d = dsn("demo_reader", "p@ss/word", "db:5432")  # a made-up password with URL characters
    expected = "postgresql://demo_reader:p%40ss%2Fword@db:5432/demo?"  # betterleaks:allow -- fake
    assert d.startswith(expected)
    assert "statement_timeout%3D5000" in d


def test_a_crash_answers_a_plain_500_with_nothing_inside(caplog):
    class Broken(CountingRepo):
        def meta(self):
            raise RuntimeError("secret detail /srv/x password=1")

    r = app(repo=Broken()).get("/api/meta")
    assert "unhandled error on GET /api/meta" in caplog.text  # logged for us, not shown
    assert r.status_code == 500 and r.json() == {"detail": "internal error"}
    assert "secret" not in r.text and "Traceback" not in r.text
    assert r.headers["X-Content-Type-Options"] == "nosniff"


# ---- clean-up ------------------------------------------------------------------------------


class FakeConn:
    def __init__(self):
        self.sql = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return self

    def execute(self, sql, args):
        self.sql.append((sql, args))
        self.rowcount = 3


def test_the_clean_up_deletes_by_age_only_and_refuses_a_negative_age():
    from graphguard.demo import db

    conn = FakeConn()
    assert db.clear_visitors(7, conn) == 3
    [(sql, args)] = conn.sql
    assert sql.startswith("DELETE FROM case_actions WHERE at < now() - ") and args == (7,)
    with pytest.raises(ValueError):
        db.clear_visitors(-1, conn)
    assert db.main(["db", "clear-visitors"]) == 2 and db.main(["db", "clear-visitors", "x"]) == 2


# ---- the connection pool waits instead of failing (found by the load test) -------------------


class FakePool:
    """psycopg2's ThreadedConnectionPool: raises when every connection is out."""

    def __init__(self, n):
        self.free, self.lock, self.closed = n, threading.Lock(), 0

    def getconn(self):
        with self.lock:
            if self.free == 0:
                raise RuntimeError("connection pool exhausted")
            self.free -= 1
            return object()

    def putconn(self, conn, close=False):
        with self.lock:
            self.free += 1
            self.closed += close


def test_more_requests_than_connections_wait_their_turn():
    from graphguard.demo.queries import WaitingPool

    pool = WaitingPool(FakePool(2), size=2, wait=5)
    errors = []

    def use():
        try:
            c = pool.getconn()
            time.sleep(0.02)
            pool.putconn(c)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=use) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_a_full_pool_answers_busy_after_the_wait_not_a_crash():
    from graphguard.demo.queries import Busy, WaitingPool

    pool = WaitingPool(FakePool(1), size=1, wait=0.05)
    pool.getconn()
    with pytest.raises(Busy):
        pool.getconn()

    class BusyRepo(CountingRepo):
        def meta(self):
            raise Busy

    r = app(repo=BusyRepo()).get("/api/meta")
    assert r.status_code == 503 and r.json() == {"detail": "busy, try again in a moment"}
