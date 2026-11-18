"""Can Feast's point-in-time join build training's history features? (S5.6e)

Training counts "payments this account sent before this one" in (timestamp,
source_row) order: of two payments in the same minute, the second counts the
first (FINDING-010; 9.4% of transactions tie on the minute). Feast joins on the
event timestamp alone, breaking ties with a `created` timestamp.

This is a characterisation test: it records what Feast returns, so the decision in
ADR 0004 rests on behaviour, not on reading docs. If a Feast upgrade changes the
behaviour, this test fails and the decision must be revisited.
"""

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest
from feast import Entity, FeatureStore, FeatureView, Field, FileSource, ValueType
from feast.repo_config import RepoConfig
from feast.types import Int64

T = dt.datetime(2022, 9, 2, 10, 0, tzinfo=dt.UTC)
LATER = T + dt.timedelta(minutes=5)

# Three payments from account A. A1 and A2 share a minute; A1 came first in the file.
PAYMENTS = [("A1", T, 0), ("A2", T, 1), ("A3", LATER, 2)]  # (id, timestamp, source_row)
TRAINING_TRUTH = {"A1": 0, "A2": 1, "A3": 2}  # payments A sent strictly before each one


def _store(tmp_path: Path, rows: pd.DataFrame) -> tuple[FeatureStore, list]:
    rows.to_parquet(tmp_path / "states.parquet")
    src = FileSource(
        path=str(tmp_path / "states.parquet"),
        timestamp_field="event_ts",
        created_timestamp_column="created_ts",
    )
    acct = Entity(name="account", join_keys=["account"], value_type=ValueType.STRING)
    fv = FeatureView(
        name="history",
        entities=[acct],
        ttl=dt.timedelta(days=30),
        schema=[Field(name="n_sent_before", dtype=Int64)],
        source=src,
    )
    cfg = RepoConfig(
        project="tie_check",
        provider="local",
        registry=str(tmp_path / "registry.db"),
        online_store={"type": "sqlite", "path": str(tmp_path / "online.db")},
        offline_store={"type": "duckdb"},
        entity_key_serialization_version=3,
    )
    store = FeatureStore(config=cfg)
    store.apply([acct, fv])
    return store, ["history:n_sent_before"]


def _retrieve(store, refs) -> dict[str, int]:
    entity_df = pd.DataFrame(
        {
            "account": ["A"] * 3,
            "event_timestamp": [ts for _, ts, _ in PAYMENTS],
            "payment": [p for p, _, _ in PAYMENTS],
        }
    )
    out = store.get_historical_features(entity_df=entity_df, features=refs).to_df()
    return dict(zip(out["payment"], out["n_sent_before"].astype(int), strict=True))


def test_states_written_before_each_payment_cannot_separate_a_same_minute_tie(tmp_path):
    # The natural modelling: one row per payment holding the count *before* it,
    # stamped at the payment's time, tie-broken by source order via `created_ts`.
    rows = pd.DataFrame(
        {
            "account": ["A"] * 3,
            "n_sent_before": [0, 1, 2],
            "event_ts": [ts for _, ts, _ in PAYMENTS],
            "created_ts": [T + dt.timedelta(microseconds=r) for _, _, r in PAYMENTS],
        }
    )
    got = _retrieve(*_store(tmp_path, rows))
    assert got != TRAINING_TRUTH
    # A1 receives A2's row: the same-minute payment that came AFTER it in the file.
    assert got["A1"] == 1 and got["A2"] == 1 and got["A3"] == 2


def test_states_written_after_each_payment_let_a_payment_see_itself(tmp_path):
    # The other natural modelling: the running count *including* the payment.
    rows = pd.DataFrame(
        {
            "account": ["A"] * 3,
            "n_sent_before": [1, 2, 3],
            "event_ts": [ts for _, ts, _ in PAYMENTS],
            "created_ts": [T + dt.timedelta(microseconds=r) for _, _, r in PAYMENTS],
        }
    )
    got = _retrieve(*_store(tmp_path, rows))
    assert got != TRAINING_TRUTH
    assert got["A3"] == 3  # counts itself: leakage, contract rule 3


@pytest.mark.parametrize("truth", [TRAINING_TRUTH])
def test_the_fixture_is_what_training_would_compute(truth):
    # Guard on the test itself: payments strictly before, in (timestamp, source_row) order.
    order = sorted(PAYMENTS, key=lambda p: (p[1], p[2]))
    assert {p: i for i, (p, _, _) in enumerate(order)} == truth
