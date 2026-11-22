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

import numpy as np
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


def split_truth(
    df: pl.DataFrame, rings: pl.DataFrame | None = None
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(queue table, answer key). The answer key carries the ring id, type and hop
    (gold.rings, S7.2) -- never the queue table, never the agent."""
    truth = df.select("event_id", pl.col("is_laundering").cast(pl.Boolean)).sort("event_id")
    if rings is not None:
        truth = truth.join(
            rings.select(
                pl.col("source_row").alias("event_id"),
                "pattern_id", "pattern_type", "hop",
            ),
            on="event_id", how="left", maintain_order="left",
        )  # fmt: skip
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


WINDOW_DAYS = 50.5667 / 24  # 2022-09-06 13:34 -> 2022-09-08 16:08 (the validation window)
CHECKPOINTS = (50, 100, 211, 500, 1_000, 5_000)  # 211 = a 100-a-day team over the window


def strict_order(df: pl.DataFrame, key: str, descending: bool = True) -> np.ndarray:
    """A strict ranking signal (higher = sooner) from `key`, ties broken by event order --
    the same tie rule as the queue (ranked())."""
    ordered = df.with_row_index("_i").sort(
        [key, "event_time", "event_id"], descending=[descending, False, False]
    )
    sig = np.empty(df.height, dtype=float)
    sig[ordered["_i"].to_numpy()] = np.arange(df.height, 0, -1, dtype=float)
    return sig


def capacity_table(tx: pl.DataFrame, truth: pl.DataFrame, seed: int, max_k: int = 5_000):
    """The slider's numbers (S7.3) for four rankings of the same validation rows."""
    from graphguard.evaluation.capacity import capacity_curve
    from graphguard.evaluation.evaluate import NO_PATTERN
    from graphguard.stream.rules import rules_only_rank

    df = tx.select("event_id", "event_time", "priority", "score", "rules", "amount_paid").join(
        truth.select("event_id", "is_laundering", "pattern_id"), on="event_id", how="left"
    )
    y = df["is_laundering"].cast(pl.Int8).to_numpy()
    pids = df["pattern_id"].fill_null(NO_PATTERN).to_numpy()
    rules_rank = [
        rules_only_rank(tuple(r), a)
        for r, a in zip(df["rules"].to_list(), df["amount_paid"].to_list(), strict=True)
    ]
    df = df.with_columns(pl.Series("rules_rank", rules_rank, dtype=pl.Float64))
    rankings = {
        "system": strict_order(df, "priority"),
        "model": strict_order(df, "score"),
        "rules": strict_order(df, "rules_rank"),
        "random": np.random.default_rng(seed).permutation(df.height).astype(float) + 1.0,
    }
    rows = [
        {"ranking": name, **r}
        for name, sig in rankings.items()
        for r in capacity_curve(y, sig, pids, max_k=max_k)
    ]
    return pl.DataFrame(rows)


def subgraphs_table(tx: pl.DataFrame, accounts: pl.DataFrame, edges: pl.DataFrame, top_n: int):
    """S7.5: one as-of money-flow graph per top alert, names on the nodes, the stream's rank
    and score on edges that are validation transactions. No labels."""
    from graphguard.demo.subgraph import EdgeIndex, subgraph

    index = EdgeIndex(
        edges.join(
            tx.select(pl.col("event_id").alias("source_row"), "rank", "score"),
            on="source_row",
            how="left",
        )
    )
    names = {
        f"{b}:{a}": (bn, en)
        for b, a, bn, en in accounts.select(
            "bank_id", "account", "bank_name", "entity_name"
        ).iter_rows()
    }
    top = tx.filter(pl.col("rank") <= top_n).sort("rank")["event_id"].to_list()
    graphs = []
    for eid in top:
        g = subgraph(index, eid)
        for n in g["nodes"]:
            n["bank"], n["name"] = names.get(n["id"], (None, None))
        graphs.append(json.dumps(g, sort_keys=True, separators=(",", ":")))
    return pl.DataFrame({"event_id": top, "graph": graphs},
                        schema={"event_id": pl.Int64, "graph": pl.Utf8})  # fmt: skip


def _graph_edges() -> pl.DataFrame:
    """Silver from 72 h before validation to its end: early alerts reach back into training
    transactions (never the sealed window)."""
    from graphguard.demo.subgraph import WINDOW
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.tables import SILVER_TX, _scan

    train_end, val_end = frozen_boundaries()
    return (
        _scan(open_catalog("reader"), SILVER_TX)
        .filter((pl.col("timestamp") >= train_end - WINDOW) & (pl.col("timestamp") < val_end))
        .select(
            "source_row",
            "timestamp",
            "from_bank",
            "from_account",
            "to_bank",
            "to_account",
            "amount_paid",
            "payment_currency",
            "payment_format",
        )  # fmt: skip
        .collect()
    )


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
    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.tables import read_rings

    tx, truth = split_truth(tx, read_rings(open_catalog("reader")))
    from graphguard.config import SEED

    capacity = capacity_table(tx, truth, seed=SEED)
    from graphguard.config import REPO_ROOT
    from graphguard.demo.explain import explain
    from graphguard.serving.model_bundle import ModelBundle

    bundle = ModelBundle.load(REPO_ROOT / "models" / "production")
    explanations = explain(tx, feature_names, bundle)  # refuses on any score mismatch
    from graphguard.demo.explain import TOP_N

    graphs = subgraphs_table(tx, accounts, _graph_edges(), top_n=TOP_N)
    tables = {
        "transactions": tx,
        "truth": truth,
        "accounts": accounts,
        "capacity": capacity,
        "explanations": explanations,
        "subgraphs": graphs,
    }
    info = {
        "built_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "model_version": versions[0],
        "feature_names": feature_names,
        "rows": {k: v.height for k, v in tables.items()},
        "fingerprints": {k: fingerprint(v) for k, v in tables.items() if k != "capacity"}
        | {"capacity": fingerprint(capacity.sort("ranking", "k"))},
        "explained_model_metadata": bundle.trained_on,
        "window": [str(b) for b in frozen_boundaries()],
    }
    return tables, info


def checkpoints(capacity: pl.DataFrame) -> dict:
    """The numbers worth writing down (docs/analysis/s7.3-capacity.json)."""
    out = {
        "window_days": round(WINDOW_DAYS, 4),
        "per_day_note": "a team working N alerts a day handles k = N x window_days alerts",
        "rings_note": "caught = >= 50% of a ring's validation hops in the top k; touched = any",
        "rankings": {},
    }
    for (name,), part in capacity.group_by(["ranking"], maintain_order=True):
        rows = part.filter(pl.col("k").is_in(CHECKPOINTS)).sort("k")
        out["rankings"][name] = {
            str(r["k"]): {c: r[c] for c in ("caught", "missed", "precision", "recall",
                                             "rings_caught", "rings_touched", "rings_total")}
            for r in rows.to_dicts()
        }  # fmt: skip
    return out


def main(argv: list[str]) -> int:
    from graphguard.config import REPO_ROOT
    from graphguard.demo import db as ddb

    tables, info = assemble()
    ddb.load(tables, info)
    (REPO_ROOT / "docs" / "analysis" / "s7.3-capacity.json").write_text(
        json.dumps(checkpoints(tables["capacity"]), indent=2) + "\n"
    )
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
