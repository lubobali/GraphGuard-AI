"""Every model goes through one entry point, so every model is scored the
same way. These tests pin that contract."""

import numpy as np
import pytest

from graphguard.evaluation.baselines import rank_by_amount, rank_randomly
from graphguard.evaluation.evaluate import evaluate


@pytest.mark.unit
def test_evaluate_reports_every_requested_k():
    y = np.array([1, 0, 1, 0, 0, 0])
    s = np.array([0.9, 0.1, 0.8, 0.2, 0.3, 0.4])
    out = evaluate(y, s, k_values=(1, 2, 3))
    assert set(out["precision_at_k"]) == {1, 2, 3}
    assert out["precision_at_k"][2] == 1.0


@pytest.mark.unit
def test_evaluate_includes_pr_auc_and_base_rate():
    y = np.array([1, 0, 0, 0])
    out = evaluate(y, np.array([0.9, 0.1, 0.2, 0.3]), k_values=(1,))
    assert out["pr_auc"] == pytest.approx(1.0)
    assert out["base_rate"] == pytest.approx(0.25)
    assert out["n_rows"] == 4
    assert out["n_positives"] == 1


@pytest.mark.unit
def test_lift_compares_precision_to_the_base_rate():
    """precision@k of 1.0 at a 25% base rate is a lift of 4."""
    y = np.array([1, 0, 0, 0])
    out = evaluate(y, np.array([0.9, 0.1, 0.2, 0.3]), k_values=(1,))
    assert out["lift_at_k"][1] == pytest.approx(4.0)


@pytest.mark.unit
def test_pattern_metrics_appear_only_when_pattern_ids_are_given():
    y = np.array([1, 1, 0, 0])
    s = np.array([0.9, 0.8, 0.1, 0.2])
    assert "pattern" not in evaluate(y, s, k_values=(2,))
    out = evaluate(y, s, k_values=(2,), pattern_ids=np.array([7, 7, -1, -1]))
    assert out["pattern"][2]["n_patterns"] == 1


@pytest.mark.unit
def test_unlabelled_rows_are_excluded_from_pattern_metrics():
    """FINDING-003: rows with no ring (-1) must not become a phantom pattern."""
    y = np.array([1, 1, 1, 0])
    s = np.array([0.9, 0.8, 0.7, 0.1])
    out = evaluate(y, s, k_values=(3,), pattern_ids=np.array([7, 7, -1, -1]))
    assert out["pattern"][3]["n_patterns"] == 1


@pytest.mark.unit
def test_cost_reports_hours_and_value_missed():
    y = np.array([1, 1, 0, 0])
    s = np.array([0.9, 0.1, 0.2, 0.3])
    amounts = np.array([1000.0, 5000.0, 10.0, 10.0])
    out = evaluate(y, s, k_values=(1,), amounts=amounts, hours_per_alert=0.5)
    cost = out["cost"][1]
    assert cost["investigator_hours"] == pytest.approx(0.5)
    # the 5000 laundering row is ranked last, so it is missed
    assert cost["laundering_value_missed"] == pytest.approx(5000.0)
    assert cost["laundering_value_caught"] == pytest.approx(1000.0)


# ------------------------------------------------------------------ baselines


@pytest.mark.unit
def test_random_baseline_is_reproducible():
    a = rank_randomly(1000, seed=42)
    b = rank_randomly(1000, seed=42)
    assert np.array_equal(a, b)


@pytest.mark.unit
def test_random_baseline_changes_with_the_seed():
    assert not np.array_equal(rank_randomly(1000, seed=1), rank_randomly(1000, seed=2))


@pytest.mark.unit
def test_amount_baseline_ranks_bigger_amounts_higher():
    amounts = np.array([10.0, 5000.0, 300.0])
    scores = rank_by_amount(amounts)
    assert scores[1] > scores[2] > scores[0]


@pytest.mark.unit
def test_random_baseline_precision_sits_near_the_base_rate():
    """The floor any real model must clear."""
    rng = np.random.default_rng(0)
    y = np.zeros(100_000, dtype=int)
    y[:100] = 1
    rng.shuffle(y)
    out = evaluate(y, rank_randomly(len(y), seed=7), k_values=(1000,))
    assert out["precision_at_k"][1000] == pytest.approx(0.001, abs=0.002)
