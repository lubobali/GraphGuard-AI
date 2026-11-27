"""The demo API's queries (S7.6). Reads connect as `demo_reader` only; the verdict -- the one
write -- as `demo_writer` (INSERT into verdicts, nothing else). No polars/numpy here: the API
container stays small.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from urllib.parse import quote

from graphguard.demo.reasons import RULE_TEXT

WINDOW_DAYS = 50.5667 / 24  # the validation window, 2022-09-06 13:34 -> 09-08 16:08
MAX_K = 5_000
BANNER = (
    "Synthetic data (IBM AMLworld simulator), validation window 2022-09-06 to 09-08. "
    "No real people or banks."
)


def k_for(per_day: float) -> int:
    """A team working `per_day` alerts a day handles k alerts over the window."""
    return max(1, min(MAX_K, round(per_day * WINDOW_DAYS)))


def _env(path: str) -> dict[str, str]:
    with open(path) as f:
        return dict(ln.strip().split("=", 1) for ln in f if "=" in ln and not ln.startswith("#"))


# S7.17 / FINDING-020: the only reviewer whose "strong" label held up in testing (it never
# called a right decision "strong"); the manager's count uses it alone.
TRUSTED_REVIEWER = "anthropic/claude-sonnet-5.5"


class Busy(Exception):
    """Every database connection is in use and none came free in time (the API answers 503)."""


class WaitingPool:
    """S8b.2: psycopg2's pool raises when all its connections are out; the API runs up to 40
    requests at once, so under load most failed (the load test: 31% 500s). This waits for a
    connection, up to `wait` seconds, then raises Busy. A broken connection is closed, not
    reused (a Postgres restart would otherwise poison the pool)."""

    def __init__(self, pool, size: int, wait: float = 10.0):
        self.pool, self.wait = pool, wait
        self.slots = threading.BoundedSemaphore(size)

    def getconn(self):
        if not self.slots.acquire(timeout=self.wait):
            raise Busy
        try:
            return self.pool.getconn()
        except BaseException:
            self.slots.release()
            raise

    def putconn(self, conn, close: bool = False) -> None:
        try:
            self.pool.putconn(conn, close=close)
        finally:
            self.slots.release()


STATEMENT_TIMEOUT_MS = 5_000  # S8b.2: no query from a public visitor runs longer


def dsn(role: str, password: str, host: str) -> str:
    """A demo login, with a time limit on every statement."""
    opts = quote(f"-c statement_timeout={STATEMENT_TIMEOUT_MS}", safe="")
    return f"postgresql://{role}:{quote(password, safe='')}@{host}/demo?options={opts}"


class PgRepo:
    """Small connection pools: reads as demo_reader, the verdict as demo_writer."""

    def __init__(self, host: str | None = None, env_file: str | None = None):
        from psycopg2.pool import ThreadedConnectionPool

        host = host or os.environ.get("GRAPHGUARD_DEMO_DB", "127.0.0.1:5434")
        # In the container the logins arrive as environment (compose env_file); on the
        # host (tests) from .secrets/demo-api.env.
        if "DEMO_READER_PASSWORD" in os.environ:
            env = dict(os.environ)
        else:
            from graphguard.config import REPO_ROOT

            env = _env(env_file or str(REPO_ROOT / ".secrets" / "demo-api.env"))

        self._read = WaitingPool(
            ThreadedConnectionPool(1, 4, dsn("demo_reader", env["DEMO_READER_PASSWORD"], host)), 4
        )
        self._write = WaitingPool(
            ThreadedConnectionPool(1, 1, dsn("demo_writer", env["DEMO_WRITER_PASSWORD"], host)), 1
        )
        self._lock = threading.Lock()

    @contextmanager
    def _cur(self, pool):
        import psycopg2

        conn = pool.getconn()
        broken = False
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                yield cur
        except psycopg2.OperationalError:
            broken = True
            raise
        finally:
            pool.putconn(conn, close=broken or bool(conn.closed))

    def _all(self, sql: str, args=()) -> list[dict]:
        with self._cur(self._read) as cur:
            cur.execute(sql, args)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]

    def _one(self, sql: str, args=()) -> dict | None:
        rows = self._all(sql, args)
        return rows[0] if rows else None

    # --- reads -----------------------------------------------------------------------
    def meta(self) -> dict:
        info = self._one("SELECT info FROM build_info")
        return {
            "banner": BANNER,
            "window_days": WINDOW_DAYS,
            "build": info["info"] if info else None,
        }

    def capacity(self, k: int) -> dict:
        rows = self._all(
            "SELECT ranking, k, caught, missed, precision, recall, rings_caught, "
            "rings_touched, rings_total FROM capacity WHERE k = %s",
            (k,),
        )
        return {r["ranking"]: r for r in rows}

    def capacity_curve(self, step: int = 25) -> dict:
        rows = self._all(
            "SELECT ranking, k, caught, rings_caught FROM capacity "
            "WHERE k = 1 OR k %% %s = 0 ORDER BY ranking, k",
            (step,),
        )
        out: dict[str, list] = {}
        for r in rows:
            out.setdefault(r["ranking"], []).append([r["k"], r["caught"], r["rings_caught"]])
        return out

    def queue(self, k: int, page: int, page_size: int = 50) -> dict:
        groups = self._all(
            """
            WITH q AS (SELECT * FROM transactions WHERE rank <= %(k)s),
            g AS (SELECT from_bank, from_account, count(*) AS alerts, min(rank) AS best
                  FROM q GROUP BY from_bank, from_account)
            SELECT g.alerts, q.event_id, q.rank, q.percentile, q.event_time,
                   q.event_time + interval '24 hours' AS due, q.amount_paid,
                   q.payment_currency, q.payment_format, q.cold_policy, q.rules,
                   q.from_name, q.from_bank_name, q.to_name, q.to_bank_name,
                   q.from_account, q.to_account, e.reasons[1] AS top_reason,
                   EXISTS (SELECT 1 FROM agent_reports a WHERE a.event_id = q.event_id)
                     AS has_ai
            FROM g JOIN q ON q.rank = g.best
            LEFT JOIN explanations e ON e.event_id = q.event_id
            ORDER BY g.best LIMIT %(lim)s OFFSET %(off)s
            """,
            {"k": k, "lim": page_size, "off": (page - 1) * page_size},
        )
        total = self._one(
            "SELECT count(*) AS alerts, count(DISTINCT (from_bank, from_account)) AS accounts "
            "FROM transactions WHERE rank <= %s",
            (k,),
        )
        return {"k": k, "page": page, "page_size": page_size, **total, "groups": groups}

    def alert(self, event_id: int) -> dict | None:
        tx = self._one(
            "SELECT t.event_id, t.event_time, t.from_bank, t.from_account, t.from_bank_name, "
            "t.from_name, t.to_bank, t.to_account, t.to_bank_name, t.to_name, t.amount_paid, "
            "t.payment_currency, t.amount_received, t.receiving_currency, t.payment_format, "
            "t.rank, t.percentile, t.alert, t.cold_policy, t.rules, t.features, "
            "t.model_version, e.base, e.contribs, e.reasons, e.groups "
            "FROM transactions t LEFT JOIN explanations e USING (event_id) WHERE event_id = %s",
            (event_id,),
        )
        if tx is None:
            return None
        names = (self.meta()["build"] or {}).get("feature_names", [])
        contribs = tx.pop("contribs")
        values = tx.pop("features")
        tx["contributions"] = (
            sorted(
                [
                    {"feature": f, "value": v, "contribution": c}
                    for f, v, c in zip(names, values, contribs, strict=True)
                ],
                key=lambda d: -abs(d["contribution"]),
            )
            if contribs
            else None
        )
        tx["rule_text"] = [RULE_TEXT.get(r, r) for r in tx["rules"]]
        tx["history"] = {
            side: self._all(
                f"SELECT event_id, event_time, from_name, to_name, amount_paid, "
                f"payment_currency, payment_format, rank FROM transactions "
                f"WHERE {side}_account = %s AND (event_time, event_id) < (%s, %s) "
                f"ORDER BY event_time DESC, event_id DESC LIMIT 20",
                (tx[f"{side}_account"], tx["event_time"], event_id),
            )
            for side in ("from", "to")
        }
        g = self._one("SELECT graph FROM subgraphs WHERE event_id = %s", (event_id,))
        tx["ring"] = g["graph"] if g else None
        tx["reviews"] = self._all(
            "SELECT direction, model, review FROM ai_reviews WHERE event_id = %s "
            "ORDER BY direction, model",
            (event_id,),
        )
        tx["agent"] = self._all(
            "SELECT model, report, at FROM agent_reports WHERE event_id = %s ORDER BY model",
            (event_id,),
        )
        return tx

    def answer(self, event_id: int) -> dict | None:
        t = self._one(
            "SELECT is_laundering, pattern_id, pattern_type, hop FROM truth WHERE event_id = %s",
            (event_id,),
        )
        if t is None:
            return None
        t["ring_hops"] = (
            [
                r["event_id"]
                for r in self._all(
                    "SELECT event_id FROM truth WHERE pattern_id = %s ORDER BY hop",
                    (t["pattern_id"],),
                )
            ]
            if t["pattern_id"] is not None
            else []
        )
        return t

    def performance(self, k: int) -> dict:
        measured = self.capacity(k).get("system")
        known = self._one(
            "SELECT count(*) AS known, count(*) FILTER (WHERE label) AS laundering, "
            "max(label_known_at) AS latest FROM labels WHERE label_known_at <= "
            "(SELECT max(event_time) FROM transactions)"
        )
        total = self._one("SELECT count(*) AS laundering FROM truth WHERE is_laundering")
        return {
            "measured_offline": measured,
            "confirmed_so_far": known,
            "laundering_in_window": total["laundering"],
            "note": "labels arrive days to weeks later (FINDING-017); investigation labels "
            "exist only for alerts that were worked, so they favour the model that chose them",
        }

    def live(self, after: tuple, limit: int) -> list[dict]:
        return self._all(
            "SELECT event_id, event_time, from_name, to_name, amount_paid, payment_currency, "
            "rank, percentile, alert FROM transactions WHERE (event_time, event_id) > (%s, %s) "
            "ORDER BY event_time, event_id LIMIT %s",
            (after[0], after[1], limit),
        )

    # --- the one write ----------------------------------------------------------------
    # ---- S7.15: the case workflow ----------------------------------------------------
    _ROW = "event_id, case_owner, actor, role, action, code, reason, at"

    def case_rows(self, event_id: int) -> list[dict]:
        return self._all(
            f"SELECT {self._ROW} FROM case_actions WHERE event_id = %s ORDER BY id", (event_id,)
        )

    def visitor_actions_last_day(self) -> int:
        """S8b.2: what all visitors saved in the last 24 hours (the demo's daily cap)."""
        return self._one(
            "SELECT count(*) AS n FROM case_actions WHERE at > now() - interval '24 hours'"
        )["n"]

    def add_action(self, event_id, owner, actor, role, action, code, reason) -> None:
        with self._cur(self._write) as cur:
            cur.execute(
                "INSERT INTO case_actions (event_id, case_owner, actor, role, action, code, "
                "reason) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (event_id, owner, actor, role, action, code, reason),
            )

    def decisions(self, viewer: str) -> list[dict]:
        """The viewer's own cases and their private copy of Sam's, each with its state. The
        answer key is attached only once the viewer has acted on the case (training mode)."""
        from graphguard.demo import workflow as W

        rows = self._all(
            f"SELECT {self._ROW} FROM case_actions WHERE actor = %s OR case_owner = %s ORDER BY id",
            (viewer, viewer),
        )
        keys = {(r["event_id"], r["case_owner"]) for r in rows if r["case_owner"] == viewer}
        keys |= {(c[0], W.DEMO) for c in W.DEMO_CASES}
        ids = sorted({k[0] for k in keys})
        info = {
            r["event_id"]: r
            for r in self._all(
                "SELECT t.event_id, t.rank, t.from_name, t.to_name, t.amount_paid, "
                "t.payment_currency, tr.is_laundering FROM transactions t "
                "JOIN truth tr USING (event_id) WHERE t.event_id = ANY(%s)",
                (ids,),
            )
        }
        out = []
        for eid, owner in sorted(keys, key=lambda k: (info[k[0]]["rank"], k[1])):
            seed = W.demo_history(eid) if owner == W.DEMO else []
            mine = [r for r in rows if r["event_id"] == eid]
            history = seed + W.visible(mine, owner, viewer)
            st = W.case_state(history)
            acted = any(r["actor"] == viewer for r in history)
            i = info[eid]
            out.append({
                "event_id": eid, "owner": owner, "rank": i["rank"], "from_name": i["from_name"],
                "to_name": i["to_name"], "amount_paid": i["amount_paid"],
                "payment_currency": i["payment_currency"], **st,
                "acted": acted, "is_laundering": i["is_laundering"] if acted else None,
            })  # fmt: skip
        return out

    def manager(self, viewer: str, scope: str, k: int) -> dict:
        """The manager's page (S7.16). `me`: this visitor's cases; `all`: every visitor's
        cases (Sam's excluded), counts only -- no visitor id and no other visitor's words."""
        from graphguard.demo import workflow as W

        if scope == "me":
            cases = [c for c in self.decisions(viewer) if c["owner"] == viewer]
            reviews = self._one(
                "SELECT count(*) AS n FROM case_actions WHERE actor = %s AND role = 'reviewer'",
                (viewer,),
            )["n"]
            decided = {c["event_id"] for c in cases}
        else:
            rows = self._all(
                f"SELECT {self._ROW} FROM case_actions WHERE case_owner <> 'demo' ORDER BY id"
            )
            truth = {
                r["event_id"]: r["is_laundering"]
                for r in self._all(
                    "SELECT event_id, is_laundering FROM truth WHERE event_id = ANY(%s)",
                    (sorted({r["event_id"] for r in rows}),),
                )
            }
            cases = W.cases_by_owner(rows, truth)
            reviews = self._one("SELECT count(*) AS n FROM case_actions WHERE role = 'reviewer'")[
                "n"
            ]
            decided = {c["event_id"] for c in cases}
        leans = {
            r["event_id"]: r["typology"] != "none evident"
            for r in self._all(
                "SELECT event_id, report->>'typology' AS typology FROM agent_reports "
                "WHERE model = 'deepseek/deepseek-v4.1-flash' AND event_id = ANY(%s)",
                (sorted(decided),),
            )
        }
        strong = {
            (r["event_id"], r["direction"]): r["strength"] == "strong"
            for r in self._all(
                "SELECT event_id, direction, review->>'strength' AS strength FROM ai_reviews "
                "WHERE model = %s AND event_id = ANY(%s)",
                (TRUSTED_REVIEWER, sorted(decided)),
            )
        }
        for c in cases:
            c["ai_leans_suspicious"] = leans.get(c["event_id"])
            c["ai_strong_against"] = strong.get((c["event_id"], c["decision"]))
        as_of = self._one("SELECT max(event_time) AS t FROM transactions")["t"]
        undecided = self._all(
            "SELECT event_time FROM transactions WHERE rank <= %s AND NOT (event_id = ANY(%s))",
            (k, sorted(decided)),
        )
        closed = [c for c in cases if c["decision"] == "close"]
        qa = W.qa_sample(closed, seed=viewer if scope == "me" else "all")
        keep = ("event_id", "code", "ok") + (("reason",) if scope == "me" else ())
        return {
            "scope": scope,
            "as_of": as_of,
            **W.metrics(cases, reviews),
            "backlog": W.backlog(undecided, as_of),
            "qa": [{f: c.get(f) for f in keep} for c in qa],
        }

    def next_undecided(self, viewer: str, after: int, k: int) -> dict | None:
        """The next alert in the top k (by rank, after `after`) the viewer has not decided."""
        return self._one(
            "SELECT event_id, rank FROM transactions WHERE rank > %s AND rank <= %s "
            "AND event_id NOT IN (SELECT event_id FROM case_actions WHERE case_owner = %s "
            "AND role = 'investigator') ORDER BY rank LIMIT 1",
            (after, k, viewer),
        )


def to_json(obj) -> str:
    return json.dumps(obj, default=str)
