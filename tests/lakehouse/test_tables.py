"""The lakehouse must hold the leakage contract, not just store files.

Iceberg tables replace "features computed straight into Redis" (S5.6a). Every
property the old path had -- strictly-before features, the sealed test window,
determinism -- has to survive the move, and the tables add two of their own:
versioning and time travel. A SQLite catalog in a temp dir is used here; it is
the development backend PyIceberg documents, and these tests never touch the
real catalog in Postgres.
"""

import datetime as dt

import polars as pl
import pytest

from graphguard.lakehouse.schemas import (
    BronzeTransactions,
    GoldAccountFeatures,
    GoldEdges,
    GoldLabels,
    GoldRecentSends,
    SilverTransactions,
)
from graphguard.lakehouse.tables import (
    BRONZE_TX,
    GOLD_EDGES,
    GOLD_FEATURES,
    GOLD_LABELS,
    GOLD_RECENT_SENDS,
    SILVER_TX,
    StreamBoundsError,
    assert_in_validation,
    current_snapshot_ids,
    expire_old_snapshots,
    read_account_states,
    read_account_states_at_snapshot,
    read_edges,
    read_recent_sends,
    validation_stream,
    write_bronze,
    write_gold_edges,
    write_gold_features,
    write_gold_labels,
    write_gold_recent_sends,
    write_silver,
)
from graphguard.serving.online_features import build_account_states, recent_sends_frame

pytestmark = pytest.mark.unit

TRAIN_END = dt.datetime(2022, 9, 6, 12, 0)
VAL_END = dt.datetime(2022, 9, 8, 12, 0)
TAIL = dt.datetime(2022, 9, 11)


def _tx(ts, frm, to, amount=100.0, laundering=0):
    return {
        "timestamp": ts,
        "from_bank": "010",
        "from_account": frm,
        "to_bank": "011",
        "to_account": to,
        "amount_received": amount,
        "receiving_currency": "US Dollar",
        "amount_paid": amount,
        "payment_currency": "US Dollar",
        "payment_format": "ACH",
        "is_laundering": laundering,
    }


@pytest.fixture
def raw():
    rows = [
        _tx(dt.datetime(2022, 9, 1, 9), "A", "B", 50.0),
        _tx(dt.datetime(2022, 9, 2, 10), "A", "C", 70.0, 1),
        _tx(dt.datetime(2022, 9, 3, 11), "B", "A", 30.0),
        _tx(dt.datetime(2022, 9, 6, 1), "C", "B", 20.0),
        _tx(TRAIN_END, "A", "D", 999.0),  # exactly at the boundary
        _tx(dt.datetime(2022, 9, 7, 8), "D", "A", 15.0),  # validation
        _tx(dt.datetime(2022, 9, 9, 8), "B", "D", 40.0, 1),  # test window
        _tx(dt.datetime(2022, 9, 12, 8), "A", "B", 5.0, 1),  # post-tail artefact
    ]
    return pl.DataFrame(rows).with_columns(pl.col("timestamp").cast(pl.Datetime("us")))


def _build(cat, raw):
    write_bronze(cat, raw)
    write_silver(cat, boundaries=(TRAIN_END, VAL_END), tail_cutoff=TAIL)
    write_gold_features(cat, as_of=TRAIN_END)
    write_gold_recent_sends(cat, as_of=TRAIN_END)
    write_gold_edges(cat, as_of=TRAIN_END)
    write_gold_labels(cat)
    from graphguard.lakehouse.tables import write_rings  # S7.2: a tracked table

    write_rings(cat, _patterns(raw), (TRAIN_END, VAL_END), tail_cutoff=TAIL)


def _read(cat, name):
    return cat.load_table(name).scan().to_polars()


def test_bronze_keeps_every_raw_row(cat, raw):
    write_bronze(cat, raw)
    got = _read(cat, BRONZE_TX).sort("timestamp")
    assert got.height == raw.height
    assert got.select(raw.columns).equals(raw.sort("timestamp"))


def test_silver_holds_neither_the_test_window_nor_the_tail(cat, raw):
    _build(cat, raw)
    silver = _read(cat, SILVER_TX)
    assert silver["timestamp"].max() < VAL_END
    assert silver.height == 6


