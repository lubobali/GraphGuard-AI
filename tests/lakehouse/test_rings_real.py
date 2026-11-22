"""The ring list in the real lakehouse (S7.2): equal to the raw file, test window sealed.

Live: needs the Lakekeeper catalog and the raw ring list; skips elsewhere (CI).
"""

import os

import polars as pl
import pytest

from graphguard.config import PATTERNS_FILE

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1" or not PATTERNS_FILE.exists(),
        reason="no Lakekeeper catalog / raw ring list in this environment",
    ),
]


@pytest.fixture(scope="module")
def reader():
    from graphguard.lakehouse.catalog import open_catalog

    return open_catalog("reader")


def test_gold_rings_hold_no_test_window_row_and_168_validation_rings(reader):
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.lakehouse.tables import read_rings

    train_end, val_end = frozen_boundaries()
    rings = read_rings(reader)
    assert rings["timestamp"].max() < val_end
    val = rings.filter(pl.col("timestamp") >= train_end)
    assert val["pattern_id"].n_unique() == 168  # the number every evaluation reports


def test_the_reader_cannot_open_the_sealed_ring_list(reader):
    with pytest.raises(Exception):  # noqa: B017 -- forbidden or invisible: either is a refusal
        reader.load_table("sealed.rings").scan().to_polars()


@pytest.mark.slow
def test_ring_ids_from_gold_equal_the_raw_ring_list_on_all_of_silver(reader):
    from graphguard.analysis.patterns import parse_patterns
    from graphguard.evaluation.dataset import attach_pattern_ids
    from graphguard.lakehouse.tables import (
        SILVER_TX,
        scan_in_source_order,
        scan_silver_with_ring_ids,
    )

    new = scan_silver_with_ring_ids(reader).select("pattern_id").collect()
    old = (
        attach_pattern_ids(scan_in_source_order(reader, SILVER_TX), parse_patterns(PATTERNS_FILE))
        .select("pattern_id")
        .collect()
    )
    assert new.height == old.height and new.equals(old)  # same rows, same order, same ids
