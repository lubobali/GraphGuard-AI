"""The capacity curve (S7.3): what a team catches and misses at every workload k.

`evaluate()` is the one entry point and stays that. Calling it for each of 5,000 ks would
re-sort a million rows 5,000 times, so this computes the same quantities in one pass -- and
`tests/evaluation/test_capacity.py` holds it equal to `evaluate()`, k by k. It assumes a
strict ranking (no ties), which is what the queue's order is; with ties `evaluate()` prorates.

Rings are read both ways, as everywhere in this project (metrics.py): *caught* when at least
`threshold` of the ring's hops are in the top k, *touched* when any hop is.
"""

from __future__ import annotations

import math

import numpy as np

from graphguard.evaluation.evaluate import NO_PATTERN


def capacity_curve(
    y_true: np.ndarray,
    scores: np.ndarray,
    pattern_ids: np.ndarray,
    max_k: int = 5_000,
    threshold: float = 0.5,
) -> list[dict]:
    y = np.asarray(y_true).astype(int)
    scores = np.asarray(scores, dtype=float)
    pids = np.asarray(pattern_ids)
    if len(np.unique(scores)) != len(scores):
        raise ValueError("capacity_curve needs a strict ranking (ties: use evaluate())")
    n_pos = int(y.sum())
    order = np.argsort(-scores, kind="stable")
    position = np.empty(len(order), dtype=np.int64)
    position[order] = np.arange(len(order))
    caught = np.cumsum(y[order])

    # For each ring: the k at which it is first touched / first caught.
    labelled = pids != NO_PATTERN
    k_touch, k_caught = [], []
    for pid in np.unique(pids[labelled]):
        pos = np.sort(position[labelled & (pids == pid)])
        need = math.ceil(threshold * len(pos) - 1e-12)  # hops needed for "caught"
        k_touch.append(pos[0] + 1)
        k_caught.append(pos[need - 1] + 1)
    k_touch, k_caught = np.sort(k_touch), np.sort(k_caught)
    n_rings = len(k_touch)

    out = []
    for k in range(1, min(max_k, len(y)) + 1):
        c = int(caught[k - 1])
        out.append(
            {
                "k": k,
                "caught": c,
                "missed": n_pos - c,
                "precision": c / k,
                "recall": c / n_pos if n_pos else 0.0,
                "rings_caught": int(np.searchsorted(k_caught, k, side="right")),
                "rings_touched": int(np.searchsorted(k_touch, k, side="right")),
                "rings_total": n_rings,
            }
        )
    return out
