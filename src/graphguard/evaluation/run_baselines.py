"""Score the two dumb baselines and record them in MLflow.

These are the floor. Every model built after this is compared against these
numbers, and any model that fails to clear them is not a model.

Scored on **validation**, not test. Contract rule 4: the test window is opened
once, at the end. Even a baseline does not get to open it.
"""

from __future__ import annotations

from graphguard.config import SEED
from graphguard.evaluation.baselines import rank_by_amount, rank_randomly
from graphguard.evaluation.dataset import load_split
from graphguard.evaluation.evaluate import DEFAULT_K_VALUES, evaluate
from graphguard.tracking import log_run, start_tracking

SPLIT = "validation"


def _flatten(result: dict) -> dict[str, float]:
    """MLflow metrics are flat floats, so nested results are unrolled."""
    flat: dict[str, float] = {
        "pr_auc": result["pr_auc"],
        "base_rate": result["base_rate"],
        "n_rows": float(result["n_rows"]),
        "n_positives": float(result["n_positives"]),
    }
    for k, v in result["precision_at_k"].items():
        flat[f"precision_at_{k}"] = v
        flat[f"lift_at_{k}"] = result["lift_at_k"][k]
    for k, p in result.get("pattern", {}).items():
        flat[f"pattern_recall_at_{k}"] = p["recall"]
        flat[f"pattern_hit_rate_at_{k}"] = p["hit_rate"]
    for k, c in result.get("cost", {}).items():
        flat[f"value_missed_at_{k}"] = c["laundering_value_missed"]
    return flat


def main() -> int:
    df = load_split(SPLIT)
    y = df["is_laundering"].to_numpy()
    amounts = df["amount_paid"].to_numpy()
    pattern_ids = df["pattern_id"].to_numpy()

    baselines = {
        "random": rank_randomly(len(y), seed=SEED),
        "by_amount": rank_by_amount(amounts),
    }

    client, experiment_id = start_tracking()
    print(f"split: {SPLIT}   rows: {len(y):,}   positives: {int(y.sum()):,}\n")

    for name, scores in baselines.items():
        result = evaluate(
            y,
            scores,
            k_values=DEFAULT_K_VALUES,
            pattern_ids=pattern_ids,
            amounts=amounts,
        )

        log_run(
            experiment_id,
            params={"model": name, "split": SPLIT, "seed": str(SEED), "kind": "baseline"},
            metrics=_flatten(result),
            tags={"phase": "2", "baseline": "true"},
        )

        print(f"--- {name} ---")
        print(f"  PR-AUC {result['pr_auc']:.5f}   base rate {result['base_rate']:.5%}")
        for k in DEFAULT_K_VALUES:
            p = result["precision_at_k"][k]
            pat = result["pattern"][k]
            print(
                f"  k={k:<6} precision {p:8.5f}  lift {result['lift_at_k'][k]:6.2f}x"
                f"   rings caught {pat['n_caught']:>3}/{pat['n_patterns']}"
                f"   hit {pat['hit_rate']:.2%}"
            )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
