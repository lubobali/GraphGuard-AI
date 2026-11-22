"""A training run must record exactly which data it saw (S5.6a)."""

import datetime as dt
import hashlib
import re

import polars as pl
import pytest

from graphguard.config import REPO_ROOT
from graphguard.evaluation.dataset import SPLIT_FILE
from graphguard.lakehouse.catalog import open_catalog
from graphguard.lakehouse.lineage import NOT_A_GIT_CHECKOUT, training_lineage
from graphguard.lakehouse.tables import (
    TRACKED_TABLES,
    write_bronze,
    write_gold_features,
    write_gold_labels,
    write_rings,
    write_silver,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def cat(tmp_path):
    c = open_catalog(uri=f"sqlite:///{tmp_path}/c.db", warehouse=f"file://{tmp_path}/wh")
    row = {
        "timestamp": dt.datetime(2022, 9, 1),
        "from_bank": "1",
        "from_account": "A",
        "to_bank": "2",
        "to_account": "B",
        "amount_received": 1.0,
        "receiving_currency": "US Dollar",
        "amount_paid": 1.0,
        "payment_currency": "US Dollar",
        "payment_format": "ACH",
        "is_laundering": 0,
    }
    write_bronze(c, pl.DataFrame([row]).with_columns(pl.col("timestamp").cast(pl.Datetime("us"))))
    write_silver(c, boundaries=(dt.datetime(2022, 9, 2), dt.datetime(2022, 9, 3)))
    write_gold_features(c, as_of=dt.datetime(2022, 9, 2))
    write_gold_labels(c)
    # S7.2: the ring list is a tracked table (training reads it); one ring row here
    patterns = (
        pl.DataFrame([row])
        .select(
            pl.col("timestamp").cast(pl.Datetime("us")), "from_account", "to_account", "amount_paid"
        )
        .with_columns(
            pl.lit(0, dtype=pl.Int32).alias("pattern_id"),
            pl.lit("FAN-OUT").alias("pattern_type"),
            pl.lit("").alias("pattern_detail"),
            pl.lit(0, dtype=pl.Int32).alias("hop"),
        )
    )
    write_rings(c, patterns, (dt.datetime(2022, 9, 2), dt.datetime(2022, 9, 3)))
    return c


def test_lineage_names_every_tracked_table_snapshot(cat):
    lin = training_lineage(cat)
    for name in TRACKED_TABLES:
        assert isinstance(lin[f"snapshot.{name}"], int)


def test_lineage_never_mentions_the_sealed_table(cat):
    assert not any("sealed" in k for k in training_lineage(cat))


def test_lineage_pins_the_frozen_split_and_the_code(cat):
    lin = training_lineage(cat)
    assert lin["frozen_split_sha256"] == hashlib.sha256(SPLIT_FILE.read_bytes()).hexdigest()
    if (REPO_ROOT / ".git").exists():
        assert re.fullmatch(r"[0-9a-f]{40}(-dirty)?", lin["git_sha"])
    else:  # a tarball or image: said explicitly, never a crash or a fake sha
        assert lin["git_sha"] == NOT_A_GIT_CHECKOUT


def test_an_explicit_sha_from_the_environment_wins(cat, monkeypatch):
    monkeypatch.setenv("GRAPHGUARD_GIT_SHA", "a" * 40)
    assert training_lineage(cat)["git_sha"] == "a" * 40
