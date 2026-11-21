"""Build the lakehouse from the raw CSV: bronze -> silver (+ sealed) -> gold.

    just lakehouse-build

Writes new snapshots of every table and prints their ids. It reads the CSV,
which contains the test window, exactly like the CSV path always has; the test
window goes to `sealed` and nowhere else.
"""

from __future__ import annotations

import sys
import time

from graphguard.config import REPO_ROOT, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.dataset import frozen_boundaries
from graphguard.lakehouse.catalog import open_catalog
from graphguard.lakehouse.lineage_events import lineage_run
from graphguard.lakehouse.tables import (
    GOLD_FEATURES,
    MAINTAINED_TABLES,
    current_snapshot_ids,
    expire_old_snapshots,
    remove_orphan_files,
    write_bronze,
    write_gold_edges,
    write_gold_features,
    write_gold_labels,
    write_gold_recent_sends,
    write_silver,
)

# Snapshots kept per table after a build. Enough to time-travel back a few
# builds; small enough that old Parquet files do not pile up on a 25GB budget.
KEEP_SNAPSHOTS = 5


def main() -> int:
    with lineage_run("lakehouse-build") as run:
        run.read(str(TRANSACTIONS_FILE.relative_to(REPO_ROOT)), None, namespace="file://graphguard")
        _build()
        # Every table the build wrote, with the snapshot it ended on -- listed from
        # the catalog, so the test window's table is recorded without being named here.
        catalog = open_catalog("builder")
        for ns in catalog.list_namespaces():
            for ident in catalog.list_tables(ns):
                snap = catalog.load_table(ident).current_snapshot()
                run.wrote(".".join(ident), snap.snapshot_id if snap else None)
    return 0


def _build() -> None:
    t0 = time.time()
    boundaries = frozen_boundaries()
    catalog = open_catalog("builder")

    write_bronze(catalog, load_transactions(TRANSACTIONS_FILE))
    print(f"bronze written ({time.time() - t0:.1f}s)", flush=True)
    write_silver(catalog, boundaries)
    print(f"silver + sealed written ({time.time() - t0:.1f}s)", flush=True)
    n = write_gold_features(catalog, as_of=boundaries[0])
    print(f"gold features written: {n:,} accounts ({time.time() - t0:.1f}s)", flush=True)
    n = write_gold_recent_sends(catalog, as_of=boundaries[0])
    print(f"gold recent sends written: {n:,} ({time.time() - t0:.1f}s)", flush=True)
    n = write_gold_edges(catalog, as_of=boundaries[0])
    print(f"gold edges written: {n:,} ({time.time() - t0:.1f}s)", flush=True)
    write_gold_labels(catalog)
    print(f"gold labels written ({time.time() - t0:.1f}s)", flush=True)

    removed = 0
    for name in MAINTAINED_TABLES:
        expire_old_snapshots(catalog, name, keep_last=KEEP_SNAPSHOTS)
        removed += remove_orphan_files(catalog, name)
    print(
        f"maintenance: kept last {KEEP_SNAPSHOTS} snapshots per table, "
        f"removed {removed} orphan files"
    )
    for name, sid in current_snapshot_ids(catalog).items():
        print(f"  {name:32} snapshot {sid}")
    print(
        f"total {time.time() - t0:.1f}s; "
        f"kept last {KEEP_SNAPSHOTS} snapshots ({GOLD_FEATURES} etc.)"
    )


if __name__ == "__main__":
    sys.exit(main())
