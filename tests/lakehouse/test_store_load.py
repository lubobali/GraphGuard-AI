"""Redis is rebuilt from the gold table, without retraining (S5.6a)."""

import datetime as dt

import polars as pl
import pytest

from graphguard.lakehouse.store_load import load_store_from_gold
from graphguard.lakehouse.tables import write_bronze, write_gold_features, write_silver
from graphguard.serving.store import InMemoryFeatureStore

pytestmark = pytest.mark.unit

AS_OF = dt.datetime(2022, 9, 3)


@pytest.fixture
def cat(cat):  # local and S3, from conftest
    c = cat
    rows = [
        {
            "timestamp": dt.datetime(2022, 9, 1, h),
            "from_bank": "1",
            "from_account": f"S{h}",
            "to_bank": "2",
            "to_account": "R",
            "amount_received": 10.0,
            "receiving_currency": "US Dollar",
            "amount_paid": 10.0,
            "payment_currency": "US Dollar",
            "payment_format": "ACH",
            "is_laundering": 0,
        }
        for h in range(5)
    ]
    write_bronze(c, pl.DataFrame(rows).with_columns(pl.col("timestamp").cast(pl.Datetime("us"))))
    write_silver(
        c,
        boundaries=(dt.datetime(2022, 9, 2), dt.datetime(2022, 9, 4)),
        tail_cutoff=dt.datetime(2022, 9, 11),
    )
    write_gold_features(c, as_of=AS_OF)
    return c


def test_every_account_lands_in_the_store(cat):
    store = InMemoryFeatureStore()
    n = load_store_from_gold(cat, store, as_of=AS_OF)
    assert n == 6  # five senders and one receiver
    assert store.get("R").n_received == 5
    assert store.get("S0").n_sent == 1


def test_loading_replaces_rather_than_adds(cat):
    store = InMemoryFeatureStore()
    load_store_from_gold(cat, store, as_of=AS_OF)
    load_store_from_gold(cat, store, as_of=AS_OF)
    assert len(store._data) == 6


def test_an_as_of_with_no_gold_rows_is_an_error_not_an_empty_store(cat):
    # An empty store looks exactly like "every account is new". Refuse instead.
    with pytest.raises(ValueError, match="no gold rows"):
        load_store_from_gold(cat, InMemoryFeatureStore(), as_of=dt.datetime(2030, 1, 1))
