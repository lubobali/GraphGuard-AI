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

from ray import serve
from starlette.requests import Request

from graphguard.config import REPO_ROOT
from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.service import ScoringRequest, ScoringService
from graphguard.serving.store import DEFAULT_URL, RedisFeatureStore

BUNDLE_DIR = os.environ.get("GRAPHGUARD_BUNDLE", str(REPO_ROOT / "models" / "production"))
REDIS_URL = os.environ.get("GRAPHGUARD_REDIS_URL", DEFAULT_URL)

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
    def __init__(self, bundle_dir: str = BUNDLE_DIR, redis_url: str = REDIS_URL) -> None:
        # Loaded once per replica at startup, not per request. The bundle
        # carries the feature order and encodings, so a replica cannot drift
        # from the model it is serving.
        self._bundle = ModelBundle.load(bundle_dir)
        self._service = ScoringService(bundle=self._bundle, store=RedisFeatureStore(url=redis_url))

    def _score(self, payload: dict) -> dict:
        missing = [f for f in REQUIRED_FIELDS if f not in payload]
        if missing:
            return {"error": f"missing fields: {missing}"}

        response = self._service.score(
            ScoringRequest(
                from_account=str(payload["from_account"]),
                to_account=str(payload["to_account"]),
                amount_paid=float(payload["amount_paid"]),
                amount_received=float(payload["amount_received"]),
                from_bank=str(payload["from_bank"]),
                to_bank=str(payload["to_bank"]),
                payment_currency=str(payload["payment_currency"]),
                timestamp=dt.datetime.fromisoformat(payload["timestamp"]),
            )
        )
        return {
            "score": response.score,
            "sender_cold": response.sender_cold,
            "receiver_cold": response.receiver_cold,
            "sender_staleness_seconds": response.sender_staleness_seconds,
            "receiver_staleness_seconds": response.receiver_staleness_seconds,
            "model_trained_on": self._bundle.trained_on,
        }

    async def __call__(self, request: Request) -> dict:
        if request.url.path.rstrip("/").endswith("health"):
            return {"status": "ok", "model_trained_on": self._bundle.trained_on}
        return self._score(await request.json())


app = Scorer.bind()
