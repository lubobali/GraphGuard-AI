"""Write and read the lakehouse tables.

    bronze.transactions_raw   the CSV, typed, nothing else changed
    silver.transactions       train + validation windows, tail removed, by day
    sealed.transactions       the test window -- written here, read only by the
                              final report (guarded, see test_set_touch_check)
    gold.account_features_asof  each account's state as of a time
    gold.labels               labels, plus when each became known (Phase 6)

Every table is Iceberg format v2. Writes are whole-table (or whole-`as_of`)
overwrites from deterministic, sorted frames, so a rebuild from the same bronze
gives identical contents, and every write is a new snapshot -- which is what
makes time travel and "which data trained this model" possible.
"""

from __future__ import annotations

import datetime as dt
import tempfile
import uuid
from pathlib import Path

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import fs as pafs
from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import NoSuchTableError
from pyiceberg.expressions import AlwaysTrue, EqualTo
from pyiceberg.io.pyarrow import schema_to_pyarrow
from pyiceberg.table import Table
from pyiceberg.transforms import DayTransform

from graphguard.config import REPO_ROOT
from graphguard.evaluation.split import TAIL_CUTOFF
from graphguard.lakehouse.storage import filesystem, polars_storage_options, to_uri
from graphguard.serving.online_features import (
    AccountState,
    account_states_frame,
    states_from_frame,
)

BRONZE_TX = "bronze.transactions_raw"
SILVER_TX = "silver.transactions"
_SEALED_TX = "sealed.transactions"
GOLD_FEATURES = "gold.account_features_asof"
GOLD_LABELS = "gold.labels"

# Tables whose snapshot ids a training run records. The sealed table is
# deliberately absent: a training run must not even know which version of it exists.
TRACKED_TABLES = (BRONZE_TX, SILVER_TX, GOLD_FEATURES, GOLD_LABELS)

# Every row keeps its position in the source file. The dataset has no
# transaction id, so this is the transaction key -- and it preserves the source
# order, which float sums depend on: the CSV is not time-sorted, and reordering
# it changed 23,384 account sums by 1 ulp (S5.6a). Readers that aggregate sort
# by it first, so the lakehouse path is bit-identical to the CSV path.
SOURCE_ROW = "source_row"
_V2 = {"format-version": "2"}


def _arrow(df: pl.DataFrame) -> pa.Table:
    # Iceberg's string type maps to Arrow `string`; Polars emits `large_string`.
    # Casting here keeps the table schema stable across writers.
    table = df.to_arrow()
    fields = [
        pa.field(f.name, pa.string() if pa.types.is_large_string(f.type) else f.type, f.nullable)
        for f in table.schema
    ]
    return table.cast(pa.schema(fields))


def _table(catalog: Catalog, name: str, df: pl.DataFrame, by_day: str | None = None) -> Table:
    try:
        return catalog.load_table(name)
    except NoSuchTableError:
        table = catalog.create_table(name, schema=_arrow(df.head(0)).schema, properties=_V2)
        if by_day:
            with table.update_spec() as spec:
                spec.add_field(by_day, DayTransform(), f"{by_day}_day")
        return catalog.load_table(name)


def _overwrite(catalog: Catalog, name: str, df: pl.DataFrame, by_day: str | None = None) -> None:
    _table(catalog, name, df, by_day).overwrite(_arrow(df))


