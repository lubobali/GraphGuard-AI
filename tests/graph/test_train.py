"""The training loop must score every row it is asked to, in order.

Scores are written back by row id, and a bug there would silently misalign
scores from labels -- which would not crash, would not fail a test elsewhere,
and would make every metric meaningless.
"""

import datetime as dt

import polars as pl
import pytest
import torch

from graphguard.graph.train import make_model, run_epoch

T0 = dt.datetime(2022, 9, 1)


def _rows(n_days=3, per_day=12):
    rows = []
    for d in range(n_days):
        for i in range(per_day):
            rows.append(
                {
                    "timestamp": T0 + dt.timedelta(days=d, minutes=i),
                    "from_account": f"A{i % 5}",
                    "to_account": f"B{i % 4}",
                    "amount_paid": 100.0 + i,
                    "log_amount": 4.6,
                    "hour": 12,
                    "is_same_bank": 0,
                    "amount_ratio": 1.0,
                    "is_laundering": 1 if i == 0 else 0,
                }
            )
    return pl.DataFrame(rows).lazy()


DAYS = [(T0 + dt.timedelta(days=d)).date() for d in range(3)]


@pytest.mark.unit
def test_eval_pass_scores_every_row():
    model = make_model(hidden=8, dropout=0.0, seed=1)
    _, scores, labels = run_epoch(model, _rows(), DAYS, batch_size=8)
    assert len(scores) == 36
    assert len(labels) == 36


@pytest.mark.unit
def test_scores_are_probabilities():
    model = make_model(hidden=8, dropout=0.0, seed=1)
    _, scores, _ = run_epoch(model, _rows(), DAYS, batch_size=8)
    assert scores.min() >= 0.0
    assert scores.max() <= 1.0


@pytest.mark.unit
def test_labels_come_back_aligned_with_the_source_rows():
    """Three positives, one per day, must survive the round trip."""
    _, _, labels = run_epoch(make_model(8, 0.0, 1), _rows(), DAYS, batch_size=8)
    assert labels.sum() == 3


@pytest.mark.unit
def test_training_changes_the_weights():
    model = make_model(hidden=8, dropout=0.0, seed=1)
    before = model.head[0].weight.detach().clone()
    opt = torch.optim.Adam(model.parameters(), lr=0.05)
    run_epoch(model, _rows(), DAYS, optimizer=opt, batch_size=8, pos_weight=10.0)
    assert not torch.allclose(before, model.head[0].weight)


@pytest.mark.unit
def test_evaluation_never_subsamples():
    """max_rows_per_day is a training-only shortcut. If it applied at
    evaluation time the metric would be computed over a different population
    than the one reported."""
    _, scores, _ = run_epoch(make_model(8, 0.0, 1), _rows(), DAYS, batch_size=8, max_rows_per_day=4)
    # no optimizer -> evaluation -> every row still scored
    assert len(scores) == 36


@pytest.mark.unit
def test_a_day_with_no_rows_is_skipped_not_crashed():
    days = [*DAYS, (T0 + dt.timedelta(days=99)).date()]
    _, scores, _ = run_epoch(make_model(8, 0.0, 1), _rows(), days, batch_size=8)
    assert len(scores) == 36
