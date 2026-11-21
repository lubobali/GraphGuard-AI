"""Shadow scoring (S6.10): the challenger scores the champion's own inputs; the report is fair."""

import numpy as np
import pytest

from graphguard.stream import shadow as sh

pytestmark = pytest.mark.unit


class Bundle:
    def score_rows(self, rows):
        return [r["a"] * 2 + r["b"] for r in rows]


def test_the_challenger_scores_exactly_the_champions_feature_vector():
    payloads = [{"event_id": 1, "score": 0.5, "features": [0.1, 0.2], "feature_names": ["a", "b"]}]
    (s,) = sh.score_payloads(Bundle(), payloads)
    assert s == {"event_id": 1, "score": 0.1 * 2 + 0.2, "champion_score": 0.5}


def test_identical_models_agree_perfectly():
    rows = [(i, i / 100, i / 100, None, "warm") for i in range(200)]
    r = sh.compare(rows)
    assert r["rank_correlation"] == 1.0 and r["top_k_overlap"] == 1.0
    assert r["mean_abs_score_diff"] == 0.0


def test_reversed_models_disagree_and_labels_decide_who_is_better():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(1000):
        lab = bool(rng.random() < 0.1)
        champ = 0.9 if lab else rng.random() * 0.5  # champion finds the positives
        rows.append((i, champ, 1 - champ, lab, "warm" if i % 2 else "scored: sender new"))
    r = sh.compare(rows)
    assert r["rank_correlation"] < 0 and r["top_k_overlap"] == 0.0
    assert r["champion_precision_top20pct_labelled"] > r["challenger_precision_top20pct_labelled"]
    assert "biased" in r["labelled_note"]
    assert set(r["by_segment"]) == {"warm", "scored: sender new"}


def test_unlabelled_rows_are_compared_but_never_counted_as_negatives():
    rows = [(1, 0.9, 0.8, None, "warm"), (2, 0.1, 0.2, True, "warm"), (3, 0.5, 0.4, None, "warm")]
    r = sh.compare(rows)
    assert r["n"] == 3 and r["labelled"] == 1


def test_an_empty_stream_reports_nothing():
    assert sh.compare([]) == {"n": 0}
