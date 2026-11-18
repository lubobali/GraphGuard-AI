"""GraphGuard's account features, declared for Feast (S5.6e).

One entity (`account`) and one feature view over `gold.account_features_asof` -- the
account states the scorer uses, as of the end of the training window. Read through
Lakekeeper as the `reader` identity: Feast sends a Dex token (env `GG_FEAST_TOKEN`,
set by `run.py`) and Lakekeeper vends a read-only key for that one table.

These are the same nine columns `graphguard.serving.online_features.STATE_COLUMNS`
holds; `run.py` checks Feast's values against ours, account by account.
"""

from datetime import timedelta

from feast import Entity, FeatureView, Field, ValueType
from feast.infra.data_sources.contrib.iceberg_catalog.iceberg_source import IcebergSource
from feast.types import Float64, Int64, String, UnixTimestamp

account = Entity(
    name="account",
    join_keys=["account"],
    value_type=ValueType.STRING,
    description="A bank account id",
)

gold_account_states = IcebergSource(
    name="gold_account_features_asof",
    catalog_type="rest",
    endpoint="http://127.0.0.1:8181/catalog",
    warehouse="graphguard",
    namespace="gold",
    table="account_features_asof",
    timestamp_field="as_of",
    token_env_var="GG_FEAST_TOKEN",
)

account_state = FeatureView(
    name="account_state",
    entities=[account],
    # The states are a snapshot at `as_of`; they do not expire by age here. (What
    # staleness means for serving is FINDING-008's subject, not Feast's TTL.)
    ttl=timedelta(days=0),
    # Every column declared, so Feast never has to infer types. (Its inference uses
    # a small REST client that sends the warehouse *name* where Lakekeeper expects
    # the warehouse id -- HTTP 400. Reads go through PyIceberg, which resolves it.)
    schema=[
        Field(name="account", dtype=String),
        Field(name="n_sent", dtype=Int64),
        Field(name="n_received", dtype=Int64),
        Field(name="amount_sent", dtype=Float64),
        Field(name="amount_received", dtype=Float64),
        Field(name="distinct_out", dtype=Int64),
        Field(name="distinct_in", dtype=Int64),
        Field(name="sent_last_24h", dtype=Int64),
        Field(name="last_seen", dtype=UnixTimestamp),
        Field(name="last_sent", dtype=UnixTimestamp),
    ],
    source=gold_account_states,
    online=True,
)
