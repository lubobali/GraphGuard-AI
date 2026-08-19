"""The patterns file is a text format, not a CSV, and must be parsed as one.

Blocks look like:

    BEGIN LAUNDERING ATTEMPT - FAN-OUT:  Max 16-degree Fan-Out
    <transaction rows>
    END LAUNDERING ATTEMPT - FAN-OUT

Each block is one laundering attempt. Losing the block boundaries would turn
labelled rings into a flat pile of transactions and destroy the only
pattern-level ground truth the dataset has.
"""

import polars as pl
import pytest

from graphguard.analysis.patterns import parse_patterns

SAMPLE = """BEGIN LAUNDERING ATTEMPT - FAN-OUT:  Max 3-degree Fan-Out
2022/09/01 00:06,021174,800737690,012,80011F990,2848.96,Euro,2848.96,Euro,ACH,1
2022/09/01 04:33,021174,800737690,020,80020C5B0,8630.40,Euro,8630.40,Euro,ACH,1
END LAUNDERING ATTEMPT - FAN-OUT

BEGIN LAUNDERING ATTEMPT - CYCLE:  Max 2 hops
2022/09/02 10:00,001,800000001,002,800000002,100.00,US Dollar,100.00,US Dollar,ACH,1
2022/09/03 11:00,002,800000002,001,800000001,100.00,US Dollar,100.00,US Dollar,ACH,1
END LAUNDERING ATTEMPT - CYCLE
"""


@pytest.fixture
def parsed(tmp_path):
    p = tmp_path / "patterns.txt"
    p.write_text(SAMPLE)
    return parse_patterns(p)


@pytest.mark.unit
def test_each_block_becomes_one_pattern(parsed):
    assert parsed["pattern_id"].n_unique() == 2


@pytest.mark.unit
def test_pattern_type_is_captured(parsed):
    assert sorted(parsed["pattern_type"].unique().to_list()) == ["CYCLE", "FAN-OUT"]


@pytest.mark.unit
def test_detail_after_the_colon_is_kept(parsed):
    fan = parsed.filter(pl.col("pattern_type") == "FAN-OUT")
    assert fan["pattern_detail"][0] == "Max 3-degree Fan-Out"


@pytest.mark.unit
def test_all_transaction_rows_are_kept(parsed):
    assert parsed.height == 4


@pytest.mark.unit
def test_transaction_columns_match_the_loader(parsed):
    for col in ("timestamp", "from_account", "to_account", "amount_paid"):
        assert col in parsed.columns


@pytest.mark.unit
def test_timestamps_are_datetimes(parsed):
    assert parsed["timestamp"].dtype == pl.Datetime


@pytest.mark.unit
def test_rows_keep_their_block_order(parsed):
    """Hop order inside a ring is the whole point; it must not be reordered."""
    cycle = parsed.filter(pl.col("pattern_type") == "CYCLE").sort("hop")
    assert cycle["from_account"].to_list() == ["800000001", "800000002"]
    assert cycle["hop"].to_list() == [0, 1]


@pytest.mark.unit
def test_blank_lines_are_ignored(tmp_path):
    p = tmp_path / "p.txt"
    p.write_text("\n\n" + SAMPLE + "\n\n")
    assert parse_patterns(p).height == 4