def test_test_window_rows_exist_only_in_the_sealed_table(cat, raw):
    _build(cat, raw)
    from graphguard.lakehouse.tables import _SEALED_TX  # the one allowed reference

    sealed = _read(cat, _SEALED_TX)
    assert sealed.height == 1
    assert sealed["timestamp"].min() >= VAL_END
    assert sealed["timestamp"].max() < TAIL


def test_silver_is_partitioned_by_day(cat, raw):
    _build(cat, raw)
    spec = cat.load_table(SILVER_TX).spec()
    assert [str(f.transform) for f in spec.fields] == ["day"]


@pytest.mark.parametrize("name", [BRONZE_TX, SILVER_TX, GOLD_FEATURES, GOLD_LABELS])
def test_every_table_is_iceberg_format_v2(cat, raw, name):
    _build(cat, raw)
    assert cat.load_table(name).metadata.format_version == 2


def test_gold_features_equal_the_serving_path(cat, raw):
    # Parity: the store filled from gold must hold exactly what the existing
    # path computes. If these differ, the deployed model sees different numbers.
    _build(cat, raw)
    silver_lf = _read(cat, SILVER_TX).lazy()
    assert read_account_states(cat, as_of=TRAIN_END) == build_account_states(silver_lf, TRAIN_END)


def test_a_transaction_at_exactly_as_of_is_not_counted(cat, raw):
    # The 999.0 transfer happens AT train_end. A state "as of train_end" must not
    # include it, or a transaction can see itself.
    _build(cat, raw)
    a = read_account_states(cat, as_of=TRAIN_END)["A"]
    assert a.n_sent == 2
    assert a.amount_sent == pytest.approx(120.0)
    assert "D" not in read_account_states(cat, as_of=TRAIN_END) or (
        read_account_states(cat, as_of=TRAIN_END)["D"].n_received == 0
    )


def test_rebuilding_from_the_same_bronze_gives_identical_tables(cat, raw):
    _build(cat, raw)
    first = {
        n: _read(cat, n).sort(pl.all()).hash_rows().sum()
        for n in (SILVER_TX, GOLD_FEATURES, GOLD_LABELS)
    }
    write_silver(cat, boundaries=(TRAIN_END, VAL_END), tail_cutoff=TAIL)
    write_gold_features(cat, as_of=TRAIN_END)
    write_gold_labels(cat)
    second = {
        n: _read(cat, n).sort(pl.all()).hash_rows().sum()
        for n in (SILVER_TX, GOLD_FEATURES, GOLD_LABELS)
    }
    assert first == second


def test_time_travel_returns_the_older_features(cat, raw):
    _build(cat, raw)
    old_snapshot = current_snapshot_ids(cat)[GOLD_FEATURES]
    old_states = read_account_states(cat, as_of=TRAIN_END)

    # New data arrives and gold is rebuilt.
    more = raw.vstack(
        pl.DataFrame([_tx(dt.datetime(2022, 9, 5, 9), "A", "E", 1.0)]).with_columns(
            pl.col("timestamp").cast(pl.Datetime("us"))
        )
    )
    write_bronze(cat, more)
    write_silver(cat, boundaries=(TRAIN_END, VAL_END), tail_cutoff=TAIL)
    write_gold_features(cat, as_of=TRAIN_END)

    assert read_account_states(cat, as_of=TRAIN_END)["A"].n_sent == 3
    assert read_account_states_at_snapshot(cat, old_snapshot, as_of=TRAIN_END) == old_states


def test_labels_carry_no_test_window_rows_and_an_unset_known_at(cat, raw):
    _build(cat, raw)
    labels = _read(cat, GOLD_LABELS)
    assert labels.height == 6
    assert labels["timestamp"].max() < VAL_END
    # When a label becomes known is Phase 6's label-delay policy. Until then it
    # is explicitly unknown, not silently "immediately".
    assert labels["label_known_at"].null_count() == labels.height


def test_expire_keeps_only_the_last_n_snapshots(cat, raw):
    _build(cat, raw)
    for _ in range(4):
        write_gold_features(cat, as_of=TRAIN_END)
    expire_old_snapshots(cat, GOLD_FEATURES, keep_last=2)
    assert len(cat.load_table(GOLD_FEATURES).snapshots()) == 2


