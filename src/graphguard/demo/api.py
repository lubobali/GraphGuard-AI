"""The investigator demo's read API (S7.6).

    uvicorn graphguard.demo.api:app --port 8000      # in the graphguard-demo-api container

Reads as `demo_reader`; one write (the verdict) as `demo_writer`. Private by default
(127.0.0.1 only, ADR 0008 D4). Every response carries strict security headers; reads and
writes are rate limited per client; at most a few live streams are open at once; writes
accept JSON only, so a cross-site form cannot post one.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field, ValidationError

from graphguard.demo import workflow as W
from graphguard.demo.queries import BANNER, k_for, to_json

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'; object-src 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}
READ_RATE, READ_BURST = 20.0, 40.0
WRITE_RATE, WRITE_BURST = 1.0, 5.0
MAX_LIVE = 4
LIVE_PER_SECOND = 4


class RateLimiter:
    """Token bucket per (client, kind)."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.state: dict[tuple, tuple[float, float]] = {}
        self.lock = threading.Lock()

    def allow(self, client: str, kind: str, rate: float, burst: float) -> bool:
        now = self.clock()
        with self.lock:
            tokens, last = self.state.get((client, kind), (burst, now))
            tokens = min(burst, tokens + (now - last) * rate)
            ok = tokens >= 1.0
            self.state[(client, kind)] = (tokens - 1.0 if ok else tokens, now)
            return ok


UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
Visitor = Annotated[str, Query(pattern=UUID)]


class Action(BaseModel):
    """One step of the case workflow (S7.15); `demo/workflow.py` decides if it is allowed."""

    visitor: str = Field(pattern=UUID)
    owner: str | None = Field(default=None, pattern=UUID[:-1] + "|^demo$")
    role: Literal["investigator", "reviewer"]
    action: Literal["escalate", "close", "approve", "send_back"]
    code: Literal["explained", "duplicate", "insufficient", "other"] | None = None
    reason: str = Field(default="", max_length=W.MAX_REASON)


def _repo(request: Request):
    st = request.app.state
    if st.repo is None:
        from graphguard.demo.queries import PgRepo

        st.repo = PgRepo()
    return st.repo


Repo = Annotated[Any, Depends(_repo)]
PerDay = Annotated[float, Query(gt=0, le=10_000)]
router = APIRouter(prefix="/api")


def _ok(data) -> Response:
    return Response(to_json(data), media_type="application/json")


def _found(value, what: str = "no such transaction in the demo window"):
    if value is None:
        raise HTTPException(404, what)
    return value


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta")
def meta(r: Repo):
    return _ok(r.meta())


@router.get("/capacity")
def capacity(r: Repo, per_day: PerDay = 100):
    k = k_for(per_day)
    return _ok({"per_day": per_day, "k": k, "rankings": r.capacity(k)})


@router.get("/capacity/curve")
def curve(r: Repo):
    return _ok(r.capacity_curve())


@router.get("/queue")
def queue(r: Repo, per_day: PerDay = 100, page: Annotated[int, Query(ge=1, le=1_000)] = 1):
    return _ok(r.queue(k_for(per_day), page))


@router.get("/alerts/{event_id}")
def alert(event_id: int, r: Repo):
    return _ok(_found(r.alert(event_id)))


@router.get("/alerts/{event_id}/answer")
def answer(event_id: int, r: Repo):
    return _ok(_found(r.answer(event_id)))


@router.get("/performance")
def performance(r: Repo, per_day: PerDay = 100):
    return _ok(r.performance(k_for(per_day)))


def _history(r, event_id: int, owner: str, viewer: str) -> list[dict]:
    seed = W.demo_history(event_id) if owner == W.DEMO else []
    return seed + W.visible(r.case_rows(event_id), owner, viewer)


def _public(history: list[dict], viewer: str) -> list[dict]:
    """A case's rows for the page: "you" or "Sam", never another visitor's id."""
    who = {viewer: "you", W.DEMO: "Sam"}
    return [{"who": who.get(h["actor"], "someone"), "role": h["role"], "action": h["action"],
             "code": h["code"], "reason": h["reason"], "at": h["at"]} for h in history]  # fmt: skip


def _case(history: list[dict], viewer: str) -> dict:
    return {**W.case_state(history), "history": _public(history, viewer)}


