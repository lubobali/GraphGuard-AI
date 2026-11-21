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


# --- S6.11: what the soak found -------------------------------------------------------
def test_a_record_that_is_not_a_decision_is_skipped_not_fatal():
    # a non-JSON record in `decisions` crash-looped the shadow pod during the soak
    good = b'{"event_id": 1, "score": 0.5, "features": [0.1], "feature_names": ["a"]}'
    payloads, skipped = sh.decode([b"probe", good, b'{"event_id": 2}', b"[1, 2]"])
    assert [p["event_id"] for p in payloads] == [1] and skipped == 3


def test_a_lost_position_restarts_from_the_oldest_record_never_the_newest():
    # Kafka's default ("latest") silently skipped 1,021 decisions after a restart; the
    # shadow's writes are idempotent (ON CONFLICT DO NOTHING), so re-reading is safe.
    cfg = sh.kafka_config({"bootstrap.servers": "127.0.0.1:1"})
    assert cfg["auto.offset.reset"] == "earliest" and cfg["enable.auto.commit"] is False
