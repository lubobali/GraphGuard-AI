"""Train the GNN and score it on validation through the same evaluate().

Same frozen split, same entry point, same metrics as the tabular baseline, so
the comparison in Phase 4's gate is like for like.
"""

from __future__ import annotations

import argparse
import datetime as dt
import time

import polars as pl
import torch

from graphguard.analysis.patterns import parse_patterns
from graphguard.config import PATTERNS_FILE, SEED, TRANSACTIONS_FILE
from graphguard.data.loader import load_transactions
from graphguard.evaluation.dataset import attach_pattern_ids, frozen_boundaries
from graphguard.evaluation.evaluate import DEFAULT_K_VALUES, evaluate
from graphguard.evaluation.split import truncate_tail
from graphguard.features.basic import build_basic_features
from graphguard.graph.train import make_model, run_epoch
from graphguard.tracking import log_run, start_tracking


def _days_between(start: dt.datetime, end: dt.datetime) -> list[dt.date]:
    day = start.date()
    out = []
    while day <= end.date():
        out.append(day)
        day += dt.timedelta(days=1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--lr", type=float, default=0.005)
    ap.add_argument("--batch-size", type=int, default=8192)
    ap.add_argument("--max-rows-per-day", type=int, default=200_000)
    ap.add_argument("--smoke", action="store_true", help="one day, tiny, just prove it runs")
    args = ap.parse_args()

    t0 = time.time()
    train_end, val_end = frozen_boundaries()

    base = attach_pattern_ids(
        truncate_tail(load_transactions(TRANSACTIONS_FILE)), parse_patterns(PATTERNS_FILE)
    )
    frame = build_basic_features(base)

    # History is the full record: a validation row's past legitimately includes
    # the training window. Targets are only the rows of the split being scored.
    train_targets = frame.filter(pl.col("timestamp") < train_end)
    val_targets = frame.filter((pl.col("timestamp") >= train_end) & (pl.col("timestamp") < val_end))

    train_days = _days_between(dt.datetime(2022, 9, 1), train_end)
    val_days = _days_between(train_end, val_end)

    if args.smoke:
        train_days, val_days = train_days[1:2], val_days[:1]
        args.epochs, args.max_rows_per_day = 1, 20_000

    # Targets must cover exactly the days being walked, or the length check
    # below fires. This matters in smoke mode and would matter again for any
    # partial run.
    def _within(frame_: pl.LazyFrame, days: list[dt.date]) -> pl.LazyFrame:
        first = dt.datetime.combine(days[0], dt.time.min)
        last = dt.datetime.combine(days[-1], dt.time.min) + dt.timedelta(days=1)
        return frame_.filter((pl.col("timestamp") >= first) & (pl.col("timestamp") < last))

    train_targets = _within(train_targets, train_days)
    val_targets = _within(val_targets, val_days)

    print(f"train days {train_days[0]}..{train_days[-1]}   val days {val_days[0]}..{val_days[-1]}")

    counts = (
        frame.filter(pl.col("timestamp") < train_end)
        .select(pl.len().alias("n"), pl.col("is_laundering").sum().alias("pos"))
        .collect()
    )
    n, pos = int(counts["n"][0]), int(counts["pos"][0])
    pos_weight = (n - pos) / pos
    print(f"train rows {n:,}  positives {pos:,}  pos_weight {pos_weight:.0f}")

    model = make_model(hidden=args.hidden, dropout=args.dropout, seed=SEED)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    for epoch in range(args.epochs):
        t = time.time()
        loss, _, _ = run_epoch(
            model,
            frame,
            train_targets,
            train_days,
            optimizer=optimizer,
            batch_size=args.batch_size,
            pos_weight=pos_weight,
            max_rows_per_day=args.max_rows_per_day,
            seed=SEED,
        )
        print(
            f"epoch {epoch + 1}/{args.epochs}  loss {loss:.4f}  ({time.time() - t:.0f}s)",
            flush=True,
        )

    # Validation: every row scored, nothing subsampled.
    t = time.time()
    _, scores, labels = run_epoch(model, frame, val_targets, val_days, batch_size=args.batch_size)
    print(f"scored {len(scores):,} validation rows ({time.time() - t:.0f}s)", flush=True)

    val_rows = val_targets.sort("timestamp").collect()
    if val_rows.height != len(scores):
        raise RuntimeError(
            f"scored {len(scores)} rows but validation has {val_rows.height}. "
            "Refusing to truncate: that would misalign scores from labels."
        )

    result = evaluate(
        labels.astype(int),
        scores,
        k_values=DEFAULT_K_VALUES,
        pattern_ids=val_rows["pattern_id"].to_numpy(),
        amounts=val_rows["amount_paid"].to_numpy(),
    )

    print("\n--- graphsage on validation ---")
    print(f"  PR-AUC {result['pr_auc']:.5f}   base rate {result['base_rate']:.5%}")
    for k in DEFAULT_K_VALUES:
        pat = result["pattern"][k]
        print(
            f"  k={k:<6} precision {result['precision_at_k'][k]:8.5f}"
            f"  lift {result['lift_at_k'][k]:7.2f}x"
            f"   rings {pat['n_caught']:>3}/{pat['n_patterns']}"
        )

    if not args.smoke:
        client, experiment_id = start_tracking()
        log_run(
            experiment_id,
            params={
                "model": "graphsage",
                "split": "validation",
                "kind": "gnn",
                "seed": str(SEED),
                "epochs": str(args.epochs),
                "hidden": str(args.hidden),
                "lr": str(args.lr),
                "dropout": str(args.dropout),
            },
            metrics={
                "pr_auc": result["pr_auc"],
                **{f"precision_at_{k}": v for k, v in result["precision_at_k"].items()},
                **{f"pattern_recall_at_{k}": p["recall"] for k, p in result["pattern"].items()},
            },
            tags={"phase": "4"},
        )

    print(f"\ntotal {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
