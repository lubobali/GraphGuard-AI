"""The two dumb baselines every model must beat.

They exist to make "the model works" falsifiable. A GNN that beats nothing is
not evidence of anything, and a surprising number of published results quietly
fail to clear these.

**random** -- the floor. Its precision@k is the base rate, by definition.

**by amount** -- the naive intuition an analyst would reach for first: big
transfers are suspicious. If this does well, the dataset's patterns are too
obvious and the project needs the harder LI variant (see PLAN.md, "the
synthetic data turns out to be too easy").
"""

from __future__ import annotations

import numpy as np


def rank_randomly(n: int, seed: int) -> np.ndarray:
    """Random scores. Seeded, because an unreproducible baseline is not one."""
    return np.random.default_rng(seed).random(n)


def rank_by_amount(amounts: np.ndarray) -> np.ndarray:
    """Score by transfer size. Bigger is ranked as more suspicious."""
    return np.asarray(amounts, dtype=float)