@router.get("/alerts/{event_id}/case")
def case(event_id: int, visitor: Visitor, r: Repo):
    _found(r.alert(event_id))
    sam = W.demo_history(event_id)
    return _ok({
        "mine": _case(_history(r, event_id, visitor, visitor), visitor),
        "sam": _case(_history(r, event_id, W.DEMO, visitor), visitor) if sam else None,
    })  # fmt: skip


@router.post("/alerts/{event_id}/actions")
async def act(event_id: int, request: Request, r: Repo):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "JSON only")
    try:
        a = Action.model_validate_json(await request.body())
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_input=False)) from None
    _found(r.alert(event_id))
    owner = a.owner or a.visitor
    history = _history(r, event_id, owner, a.visitor)
    if W.is_repeat(history, a.visitor, a.action, a.code, a.reason):
        return _ok({"saved": False, "repeat": True, "case": _case(history, a.visitor)})
    why = W.check(history, a.visitor, owner, a.role, a.action, a.code, a.reason)
    if why:
        raise HTTPException(409, why)
    r.add_action(event_id, owner, a.visitor, a.role, a.action, a.code, a.reason)
    history = _history(r, event_id, owner, a.visitor)
    body = {"saved": True, "repeat": False, "case": _case(history, a.visitor)}
    return Response(to_json(body), media_type="application/json", status_code=201)


@router.get("/decisions")
def decisions(visitor: Visitor, r: Repo):
    cases = r.decisions(visitor)
    mine = [c for c in cases if c["owner"] == visitor]
    return _ok({"cases": cases, "score": W.score(mine)})


@router.get("/manager")
def manager(visitor: Visitor, r: Repo, scope: Literal["me", "all"] = "me", per_day: PerDay = 100):
    return _ok(r.manager(visitor, scope, k_for(per_day)))


@router.get("/next")
def next_alert(visitor: Visitor, r: Repo, after: Annotated[int, Query(ge=0)] = 0,
               per_day: PerDay = 100):  # fmt: skip
    return _ok(r.next_undecided(visitor, after, k_for(per_day)) or {"event_id": None})


def _take_live_slot(state) -> bool:
    with state.live_lock:
        if state.live_open["n"] >= MAX_LIVE:
            return False
        state.live_open["n"] += 1
        return True


@router.get("/live", response_class=EventSourceResponse)
async def live(
    request: Request, r: Repo, start: Annotated[str, Query(max_length=19)] = "2022-09-06 13:34:00"
):
    # The slot is taken inside the stream, so it is always given back (finally); a full
    # server answers with one "busy" event and closes rather than failing mid-stream.
    st = request.app.state
    if not _take_live_slot(st):
        yield ServerSentEvent(raw_data='{"detail": "too many live streams"}', event="busy")
        return
    try:
        cursor = (start, -1)
        for _ in range(600):  # ~2.5 minutes per connection, then the client reconnects
            rows = await asyncio.to_thread(r.live, cursor, LIVE_PER_SECOND)
            if not rows:
                break
            for row in rows:
                yield ServerSentEvent(raw_data=to_json(row), event="transaction")
            cursor = (str(rows[-1]["event_time"]), rows[-1]["event_id"])
            await asyncio.sleep(1.0)
    finally:
        with st.live_lock:
            st.live_open["n"] -= 1


def create_app(repo=None, limiter: RateLimiter | None = None, web_dir: str | None = None):
    app = FastAPI(title="GraphGuard investigator demo", docs_url=None, redoc_url=None,
                  openapi_url=None)  # fmt: skip
    app.state.repo = repo
    app.state.limiter = limiter or RateLimiter()
    app.state.live_open = {"n": 0}
    app.state.live_lock = threading.Lock()
    app.state.banner = BANNER

    @app.middleware("http")
    async def guard(request: Request, call_next):
        client = request.client.host if request.client else "?"
        write = request.method not in ("GET", "HEAD")
        rate, burst = (WRITE_RATE, WRITE_BURST) if write else (READ_RATE, READ_BURST)
        if request.url.path.startswith("/api/") and not request.app.state.limiter.allow(
            client, "write" if write else "read", rate, burst
        ):
            response: Response = JSONResponse({"detail": "too many requests"}, status_code=429)
        else:
            response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response

    app.include_router(router)
    if web_dir:
        from fastapi.staticfiles import StaticFiles

        # check_dir=False: `next build` deletes and recreates out/, so the folder may appear
        # (or be replaced) after start-up; the parent web/ is what the container mounts.
        app.mount("/", StaticFiles(directory=web_dir, html=True, check_dir=False), name="web")
    return app


app = create_app(web_dir="/srv/webroot/out")
