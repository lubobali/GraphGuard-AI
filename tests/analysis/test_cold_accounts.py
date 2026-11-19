"""The cold-account measurement (S5.5): groups and queue recall are computed right."""

import numpy as np
import pytest

from graphguard.analysis.cold_accounts import group_of, queue_recall

pytestmark = pytest.mark.unit


def test_groups():
    assert group_of(False, False) == "warm"
    assert group_of(True, False) == "sender cold"
    assert group_of(False, True) == "receiver cold"
    assert group_of(True, True) == "both cold"


def test_queue_recall_counts_weighted_rows_against_k():
    scores = np.array([0.9, 0.8, 0.7, 0.1])
    labels = np.array([1, 1, 0, 1])
    weights = np.array([1.0, 1.0, 1.0, 1.0])
    groups = np.array(["warm", "cold", "warm", "cold"])
    # top-2: the 0.9 warm launderer and the 0.8 cold launderer; the 0.1 cold one is out
    assert queue_recall(scores, labels, weights, groups, k=2) == {"cold": 0.5, "warm": 1.0}


def test_a_sampled_warm_row_takes_its_weight_of_queue_places():
    scores = np.array([0.9, 0.5])
    labels = np.array([0, 1])
    weights = np.array([10.0, 1.0])  # one sampled warm row stands for ten
    groups = np.array(["warm", "cold"])
    assert queue_recall(scores, labels, weights, groups, k=5)["cold"] == 0.0