def test_snapshot_ids_are_reported_for_every_table(cat, raw):
    _build(cat, raw)
    ids = current_snapshot_ids(cat)
    assert set(ids) == {BRONZE_TX, SILVER_TX, GOLD_FEATURES, GOLD_LABELS, "gold.rings"}
    assert all(isinstance(v, int) for v in ids.values())


# --- data contracts, one per layer, asserted as tests -------------------------


def test_each_layer_satisfies_its_contract(cat, raw):
    _build(cat, raw)
    BronzeTransactions.validate(_read(cat, BRONZE_TX))
    SilverTransactions.validate(_read(cat, SILVER_TX))
    GoldAccountFeatures.validate(_read(cat, GOLD_FEATURES))
    GoldLabels.validate(_read(cat, GOLD_LABELS))
    GoldRecentSends.validate(_read(cat, GOLD_RECENT_SENDS))
    GoldEdges.validate(_read(cat, GOLD_EDGES))


def test_the_gold_contract_rejects_a_negative_count():
    from pandera.errors import SchemaError

    bad = pl.DataFrame(
        {
            "account": ["A"],
            "as_of": [TRAIN_END],
            "n_sent": [-1],
            "n_received": [0],
            "amount_sent": [0.0],
            "amount_received": [0.0],
            "distinct_out": [0],
            "distinct_in": [0],
            "sent_last_24h": [0],
            "last_seen": [None],
            "last_sent": [None],
        }
    ).with_columns(pl.col("as_of").cast(pl.Datetime("us")))
    with pytest.raises(SchemaError):
        GoldAccountFeatures.validate(bad)


# --- low-memory writes and file maintenance -----------------------------------


def test_a_rebuild_is_one_logical_commit_not_one_per_day(cat, raw):
    # Writes stream day by day, but readers must never see a half-written
    # table: the delete and all the day files land in one transaction.
    _build(cat, raw)
    before = len(cat.load_table(SILVER_TX).snapshots())
    write_silver(cat, boundaries=(TRAIN_END, VAL_END), tail_cutoff=TAIL)
    assert len(cat.load_table(SILVER_TX).snapshots()) - before <= 2


def test_files_left_behind_by_rebuilds_are_removed(cat, raw):
    from graphguard.lakehouse.tables import data_files_on_storage, remove_orphan_files

    _build(cat, raw)
    for _ in range(3):
        write_silver(cat, boundaries=(TRAIN_END, VAL_END), tail_cutoff=TAIL)
    on_storage_before = data_files_on_storage(cat, SILVER_TX)

    expire_old_snapshots(cat, SILVER_TX, keep_last=1)
    removed = remove_orphan_files(cat, SILVER_TX)

    live = set(cat.load_table(SILVER_TX).inspect.files()["file_path"].to_pylist())
    on_storage_after = data_files_on_storage(cat, SILVER_TX)
    assert removed > 0
    assert on_storage_after == live  # nothing referenced was deleted, nothing orphaned remains
    assert on_storage_after < on_storage_before
    assert _read(cat, SILVER_TX).height == 6  # and the table still reads


# --- exact parity: source order is preserved ----------------------------------


@pytest.mark.regression
def test_gold_is_bit_identical_even_when_the_source_is_not_in_time_order(cat):
    # Float addition is not associative: 0.1 + 0.2 + 0.3 != 0.3 + 0.2 + 0.1 in
    # the last bit. The real CSV is not time-sorted, so a lakehouse that reorders
    # rows produced sums 1 ulp off from the CSV path for 23,384 accounts (S5.6a).
    # Each row keeps its source position and features are computed in that order.
    amounts = [0.1, 0.7, 0.2, 1e16, 0.3, -1e16, 0.6]
    hours = [5, 1, 4, 2, 6, 3, 0]  # deliberately not chronological
    raw = pl.DataFrame(
        [
            _tx(dt.datetime(2022, 9, 1, h), "A", f"R{i}", a)
            for i, (h, a) in enumerate(zip(hours, amounts, strict=True))
        ]
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("us")))
    _build(cat, raw)
    expected = build_account_states(raw.lazy().filter(pl.col("timestamp") < VAL_END), TRAIN_END)
    got = read_account_states(cat, as_of=TRAIN_END)
    assert got["A"].amount_sent == expected["A"].amount_sent  # exact, not approx


