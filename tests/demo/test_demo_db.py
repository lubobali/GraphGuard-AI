"""The demo database's load format (S7.1): arrays reach Postgres exactly."""

import polars as pl
import pytest

from graphguard.demo import db

pytestmark = pytest.mark.unit


def test_lists_become_postgres_arrays():
    df = pl.DataFrame({"event_id": [1, 2], "rules": [["fan_in", 'a"b'], []],
                       "features": [[0.1, 2.0], [3.5]]})  # fmt: skip
    lines = db._csv(df).getvalue().splitlines()
    assert lines[0] == "event_id,rules,features"
    assert lines[1] == '1,"{""fan_in"",""a\\""b""}","{0.1,2.0}"'
    assert lines[2] == "2,{},{3.5}"


def test_the_queue_table_has_every_column_the_build_makes():
    assert list(db.TX_COLUMNS)[:2] == ["event_id", "event_time"]
    assert {"priority", "rank", "percentile", "from_name", "to_name"} <= set(db.TX_COLUMNS)
    assert "is_laundering" not in db.TX_COLUMNS  # the answer key lives in `truth`