def _overwrite_streaming(
    catalog: Catalog, name: str, lf: pl.LazyFrame, by_day: bool, stage: bool = False
) -> None:
    """Replace a big table without holding it in memory.

    Each day is streamed straight to its own Parquet file, then all files are
    registered in ONE transaction together with the delete of the old rows --
    so a reader sees the old table or the new one, never half of each. Writing
    the whole table through Arrow at once peaked at 3.9 GB for 5M rows (S5.6a);
    this keeps one day in memory at a time.
    """
    table = _table(catalog, name, lf.head(0).collect(), by_day="timestamp" if by_day else None)
    fs, batch_dir = filesystem(
        f"{table.location()}/data/batch-{uuid.uuid4().hex}", catalog.properties
    )
    if isinstance(fs, pafs.LocalFileSystem):
        Path(batch_dir).mkdir(parents=True, exist_ok=True)

    # The table's Arrow schema carries each column's Iceberg field id. Files
    # written with it are readable by every Iceberg engine, including Polars'
    # native reader, which refuses files without field ids.
    arrow_schema = schema_to_pyarrow(table.schema())

    # A CSV source is staged once with the streaming engine: cutting each day
    # from the CSV re-parses the whole file per day (measured 1.6 GB peak vs
    # 1.06 GB staged). Iceberg sources are not staged -- they already prune to
    # the day's files, and staging them measured worse (1.2 GB vs 1.0 GB).
    # Staging is always local scratch, even when the warehouse is on S3.
    tmp = tempfile.TemporaryDirectory(dir=_scratch_dir())
    staging = Path(tmp.name) / "staging.parquet"
    if stage:
        lf.sink_parquet(staging)
        lf = pl.scan_parquet(staging)

    day = pl.col("timestamp").dt.date()
    days = lf.select(day.unique().sort()).collect(engine="streaming")["timestamp"].to_list()
    paths = []
    try:
        for d in days:
            path = f"{batch_dir}/{d.isoformat()}.parquet"
            batch = lf.filter(day == d).sort(SOURCE_ROW).collect(engine="streaming")
            with fs.open_output_stream(path) as out:
                pq.write_table(batch.to_arrow().select(arrow_schema.names).cast(arrow_schema), out)
            paths.append(to_uri(fs, path))
    finally:
        tmp.cleanup()

    with table.transaction() as tx:
        if table.current_snapshot() is not None:
            tx.delete(AlwaysTrue())
        if paths:
            tx.add_files(paths)


def _scratch_dir() -> str:
    d = REPO_ROOT / "lakehouse" / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def _scan(catalog: Catalog, name: str, snapshot_id: int | None = None) -> pl.LazyFrame:
    table = catalog.load_table(name)
    return pl.scan_iceberg(
        table,
        snapshot_id=snapshot_id,
        storage_options=polars_storage_options(catalog.properties),
    )


def scan_in_source_order(
    catalog: Catalog, name: str, snapshot_id: int | None = None
) -> pl.LazyFrame:
    """A transactions table in the order the rows arrived, without the key column.

    Use this wherever rows are aggregated, so results match the CSV path exactly.
    """
    return _scan(catalog, name, snapshot_id).sort(SOURCE_ROW).drop(SOURCE_ROW)


# --- writers ------------------------------------------------------------------


def write_bronze(catalog: Catalog, raw: pl.DataFrame | pl.LazyFrame) -> None:
    """The CSV as it is, typed. Nothing filtered: bronze is the record of what arrived."""
    lf = raw.lazy() if isinstance(raw, pl.DataFrame) else raw
    lf = lf.with_row_index(SOURCE_ROW).with_columns(pl.col(SOURCE_ROW).cast(pl.Int64))
    _overwrite_streaming(catalog, BRONZE_TX, lf, by_day=True, stage=True)


def write_silver(
    catalog: Catalog,
    boundaries: tuple[dt.datetime, dt.datetime],
    tail_cutoff: dt.datetime = TAIL_CUTOFF,
) -> None:
    """Train + validation windows to silver; the test window to sealed only.

    The post-Sep-10 simulator tail is dropped (FINDING-001), exactly as
    `truncate_tail` does on the CSV path.
    """
    _, val_end = boundaries
    bronze = _scan(catalog, BRONZE_TX).filter(pl.col("timestamp") < tail_cutoff)
    _overwrite_streaming(catalog, SILVER_TX, bronze.filter(pl.col("timestamp") < val_end), True)
    _overwrite_streaming(catalog, _SEALED_TX, bronze.filter(pl.col("timestamp") >= val_end), True)


def write_gold_features(catalog: Catalog, as_of: dt.datetime) -> int:
    """Every account's state as of `as_of`, from silver, by the serving definition.

    Replaces only the rows for this `as_of`; other `as_of` values are kept.
    Returns the number of accounts written.
    """
    frame = account_states_frame(scan_in_source_order(catalog, SILVER_TX), as_of)
    frame = frame.with_columns(pl.lit(as_of).cast(pl.Datetime("us")).alias("as_of")).select(
        "account", "as_of", *[c for c in frame.columns if c != "account"]
    )
    table = _table(catalog, GOLD_FEATURES, frame)
    if table.current_snapshot() is None:
        table.append(_arrow(frame))  # first write: nothing to replace
    else:
        table.overwrite(_arrow(frame), overwrite_filter=EqualTo("as_of", as_of.isoformat()))
    return frame.height