def test_every_row_keeps_its_source_position(cat, raw):
    _build(cat, raw)
    bronze = _read(cat, BRONZE_TX).sort("source_row")
    assert bronze["source_row"].to_list() == list(range(raw.height))
    assert bronze.drop("source_row").equals(raw)


# --- S6.2: what the stream starts from, and what it may replay -----------------


def test_gold_recent_sends_equal_the_serving_definition(cat, raw):
    _build(cat, raw)
    expected = recent_sends_frame(
        raw.lazy().filter(pl.col("timestamp") < VAL_END), TRAIN_END
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("us")))
    got = read_recent_sends(cat, as_of=TRAIN_END)
    assert got.equals(expected)
    assert got.height == 1  # only C -> B at 09-06 01:00 is inside (train_end - 24h, train_end)


def test_the_stream_replays_validation_only_in_time_then_source_order(cat, raw):
    _build(cat, raw)
    df = validation_stream(cat, (TRAIN_END, VAL_END)).collect()
    assert df["timestamp"].min() >= TRAIN_END and df["timestamp"].max() < VAL_END
    assert df.height == 2  # the boundary row (A -> D at train_end) and D -> A
    assert df.select("timestamp", "source_row").equals(
        df.select("timestamp", "source_row").sort(["timestamp", "source_row"])
    )
    assert "source_row" in df.columns  # the event id the stream carries


def test_rows_outside_validation_are_refused():
    ok = pl.DataFrame({"timestamp": [TRAIN_END]}).with_columns(
        pl.col("timestamp").cast(pl.Datetime("us"))
    )
    assert_in_validation(ok, (TRAIN_END, VAL_END))
    for bad in (TRAIN_END - dt.timedelta(minutes=1), VAL_END):
        df = pl.DataFrame({"timestamp": [bad]})
        with pytest.raises(StreamBoundsError):
            assert_in_validation(df, (TRAIN_END, VAL_END))


def test_gold_edges_hold_every_pair_seen_before_train_end_once(cat, raw):
    _build(cat, raw)
    got = read_edges(cat, as_of=TRAIN_END)
    assert sorted(got.iter_rows()) == [("A", "B"), ("A", "C"), ("B", "A"), ("C", "B")]


# --- S7.2: the ring list, split like the transactions ---------------------------------
def _patterns(raw):
    # rings on train rows (A->C, B->A), the validation row (D->A), the test-window row (B->D)
    frm, to = pl.col("from_account"), pl.col("to_account")
    picked = raw.filter(frm.is_in(["D", "B"]) & to.is_in(["A", "D"]) | ((frm == "A") & (to == "C")))
    return picked.select("timestamp", "from_account", "to_account", "amount_paid").with_columns(
        pl.Series("pattern_id", list(range(picked.height)), dtype=pl.Int32),
        pl.lit("FAN-OUT").alias("pattern_type"),
        pl.lit("").alias("pattern_detail"),
        pl.lit(0, dtype=pl.Int32).alias("hop"),
    )


def test_rings_are_split_like_the_transactions(cat, raw):
    from graphguard.lakehouse.tables import GOLD_RINGS, read_rings, write_rings

    _build(cat, raw)
    gold_n, sealed_n = write_rings(cat, _patterns(raw), (TRAIN_END, VAL_END), tail_cutoff=TAIL)
    gold = read_rings(cat)
    assert gold_n == gold.height == 3 and sealed_n == 1  # A->C, B->A, D->A | B->D
    assert gold["timestamp"].max() < VAL_END
    sealed = _read(cat, "sealed.rings")
    assert sealed["timestamp"].min() >= VAL_END
    assert GOLD_RINGS.startswith("gold.")


def test_silver_with_ring_ids_equals_attaching_the_raw_ring_list(cat, raw):
    from graphguard.evaluation.dataset import attach_pattern_ids
    from graphguard.lakehouse.tables import (
        scan_in_source_order,
        scan_silver_with_ring_ids,
        write_rings,
    )

    _build(cat, raw)
    write_rings(cat, _patterns(raw), (TRAIN_END, VAL_END), tail_cutoff=TAIL)
    new = scan_silver_with_ring_ids(cat).collect()
    old = attach_pattern_ids(scan_in_source_order(cat, SILVER_TX), _patterns(raw)).collect()
    assert new.equals(old.select(new.columns))
