"""The scoring service: one transaction in, one score out.

Assembles a scoring row from two stored account states plus the transaction's
own fields, and returns the score alongside the two things anyone consuming it
needs to judge whether to trust it:

- **whether either account was cold** -- scored on zeros because nothing is
  known about it yet, which is a different kind of answer from a confident one
- **how stale the stored state was** -- FINDING-008 measured stale features
  costing 83% of PR-AUC, so staleness is reported per request rather than
  assumed away
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from graphguard.serving.model_bundle import ModelBundle
from graphguard.serving.online_features import AccountState, to_model_row
from graphguard.serving.store import FeatureStore

UNSEEN_CATEGORY = -1


@dataclass(frozen=True)
class ScoringRequest:
    from_account: str
    to_account: str
    amount_paid: float
    amount_received: float
    from_bank: str
    to_bank: str
    payment_currency: str
    timestamp: dt.datetime


@dataclass(frozen=True)
class ScoringResponse:
    score: float
    sender_cold: bool
    receiver_cold: bool
    sender_staleness_seconds: float | None
    receiver_staleness_seconds: float | None


class ScoringService:
    def __init__(self, bundle: ModelBundle, store: FeatureStore) -> None:
        self._bundle = bundle
        self._store = store
        self._currency_map = bundle.category_maps.get("payment_currency", {})

    @staticmethod
    def _staleness(state: AccountState, at: dt.datetime) -> float | None:
        """How old the stored state is: now minus when it was materialised.

        Not `at - last_seen`, which is how long since the account last did
        anything. That is account recency, a different question, and reporting
        it as staleness would have monitoring watch the wrong number.
        """
        if state.is_cold or state.materialised_at is None:
            return None
        return (at - state.materialised_at).total_seconds()

    def score(self, request: ScoringRequest) -> ScoringResponse:
        # One round trip for both accounts, not two. Inside a 50ms budget the
        # difference between one network hop and two is not negligible.
        fetched = self._store.get_many([request.from_account, request.to_account])

        sender = fetched[request.from_account] or AccountState.cold(request.from_account)
        receiver = fetched[request.to_account] or AccountState.cold(request.to_account)

        row = to_model_row(
            sender=sender,
            receiver=receiver,
            timestamp=request.timestamp,
            amount_paid=request.amount_paid,
            amount_received=request.amount_received,
            from_bank=request.from_bank,
            to_bank=request.to_bank,
            payment_currency_code=self._currency_map.get(request.payment_currency, UNSEEN_CATEGORY),
        )

        return ScoringResponse(
            score=self._bundle.score_one(row),
            sender_cold=sender.is_cold,
            receiver_cold=receiver.is_cold,
            sender_staleness_seconds=self._staleness(sender, request.timestamp),
            receiver_staleness_seconds=self._staleness(receiver, request.timestamp),
        )
