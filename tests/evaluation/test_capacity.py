"""The capacity curve (S7.3) must equal the one entry point, k by k."""

import numpy as np
import pytest

from graphguard.evaluation.capacity import capacity_curve
from graphguard.evaluation.evaluate import DEFAULT_K_VALUES, NO_PATTERN, evaluate

pytestmark = pytest.mark.unit


def _data(seed=0, n=20_000):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.02).astype(int)
    scores = rng.permutation(n).astype(float)  # a strict ranking, like the queue's
    pids = np.full(n, NO_PATTERN)
    pos = np.flatnonzero(y)
    pids[pos] = rng.integers(0, 60, size=len(pos))  # rings of uneven size
    return y, scores, pids


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_curve_equals_evaluate_at_the_default_and_random_ks(seed):
    y, s, pids = _data(seed)
    curve = capacity_curve(y, s, pids, max_k=5_000)
    ks = sorted(set(DEFAULT_K_VALUES) | set(np.random.default_rng(seed).integers(1, 5_001, 20)))
    ref = evaluate(y, s, k_values=tuple(int(k) for k in ks), pattern_ids=pids)
    for k in ks:
        row = curve[k - 1]
        assert row["k"] == k
        # evaluate() derives counts as precision x k: equal up to float rounding
        assert row["caught"] == pytest.approx(ref["caught_at_k"][k], abs=1e-9)
        assert row["missed"] == pytest.approx(ref["missed_at_k"][k], abs=1e-9)
        assert row["precision"] == pytest.approx(ref["precision_at_k"][k], abs=1e-12)
        assert row["recall"] == pytest.approx(ref["recall_at_k"][k], abs=1e-12)
        assert row["rings_caught"] == ref["pattern"][k]["n_caught"]
        assert row["rings_touched"] == round(ref["pattern"][k]["hit_rate"] * row["rings_total"])
        assert row["rings_total"] == ref["pattern"][k]["n_patterns"]


def test_the_curve_only_grows():
    y, s, pids = _data(3)
    curve = capacity_curve(y, s, pids, max_k=3_000)
    for col in ("caught", "rings_caught", "rings_touched"):
        vals = [r[col] for r in curve]
        assert vals == sorted(vals)


def test_a_ring_is_caught_at_half_its_hops_and_touched_at_one():
    y = np.array([1, 1, 1, 1, 0, 0])
    s = np.array([6.0, 1.0, 5.0, 0.5, 4.0, 3.0])  # order: 0, 2, 4, 5, 1, 3
    pids = np.array([7, 7, 7, 7, NO_PATTERN, NO_PATTERN])
    curve = capacity_curve(y, s, pids, max_k=6)
    assert [r["rings_touched"] for r in curve] == [1, 1, 1, 1, 1, 1]
    assert [r["rings_caught"] for r in curve] == [0, 1, 1, 1, 1, 1]  # 2 of 4 hops at k=2
