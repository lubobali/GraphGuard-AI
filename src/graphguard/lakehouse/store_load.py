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
    return len(states)


def main() -> int:
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.serving.store import RedisFeatureStore

    train_end, _ = frozen_boundaries()
    t0 = time.time()
    n = load_store_from_gold(open_catalog(), RedisFeatureStore(), as_of=train_end)
    print(
        f"online store loaded from gold: {n:,} accounts as of {train_end} ({time.time() - t0:.1f}s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
