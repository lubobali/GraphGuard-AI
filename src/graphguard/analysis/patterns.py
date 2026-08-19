"""Parse the labelled laundering patterns file.

This file is the reason this dataset beats the alternatives. It does not just
say which transactions are laundering; it says which transactions belong to
the *same* laundering attempt, and what shape that attempt is. That is what
makes pattern-level recall measurable -- catching one hop of a twelve-hop ring
is not catching the ring.

The format is blocks of plain text, not CSV:

    BEGIN LAUNDERING ATTEMPT - FAN-OUT:  Max 16-degree Fan-Out
    <transaction rows, in hop order>
    END LAUNDERING ATTEMPT - FAN-OUT

Row order inside a block is meaningful and is preserved as `hop`.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from graphguard.data.loader import CANONICAL_COLUMNS, TIMESTAMP_FORMAT

_BEGIN = re.compile(r"^BEGIN LAUNDERING ATTEMPT\s*-\s*([A-Z\- ]+?)\s*(?::\s*(.*))?$")
_END = re.compile(r"^END LAUNDERING ATTEMPT")


def parse_patterns(path: str | Path) -> pl.DataFrame:
    """Return one row per transaction, tagged with the attempt it belongs to."""
    pattern_ids: list[int] = []
    pattern_types: list[str] = []
    details: list[str] = []
    hops: list[int] = []
    rows: list[list[str]] = []

    current_id = -1
    current_type = ""
    current_detail = ""
    hop = 0

    with open(path, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue

            begin = _BEGIN.match(line)
            if begin:
                current_id += 1
                current_type = begin.group(1).strip()
                current_detail = (begin.group(2) or "").strip()
                hop = 0
                continue

            if _END.match(line):
                continue

            fields = line.split(",")
            if len(fields) != len(CANONICAL_COLUMNS):
                # Not a transaction row. Skipped rather than guessed at.
                continue

            pattern_ids.append(current_id)
            pattern_types.append(current_type)
            details.append(current_detail)
            hops.append(hop)
            rows.append(fields)
            hop += 1

    frame = pl.DataFrame(
        {name: [r[i] for r in rows] for i, name in enumerate(CANONICAL_COLUMNS)},
        schema={name: pl.String for name in CANONICAL_COLUMNS},
    )

    return frame.with_columns(
        pl.Series("pattern_id", pattern_ids, dtype=pl.Int32),
        pl.Series("pattern_type", pattern_types, dtype=pl.String),
        pl.Series("pattern_detail", details, dtype=pl.String),
        pl.Series("hop", hops, dtype=pl.Int32),
    ).with_columns(
        pl.col("timestamp").str.to_datetime(TIMESTAMP_FORMAT),
        pl.col("amount_paid").cast(pl.Float64),
        pl.col("amount_received").cast(pl.Float64),
        pl.col("is_laundering").cast(pl.Int8),
    )
