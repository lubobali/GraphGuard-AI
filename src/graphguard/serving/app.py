"""Ray Serve deployment: the scoring service as an HTTP endpoint.

Deliberately thin. All the logic -- feature assembly, cold accounts, staleness,
the model -- lives in `ScoringService` and is unit tested there. This layer only
translates HTTP to that call and back, because logic that lives inside a server
class is logic that can only be tested by starting a server.

Resources are capped because this box runs LuBot production alongside it.
"""

from __future__ import annotations

import datetime as dt
import os
import time

import redis
from ray import serve
from starlette.requests import Request
from starlette.responses import JSONResponse

from graphguard.config import REPO_ROOT
from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.service import ScoringRequest, ScoringService
from graphguard.serving.store import STORE_DOWN, RedisFeatureStore

BUNDLE_DIR = os.environ.get("GRAPHGUARD_BUNDLE", str(REPO_ROOT / "models" / "production"))
# In the pod the URL (with the scorer's credentials) comes from a Kubernetes Secret.
REDIS_URL = os.environ.get("GRAPHGUARD_REDIS_URL")

REQUIRED_FIELDS = (
    "from_account",
    "to_account",
    "amount_paid",
    "amount_received",
    "from_bank",
    "to_bank",
    "payment_currency",
    "timestamp",
)


@serve.deployment(
    num_replicas=2,
    ray_actor_options={"num_cpus": 0.5},
    max_ongoing_requests=32,
)
class Scorer:
    def __init__(self, bundle_dir: str = BUNDLE_DIR, redis_url: str | None = REDIS_URL) -> None:
        # Loaded once per replica at startup, not per request. The bundle
        # carries the feature order and encodings, so a replica cannot drift
        # from the model it is serving.
        self._bundle = ModelBundle.load(bundle_dir)
        self._service = ScoringService(
            bundle=self._bundle, store=RedisFeatureStore(url=redis_url, user="scorer")
        )

    # --- readiness (S5.5): a broken or empty store must never look like a new account ---
    READY_TTL_S = 1.0  # one Redis round trip per second at most, not per request

    def _readiness(self) -> str | None:
        now = time.monotonic()
        cached = getattr(self, "_ready_cache", None)
        if cached and now - cached[0] < self.READY_TTL_S:
            return cached[1]
        why = self._service.store.readiness()
        self._ready_cache = (now, why)
        return why

    @staticmethod
    def _parse(payload: dict) -> ScoringRequest:
        """The request, or ValueError naming what is wrong (-> 422)."""
        missing = [f for f in REQUIRED_FIELDS if f not in payload]
        if missing:
            raise ValueError(f"missing fields: {missing}")
        try:
            return ScoringRequest(
                from_account=str(payload["from_account"]),
                to_account=str(payload["to_account"]),
                amount_paid=float(payload["amount_paid"]),
                amount_received=float(payload["amount_received"]),
                from_bank=str(payload["from_bank"]),
                to_bank=str(payload["to_bank"]),
                payment_currency=str(payload["payment_currency"]),
                timestamp=dt.datetime.fromisoformat(payload["timestamp"]),
            )
        except (TypeError, ValueError) as e:
            raise ValueError(f"malformed field: {e}") from None

    def _score(self, payload: dict) -> JSONResponse | dict:
        try:
            request = self._parse(payload)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=422)
        if why := self._readiness():
            return JSONResponse({"error": why}, status_code=503)
        try:
            response = self._service.score(request)
        except (redis.ConnectionError, redis.TimeoutError):
            self._ready_cache = (time.monotonic(), STORE_DOWN)
            return JSONResponse({"error": STORE_DOWN}, status_code=503)
        return {
            "score": response.score,
            "sender_cold": response.sender_cold,
            "receiver_cold": response.receiver_cold,
            "cold_policy": response.cold_policy,
            "sender_staleness_seconds": response.sender_staleness_seconds,
            "receiver_staleness_seconds": response.receiver_staleness_seconds,
            "model_trained_on": self._bundle.trained_on,
        }

    def _health(self) -> JSONResponse:
        why = self._readiness()
        body = {"status": "ok" if why is None else "unavailable",
                "model_trained_on": self._bundle.trained_on}  # fmt: skip
        if why:
            body["reason"] = why
        return JSONResponse(body, status_code=200 if why is None else 503)

    async def __call__(self, request: Request) -> JSONResponse | dict:
        if request.url.path.rstrip("/").endswith("health"):
            return self._health()
        try:
            payload = await request.json()
        except ValueError:
            return JSONResponse({"error": "body is not JSON"}, status_code=422)
        if not isinstance(payload, dict):
            return JSONResponse({"error": "body must be a JSON object"}, status_code=422)
        return self._score(payload)


app = Scorer.bind()
