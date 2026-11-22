"""The demo copy (S7.1): what the investigator screens read, safe from stream resets.

    python -m graphguard.demo.build      # = just demo-build (root, on the host)

Every soak, e2e or chaos run empties the stream's tables, so the screens read their own
database `demo` (ADR 0008), loaded from the stream's validation decisions + silver (the
currencies, banks, payment format and the answer key) + the raw accounts file (synthetic
bank and entity names, D8).

Tables: `transactions` (the queue: priority, rank, percentile -- ADR 0007's order), `accounts`,
`truth` (the answer key, kept apart so the queue and the agent never read it by accident),
`verdicts` (the investigators' audit trail, D7) and `build_info` (where it came from).
Amounts stay in their own currency: there are 15, and no exchange rates (ADR 0008).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import sys

import polars as pl

EXPECTED_ROWS = 1_015_300  # the validation window (S6.3, S6.11)


class DemoBuildError(RuntimeError):
    pass


# --- pure parts (tested) ------------------------------------------------------------------
def check_complete(decided: int, expected: int, versions: list[str]) -> None:
    if decided != expected:
        raise DemoBuildError(
            f"the stream's decisions are incomplete: {decided} of {expected} -- "
            "run the soak (or a full replay) first"
        )
    if len(set(versions)) != 1:
        raise DemoBuildError(f"decisions come from more than one model version: {versions}")


def ranked(decisions: pl.DataFrame) -> pl.DataFrame:
    """Priority (ADR 0007), the queue's rank (1 = first; ties by event order) and the
    percentile (share of transactions ranked below)."""
    # ADR 0007's priority (stream/rules.priority), vectorised -- a test holds them equal.
    hard = pl.col("rules").list.contains("both_new") | (pl.col("rules").list.len() >= 2)
    pri = pl.when(hard).then(1.0 + pl.col("score")).otherwise(pl.col("score"))
    n = decisions.height
    out = (
        decisions.with_columns(pri.cast(pl.Float64).alias("priority"))
        .sort(["priority", "event_time", "event_id"], descending=[True, False, False])
        .with_row_index("rank", offset=1)
        .with_columns(
            pl.col("rank").cast(pl.Int64),
            ((n - pl.col("rank")) / n * 100).round(4).alias("percentile"),
        )
    )
    return out


def accounts_table(raw: pl.DataFrame) -> pl.DataFrame:
    """(bank id, account) -> names. The key is the PAIR: some account numbers exist at two
    banks (8 in AMLworld HI-Small)."""
    return raw.select(
        pl.col("Bank ID").cast(pl.Int64).alias("bank_id"),
        pl.col("Account Number").alias("account"),
        pl.col("Bank Name").alias("bank_name"),
        pl.col("Entity Name").alias("entity_name"),
    ).unique(["bank_id", "account"], keep="first", maintain_order=True)


def with_names(tx: pl.DataFrame, accounts: pl.DataFrame) -> pl.DataFrame:
    out = tx
    for side in ("from", "to"):
        names = accounts.rename(
            {
                "bank_id": f"_{side}_bank_id",
                "account": f"{side}_account",
                "bank_name": f"{side}_bank_name",
                "entity_name": f"{side}_name",
            }
        )
        out = out.with_columns(pl.col(f"{side}_bank").cast(pl.Int64).alias(f"_{side}_bank_id"))
        out = out.join(names, on=[f"_{side}_bank_id", f"{side}_account"], how="left")
        out = out.drop(f"_{side}_bank_id")
    return out


def split_truth(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    truth = df.select("event_id", pl.col("is_laundering").cast(pl.Boolean)).sort("event_id")
    return df.drop("is_laundering"), truth


def fingerprint(df: pl.DataFrame) -> str:
    """sha256 of the rows in key order, independent of how they arrived."""
    key = "event_id" if "event_id" in df.columns else df.columns[0]
    flat = df.with_columns(
        pl.col(c).cast(pl.List(pl.Utf8)).list.join("|")
        for c, t in df.schema.items()
        if isinstance(t, pl.List)
    )
    h = hashlib.sha256()
    # in slices: one CSV string of a million rows cost hundreds of MB (S7.1)
    for i, part in enumerate(flat.sort(key).iter_slices(100_000)):
        h.update(part.write_csv(float_precision=17, include_header=i == 0).encode())
    return h.hexdigest()


# --- the load ------------------------------------------------------------------------------
def _decisions() -> tuple[pl.DataFrame, list[str], list[str]]:
    from graphguard.config import REPO_ROOT
    from graphguard.stream import db

    with db.connect(secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT model_version FROM decisions")
        versions = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT names FROM feature_sets ORDER BY version")
        names = [r[0] for r in cur.fetchall()]
        # COPY, not fetchall: a million rows as Python objects peaked at 3.5 GB (S7.1).
        buf = io.BytesIO()
        cur.copy_expert(
            "COPY (SELECT event_id, event_time, score, cold_policy, "
            "array_to_string(rules, '|') AS rules, alert::int AS alert, model_version, "
            "array_to_string(features, '|') AS features FROM decisions) "
            "TO STDOUT WITH (FORMAT csv, HEADER)",
            buf,
        )
    buf.seek(0)
    df = pl.read_csv(
        buf,
        schema={
            "event_id": pl.Int64,
            "event_time": pl.Datetime("us"),
            "score": pl.Float64,
            "cold_policy": pl.Utf8,
            "rules": pl.Utf8,
            "alert": pl.Int8,
            "model_version": pl.Utf8,
            "features": pl.Utf8,
        },
        missing_utf8_is_empty_string=True,
    ).with_columns(
        pl.when(pl.col("rules") == "")
        .then(pl.lit([], dtype=pl.List(pl.Utf8)))
        .otherwise(pl.col("rules").str.split("|"))
        .alias("rules"),
        pl.col("features").str.split("|").cast(pl.List(pl.Float64)),
        pl.col("alert").cast(pl.Boolean),
    )
    if len({tuple(n) for n in names}) != 1:
        raise DemoBuildError("feature_sets holds more than one feature list")
    return df, versions, names[0]


def assemble() -> tuple[dict[str, pl.DataFrame], dict]:
    from graphguard.config import ACCOUNTS_FILE
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.lakehouse.tables import assert_in_validation
    from graphguard.stream import replayer as rp

    decisions, versions, feature_names = _decisions()
    silver = rp.load_rows()  # validation window only, asserted inside
    check_complete(decisions.height, silver.height, versions)
    if silver.height != EXPECTED_ROWS:
        raise DemoBuildError(f"validation window has {silver.height} rows, not {EXPECTED_ROWS}")
    assert_in_validation(silver, frozen_boundaries())

    tx = silver.rename({"source_row": "event_id", "timestamp": "event_time"}).join(
        decisions.drop("event_time"), on="event_id", how="inner"
    )
    del silver, decisions  # peak memory (S7.1)
    if tx.height != EXPECTED_ROWS:
        raise DemoBuildError(f"only {tx.height} decisions match silver rows")
    tx = ranked(tx)
    accounts = accounts_table(pl.read_csv(ACCOUNTS_FILE, infer_schema_length=0).with_columns(
        pl.col("Bank ID").cast(pl.Int64)))  # fmt: skip
    tx = with_names(tx, accounts)
    tx, truth = split_truth(tx)
    tables = {"transactions": tx, "truth": truth, "accounts": accounts}
    info = {
        "built_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "model_version": versions[0],
        "feature_names": feature_names,
        "rows": {k: v.height for k, v in tables.items()},
        "fingerprints": {k: fingerprint(v) for k, v in tables.items()},
        "window": [str(b) for b in frozen_boundaries()],
    }
    return tables, info


def main(argv: list[str]) -> int:
    from graphguard.demo import db as ddb

    tables, info = assemble()
    ddb.load(tables, info)
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