def write_gold_labels(catalog: Catalog) -> None:
    labels = (
        _scan(catalog, SILVER_TX)
        .select(
            SOURCE_ROW, "timestamp", "from_account", "to_account", "amount_paid", "is_laundering"
        )
        .with_columns(pl.lit(None, dtype=pl.Datetime("us")).alias("label_known_at"))
    )
    _overwrite_streaming(catalog, GOLD_LABELS, labels, by_day=False)


# --- readers ------------------------------------------------------------------


def _states(catalog: Catalog, as_of: dt.datetime, snapshot_id: int | None) -> pl.DataFrame:
    return (
        _scan(catalog, GOLD_FEATURES, snapshot_id)
        .filter(pl.col("as_of") == as_of)
        .drop("as_of")
        .sort("account")
        .collect()
    )


def read_account_states(catalog: Catalog, as_of: dt.datetime) -> dict[str, AccountState]:
    return states_from_frame(_states(catalog, as_of, None), as_of)


def read_account_states_at_snapshot(
    catalog: Catalog, snapshot_id: int, as_of: dt.datetime
) -> dict[str, AccountState]:
    """Time travel: the states exactly as a past snapshot held them."""
    return states_from_frame(_states(catalog, as_of, snapshot_id), as_of)


def read_states_frame(catalog: Catalog, as_of: dt.datetime) -> pl.DataFrame:
    return _states(catalog, as_of, None)


# --- versioning ---------------------------------------------------------------


def current_snapshot_ids(catalog: Catalog) -> dict[str, int]:
    """The snapshot id of every tracked table -- what a training run logs."""
    out = {}
    for name in TRACKED_TABLES:
        snap = catalog.load_table(name).current_snapshot()
        if snap is not None:
            out[name] = snap.snapshot_id
    return out


def expire_old_snapshots(catalog: Catalog, name: str, keep_last: int) -> int:
    """Drop all but the newest `keep_last` snapshots of a table. Returns how many went."""
    table = catalog.load_table(name)
    snaps = sorted(table.snapshots(), key=lambda s: s.timestamp_ms)
    doomed = [s.snapshot_id for s in snaps[:-keep_last]] if keep_last > 0 else []
    if doomed:
        table.maintenance.expire_snapshots().by_ids(doomed).commit()
    return len(doomed)


def data_files_on_storage(catalog: Catalog, name: str) -> set[str]:
    """Every Parquet file under the table's data directory, as full URIs."""
    table = catalog.load_table(name)
    fs, data_dir = filesystem(f"{table.location()}/data", catalog.properties)
    infos = fs.get_file_info(pafs.FileSelector(data_dir, recursive=True, allow_not_found=True))
    return {
        to_uri(fs, i.path)
        for i in infos
        if i.type == pafs.FileType.File and i.path.endswith(".parquet")
    }


def remove_orphan_files(catalog: Catalog, name: str) -> int:
    """Delete Parquet files under the table's data dir that no snapshot references.

    Rebuilds replace files; expiring snapshots forgets the old ones but leaves
    them in storage. PyIceberg has no orphan cleanup (it needs Spark or Trino),
    so this is our own, for local disk and S3 alike: list what every remaining
    snapshot references, delete everything else. Run only after
    `expire_old_snapshots`. On S3, bucket versioning keeps deleted files for 7
    days as a safety net (docs/runbooks/aws-setup.md).
    """
    table = catalog.load_table(name)
    referenced = set(table.inspect.all_files()["file_path"].to_pylist())
    fs, data_dir = filesystem(f"{table.location()}/data", catalog.properties)
    removed = 0
    for uri in data_files_on_storage(catalog, name) - referenced:
        fs.delete_file(filesystem(uri, catalog.properties)[1])
        removed += 1
    if isinstance(fs, pafs.LocalFileSystem):
        root = Path(data_dir)
        for d in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    return removed
