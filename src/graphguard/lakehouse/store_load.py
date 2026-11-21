"""Fill the online store from the gold table -- without retraining (S5.6a).

Before this, the only way to refill Redis was `just build-artifacts`, which
retrains the model to do it. Now the model and the store are separate:
training writes the bundle; this loads the state the bundle expects.

Reload is in place: every current account is overwritten, then accounts that no
longer exist are removed. The store is never empty mid-reload, so no request
ever sees every account as cold.

    just store-load
"""

from __future__ import annotations

import datetime as dt
import sys
import time

from pyiceberg.catalog import Catalog

from graphguard.lakehouse.tables import read_states_frame
from graphguard.serving.online_features import states_from_frame


def load_store_from_gold(catalog: Catalog, store, as_of: dt.datetime) -> int:
    """Overwrite the store with gold's states as of `as_of`. Returns accounts loaded."""
    frame = read_states_frame(catalog, as_of)
    if frame.height == 0:
        # An empty load would leave every account cold, which looks like
        # "every customer is new" rather than like an error. Refuse.
        raise ValueError(f"no gold rows for as_of={as_of.isoformat()}; refusing to load")
    states = states_from_frame(frame, as_of)
    store.put_many(list(states.values()))
    store.prune_except(set(states))
    # Last: "the store is completely loaded" (S5.5). After a Redis restart the marker is
    # gone, so the scorer answers 503 until this line runs -- never a cold score.
    store.set_marker({
        "as_of": as_of.isoformat(),
        "accounts": len(states),
        "loaded_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    })  # fmt: skip
    return len(states)


def seed_stream_from_gold(catalog: Catalog, stream_store, as_of: dt.datetime,
                          accounts: list[str]) -> dict[str, int]:  # fmt: skip
    """The stream's seed (S6.3): 24 h send windows and seen pairs as of `as_of`, from gold.
    A reload is a reset: whatever the stream applied since is dropped with it."""
    from graphguard.lakehouse.tables import read_edges, read_recent_sends
    from graphguard.stream.updater import seed_stream

    recent, edges = read_recent_sends(catalog, as_of), read_edges(catalog, as_of)
    if edges.height == 0:
        raise ValueError(f"no gold edges for as_of={as_of.isoformat()}; refusing to seed")
    seed_stream(stream_store, accounts, recent, edges)
    return {"window_sends": recent.height, "edges": edges.height}


def main() -> int:
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.lineage_events import lineage_run
    from graphguard.lakehouse.tables import GOLD_EDGES, GOLD_FEATURES, GOLD_RECENT_SENDS
    from graphguard.serving.store import REDIS_BASE, RedisFeatureStore
    from graphguard.stream.updater import RedisStore

    train_end, _ = frozen_boundaries()
    t0 = time.time()
    catalog = open_catalog("reader")
    with lineage_run("store-load") as run:
        snap = catalog.load_table(GOLD_FEATURES).current_snapshot()
        store = RedisFeatureStore()
        n = load_store_from_gold(catalog, store, as_of=train_end)
        run.read(GOLD_FEATURES, snap.snapshot_id if snap else None)
        run.wrote("db0/gg:acct", None, namespace=REDIS_BASE)
        accounts = sorted(read_states_frame(catalog, train_end)["account"].to_list())
        seeded = seed_stream_from_gold(catalog, RedisStore(store.client), train_end, accounts)
        run.read(GOLD_RECENT_SENDS, None)
        run.read(GOLD_EDGES, None)
        run.wrote("db0/gg:edge+win", None, namespace=REDIS_BASE)
    print(
        f"online store loaded from gold: {n:,} accounts as of {train_end}; stream seed "
        f"{seeded['window_sends']:,} recent sends, {seeded['edges']:,} pairs "
        f"({time.time() - t0:.1f}s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
