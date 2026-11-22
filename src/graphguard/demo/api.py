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
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field, ValidationError

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


class Verdict(BaseModel):
    verdict: Literal["escalate", "close"]
    note: str = Field(default="", max_length=2000)


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


@router.post("/alerts/{event_id}/verdict", status_code=201)
async def verdict(event_id: int, request: Request, r: Repo):
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "JSON only")
    try:
        body = Verdict.model_validate_json(await request.body())
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_input=False)) from None
    _found(r.alert(event_id))
    r.add_verdict(event_id, body.verdict, body.note)
    return {"saved": True}


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
    web = Path(web_dir) if web_dir else None
    if web is not None and web.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app


app = create_app(web_dir="/srv/web")
