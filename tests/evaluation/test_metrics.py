"""The evaluation harness is tested hardest, because nothing downstream can
reveal that it is wrong.

If precision@k is subtly broken, every model in this project reports a wrong
number and every comparison between them is meaningless -- and the tests, the
training loop and the dashboards would all still look fine.
"""

import numpy as np
import pytest

from graphguard.evaluation.metrics import (
    pattern_recall,
    pr_auc,
    precision_at_k,
)

# ---------------------------------------------------------------- precision@k


@pytest.mark.unit
def test_precision_at_k_counts_positives_in_the_top_k():
    y = np.array([1, 0, 1, 0, 0])
    scores = np.array([0.9, 0.8, 0.7, 0.6, 0.5])
    # top 3 by score are indices 0,1,2 -> two positives
    assert precision_at_k(y, scores, 3) == pytest.approx(2 / 3)


@pytest.mark.unit
def test_perfect_ranking_scores_one():
    y = np.array([1, 1, 0, 0])
    scores = np.array([0.9, 0.8, 0.2, 0.1])
    assert precision_at_k(y, scores, 2) == 1.0


@pytest.mark.unit
def test_worst_ranking_scores_zero():
    y = np.array([1, 1, 0, 0])
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    assert precision_at_k(y, scores, 2) == 0.0


@pytest.mark.unit
def test_k_larger_than_the_data_uses_everything():
    y = np.array([1, 0])
    assert precision_at_k(y, np.array([0.9, 0.1]), 100) == pytest.approx(0.5)


@pytest.mark.unit
def test_k_of_zero_is_rejected():
    with pytest.raises(ValueError):
        precision_at_k(np.array([1, 0]), np.array([0.9, 0.1]), 0)


@pytest.mark.unit
def test_ties_do_not_depend_on_input_order():
    """All-equal scores must give the base rate, however the rows are ordered."""
    y = np.array([1, 0, 0, 0, 1, 0, 0, 0, 0, 0])
    scores = np.full(10, 0.5)
    first = precision_at_k(y, scores, 5)
    order = np.array([9, 8, 7, 6, 5, 4, 3, 2, 1, 0])
    second = precision_at_k(y[order], scores[order], 5)
    assert first == second


@pytest.mark.unit
def test_length_mismatch_is_rejected():
    with pytest.raises(ValueError):
        precision_at_k(np.array([1, 0]), np.array([0.9]), 1)


# -------------------------------------------------------------------- PR-AUC


@pytest.mark.unit
def test_pr_auc_is_one_for_a_perfect_ranking():
    y = np.array([1, 1, 0, 0])
    assert pr_auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(1.0)


@pytest.mark.unit
def test_pr_auc_of_random_scores_approaches_the_base_rate():
    rng = np.random.default_rng(0)
    y = np.zeros(10_000, dtype=int)
    y[:100] = 1  # 1% positives
    rng.shuffle(y)
    assert pr_auc(y, rng.random(10_000)) == pytest.approx(0.01, abs=0.01)


@pytest.mark.unit
def test_pr_auc_needs_at_least_one_positive():
    with pytest.raises(ValueError):
        pr_auc(np.zeros(5, dtype=int), np.random.default_rng(0).random(5))


# ----------------------------------------------------------- pattern recall


@pytest.mark.unit
def test_a_ring_needs_more_than_one_hop_to_count_as_caught():
    """Catching 1 transaction of a 4-hop ring is not catching the ring."""
    pattern_ids = np.array([1, 1, 1, 1])
    flagged = np.array([True, False, False, False])
    assert pattern_recall(pattern_ids, flagged, threshold=0.5)["recall"] == 0.0


@pytest.mark.unit
def test_a_ring_caught_above_threshold_counts():
    pattern_ids = np.array([1, 1, 1, 1])
    flagged = np.array([True, True, True, False])
    assert pattern_recall(pattern_ids, flagged, threshold=0.5)["recall"] == 1.0


@pytest.mark.unit
def test_recall_is_the_fraction_of_rings_caught():
    # ring 1 fully caught, ring 2 untouched
    pattern_ids = np.array([1, 1, 2, 2])
    flagged = np.array([True, True, False, False])
    assert pattern_recall(pattern_ids, flagged, threshold=0.5)["recall"] == 0.5


@pytest.mark.unit
def test_hit_rate_counts_rings_with_any_hop_flagged():
    """Separate, weaker measure: a human can pull the thread from one hop.

    Ring 1 is four hops with one flagged, so 25% -- below the 50% threshold,
    it is a hit but not a catch. Ring 2 is untouched. The two measures must
    therefore disagree, which is the point of reporting both.
    """
    pattern_ids = np.array([1, 1, 1, 1, 2, 2])
    flagged = np.array([True, False, False, False, False, False])
    out = pattern_recall(pattern_ids, flagged, threshold=0.5)
    assert out["hit_rate"] == 0.5
    assert out["recall"] == 0.0


@pytest.mark.unit
def test_denominator_is_reported():
    """FINDING-003: only 62% of laundering is in a labelled ring. The count of
    rings the metric is computed over must be visible, not implied."""
    pattern_ids = np.array([1, 1, 2, 2, 3, 3])
    flagged = np.array([True, True, False, False, True, True])
    out = pattern_recall(pattern_ids, flagged, threshold=0.5)
    assert out["n_patterns"] == 3
    assert out["n_caught"] == 2
