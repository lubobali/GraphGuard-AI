"""The single entry point every model is scored through.

One function, so no model can be measured slightly differently from another.
If a comparison between two models is to mean anything, both numbers have to
come out of the same code path -- not out of two notebooks that mostly agree.
"""

from __future__ import annotations

import numpy as np

from graphguard.evaluation.metrics import pattern_recall, pr_auc, precision_at_k

# Investigator capacity. k is how many alerts a team can actually work, so
# precision@k is reported across a plausible range rather than at one number
# pulled out of the air.
DEFAULT_K_VALUES = (50, 100, 500, 1_000, 5_000)

# Rows with no labelled ring carry this id and are excluded from pattern
# metrics. FINDING-003: 38% of laundering is in no labelled pattern.
NO_PATTERN = -1


def evaluate(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    k_values: tuple[int, ...] = DEFAULT_K_VALUES,
    pattern_ids: np.ndarray | None = None,
    amounts: np.ndarray | None = None,
    hours_per_alert: float = 0.5,
    pattern_threshold: float = 0.5,
) -> dict:
    """Score a ranking. Returns every metric this project reports.

    `scores` is a ranking signal, higher meaning more suspicious. It does not
    have to be a probability -- only the order matters.
    """
    y_true = np.asarray(y_true)
    scores = np.asarray(scores, dtype=float)

    n_rows = len(y_true)
    n_positives = int(y_true.sum())
    base_rate = n_positives / n_rows if n_rows else 0.0

    result: dict = {
        "n_rows": n_rows,
        "n_positives": n_positives,
        "base_rate": base_rate,
        "pr_auc": pr_auc(y_true, scores),
        "precision_at_k": {},
        "lift_at_k": {},
    }

    order = np.argsort(-scores, kind="stable")

    for k in k_values:
        k_eff = min(k, n_rows)
        p = precision_at_k(y_true, scores, k)
        result["precision_at_k"][k] = p
        # Lift: how many times better than picking at random.
        result["lift_at_k"][k] = (p / base_rate) if base_rate else float("nan")

        top = order[:k_eff]

        if pattern_ids is not None:
            ids = np.asarray(pattern_ids)
            labelled = ids != NO_PATTERN
            flagged = np.zeros(n_rows, dtype=bool)
            flagged[top] = True
            result.setdefault("pattern", {})[k] = pattern_recall(
                ids[labelled], flagged[labelled], threshold=pattern_threshold
            )

        if amounts is not None:
            amt = np.asarray(amounts, dtype=float)
            is_pos = y_true.astype(bool)
            caught = np.zeros(n_rows, dtype=bool)
            caught[top] = True
            result.setdefault("cost", {})[k] = {
                "investigator_hours": k_eff * hours_per_alert,
                "laundering_value_caught": float(amt[is_pos & caught].sum()),
                "laundering_value_missed": float(amt[is_pos & ~caught].sum()),
            }

    return result
