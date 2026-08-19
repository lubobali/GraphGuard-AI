"""Metrics. The most load-bearing code in the project.

If any of this is subtly wrong, every model reports a wrong number, every
comparison between models is meaningless, and nothing downstream would reveal
it -- training still converges, dashboards still render, tests still pass.
So this module is small, dependency-light where the semantics are ours, and
tested harder than anything else.

**precision@k is primary, not AUC.** At a 0.1% base rate a model can score
0.99 AUC and still hand investigators a worthless queue. precision@k asks the
only question that matters operationally: of the k accounts we told a human to
look at, how many were really laundering? k is investigator capacity.

**Pattern recall is reported two ways**, because "did we catch the ring" has
two honest readings:

- `recall` -- the ring counts as caught only if at least `threshold` of its
  hops are flagged. Catching 1 transaction in a 12-hop ring is not catching
  the ring.
- `hit_rate` -- the ring counts if *any* hop is flagged. Weaker, but it is what
  an investigator needs to start pulling the thread.

Both are reported. Quoting only the flattering one would be the kind of thing
this project exists to avoid.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score


def _validate(y_true: np.ndarray, scores: np.ndarray) -> None:
    if len(y_true) != len(scores):
        raise ValueError(f"length mismatch: {len(y_true)} labels vs {len(scores)} scores")
    if len(y_true) == 0:
        raise ValueError("empty input")


def precision_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> float:
    """Fraction of the top-k highest-scored rows that are truly positive.

    Ties are broken by taking the mean over the tied group rather than by
    input order, so the result cannot change when rows are shuffled. A metric
    that depends on row order is a metric that silently disagrees with itself.
    """
    y_true = np.asarray(y_true)
    scores = np.asarray(scores, dtype=float)
    _validate(y_true, scores)

    if k <= 0:
        raise ValueError(f"k must be positive, got {k}")

    k = min(k, len(y_true))

    # Rank by score descending. For rows tied at the cut-off, take the expected
    # value: the positives among the tied group, prorated by how many of them
    # fit inside k.
    order = np.argsort(-scores, kind="stable")
    ranked_scores = scores[order]
    ranked_labels = y_true[order]

    cutoff = ranked_scores[k - 1]
    above = ranked_scores > cutoff
    tied = ranked_scores == cutoff

    hits_above = float(ranked_labels[above].sum())
    slots_left = k - int(above.sum())

    tied_labels = ranked_labels[tied]
    if len(tied_labels) and slots_left > 0:
        hits_tied = float(tied_labels.sum()) * slots_left / len(tied_labels)
    else:
        hits_tied = 0.0

    return (hits_above + hits_tied) / k


def pr_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Area under the precision-recall curve (average precision).

    Honest under heavy imbalance in a way ROC-AUC is not: at a 0.1% base rate
    ROC-AUC is dominated by the vast negative class.
    """
    y_true = np.asarray(y_true)
    scores = np.asarray(scores, dtype=float)
    _validate(y_true, scores)

    if y_true.sum() == 0:
        raise ValueError("PR-AUC is undefined with no positive examples")

    return float(average_precision_score(y_true, scores))


def pattern_recall(
    pattern_ids: np.ndarray,
    flagged: np.ndarray,
    threshold: float = 0.5,
) -> dict:
    """How many whole laundering rings were caught.

    `pattern_ids` and `flagged` are aligned arrays over the transactions that
    belong to a labelled ring. Transactions outside any ring are excluded by
    the caller -- see FINDING-003, only 62% of laundering is in a labelled
    pattern, and `n_patterns` makes that denominator visible rather than
    implied.
    """
    pattern_ids = np.asarray(pattern_ids)
    flagged = np.asarray(flagged, dtype=bool)
    _validate(pattern_ids, flagged)

    if not 0 < threshold <= 1:
        raise ValueError(f"threshold must be in (0, 1], got {threshold}")

    unique = np.unique(pattern_ids)
    caught = 0
    hit = 0

    for pid in unique:
        member = pattern_ids == pid
        share = float(flagged[member].sum()) / int(member.sum())
        if share >= threshold:
            caught += 1
        if share > 0:
            hit += 1

    n = len(unique)
    return {
        "n_patterns": n,
        "n_caught": caught,
        "recall": caught / n if n else 0.0,
        "hit_rate": hit / n if n else 0.0,
        "threshold": threshold,
    }
