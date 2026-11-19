"""How the scorer treats accounts it has never seen, measured on validation (S5.5).

By the serving definition the store holds account states as of `train_end`; a side of a
validation transaction is *cold* when its account has no history before then. This asks
what the zero-feature fallback does to those transactions: how often they launder, what
the model scores them, and whether cold launderers still reach the top-k queue.

Validation only (contract rule 4). Every transaction with a cold side is scored, plus a
seeded sample of warm ones whose counts are scaled back up to the full window.

    python -m graphguard.analysis.cold_accounts
"""

from __future__ import annotations

import json
import sys

import numpy as np
import polars as pl

K = 5000  # the queue size every model in this project is judged at (precision@k)
WARM_SAMPLE = 100_000
SEED = 42


def group_of(sender_cold: bool, receiver_cold: bool) -> str:
    if sender_cold and receiver_cold:
        return "both cold"
    if sender_cold:
        return "sender cold"
    if receiver_cold:
        return "receiver cold"
    return "warm"


def queue_recall(scores: np.ndarray, labels: np.ndarray, weights: np.ndarray,
                 groups: np.ndarray, k: int = K) -> dict:  # fmt: skip
    """Share of each group's launderers that rank inside the top-k of the whole window
    (weights scale the warm sample back up). Pure, tested."""
    order = np.argsort(-scores, kind="stable")
    cum = np.cumsum(weights[order])
    in_queue = np.zeros(len(scores), dtype=bool)
    in_queue[order[cum <= k]] = True
    out = {}
    for g in np.unique(groups):
        m = (groups == g) & (labels == 1)
        total = weights[m].sum()
        out[str(g)] = round(float(weights[m & in_queue].sum() / total), 4) if total else None
    return out


def measure() -> dict:
    import datetime as dt

    from graphguard.config import TRANSACTIONS_FILE
    from graphguard.data.loader import load_transactions
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.tables import read_states_frame
    from graphguard.serving.model_bundle import ModelBundle
    from graphguard.serving.online_features import states_from_frame
    from graphguard.serving.service import ScoringRequest, ScoringService
    from graphguard.serving.store import InMemoryFeatureStore

    train_end, val_end = frozen_boundaries()
    # Exactly what `just store-load` puts in Redis.
    states = states_from_frame(read_states_frame(open_catalog("reader"), train_end), train_end)
    store = InMemoryFeatureStore()
    store.put_many(list(states.values()))
    known = set(states)

    val = (load_transactions(TRANSACTIONS_FILE)
           .filter((pl.col("timestamp") >= train_end) & (pl.col("timestamp") < val_end))
           .collect())  # fmt: skip
    val = val.with_columns(
        pl.col("from_account").is_in(list(known)).not_().alias("sender_cold"),
        pl.col("to_account").is_in(list(known)).not_().alias("receiver_cold"),
    )
    val = val.with_columns(
        pl.struct("sender_cold", "receiver_cold")
        .map_elements(
            lambda s: group_of(s["sender_cold"], s["receiver_cold"]), return_dtype=pl.String
        )
        .alias("group")
    )
    counts = (val.group_by("group")
              .agg(pl.len().alias("n"), pl.col("is_laundering").sum().alias("laundering"))
              .with_columns((pl.col("n") / val.height).alias("share"),
                            (pl.col("laundering") / pl.col("n")).alias("laundering_rate"))
              .sort("group"))  # fmt: skip

    cold = val.filter(pl.col("group") != "warm")
    warm_all = val.filter(pl.col("group") == "warm")
    warm = warm_all.sample(n=min(WARM_SAMPLE, warm_all.height), seed=SEED)
    sample = pl.concat([cold, warm])
    weights = np.where(sample["group"].to_numpy() == "warm", warm_all.height / warm.height, 1.0)

    service = ScoringService(bundle=ModelBundle.load("models/production"), store=store)

    def request(r: dict) -> ScoringRequest:
        return ScoringRequest(
            r["from_account"], r["to_account"], float(r["amount_paid"]),
            float(r["amount_received"]), str(r["from_bank"]), str(r["to_bank"]),
            r["payment_currency"], r["timestamp"],
        )  # fmt: skip

    scores = np.array([service.score(request(r)).score for r in sample.iter_rows(named=True)])
    groups = sample["group"].to_numpy()
    labels = sample["is_laundering"].to_numpy()

    def median_or_none(mask: np.ndarray) -> float | None:
        return round(float(np.median(scores[mask])), 6) if mask.any() else None

    score_stats = {
        str(g): {
            "median_score": median_or_none(groups == g),
            "median_score_launderers": median_or_none((groups == g) & (labels == 1)),
        }
        for g in np.unique(groups)
    }
    return {
        "window": [train_end.isoformat(), val_end.isoformat()],
        "measured_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "validation_transactions": val.height,
        "groups": counts.to_dicts(),
        "scores": score_stats,
        f"recall_in_top_{K}": queue_recall(scores, labels, weights, groups),
    }


def main(argv: list[str]) -> int:
    out = measure()
    print(json.dumps(out, indent=1))
    if len(argv) > 1:
        with open(argv[1], "w") as f:
            json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
