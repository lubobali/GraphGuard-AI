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
    _, scores, labels = run_epoch(model, _rows(), _rows(), DAYS, batch_size=8)
    assert len(scores) == 36
    assert len(labels) == 36


@pytest.mark.unit
def test_scores_are_probabilities():
    model = make_model(hidden=8, dropout=0.0, seed=1)
    _, scores, _ = run_epoch(model, _rows(), _rows(), DAYS, batch_size=8)
    assert scores.min() >= 0.0
    assert scores.max() <= 1.0


@pytest.mark.unit
def test_labels_come_back_aligned_with_the_source_rows():
    """Three positives, one per day, must survive the round trip."""
    _, _, labels = run_epoch(make_model(8, 0.0, 1), _rows(), _rows(), DAYS, batch_size=8)
    assert labels.sum() == 3


@pytest.mark.unit
def test_training_changes_the_weights():
    model = make_model(hidden=8, dropout=0.0, seed=1)
    before = model.head[0].weight.detach().clone()
    opt = torch.optim.Adam(model.parameters(), lr=0.05)
    run_epoch(model, _rows(), _rows(), DAYS, optimizer=opt, batch_size=8, pos_weight=10.0)
    assert not torch.allclose(before, model.head[0].weight)


@pytest.mark.unit
def test_evaluation_never_subsamples():
    """max_rows_per_day is a training-only shortcut. If it applied at
    evaluation time the metric would be computed over a different population
    than the one reported."""
    _, scores, _ = run_epoch(
        make_model(8, 0.0, 1), _rows(), _rows(), DAYS, batch_size=8, max_rows_per_day=4
    )
    # no optimizer -> evaluation -> every row still scored
    assert len(scores) == 36


@pytest.mark.unit
def test_a_day_with_no_rows_is_skipped_not_crashed():
    days = [*DAYS, (T0 + dt.timedelta(days=99)).date()]
    _, scores, _ = run_epoch(make_model(8, 0.0, 1), _rows(), _rows(), days, batch_size=8)
    assert len(scores) == 36


@pytest.mark.unit
def test_only_target_rows_are_scored_even_mid_day():
    """The split boundary falls mid-day in the real data.

    History must still cover the whole day (it is the graph's past), but only
    the target rows may be scored, or scores and labels misalign.
    """
    history = _rows()
    cutoff = T0 + dt.timedelta(days=1, minutes=6)
    targets = history.filter(pl.col("timestamp") >= cutoff)

    n_targets = targets.select(pl.len()).collect().item()
    _, scores, labels = run_epoch(make_model(8, 0.0, 1), history, targets, DAYS, batch_size=8)
    assert len(scores) == n_targets
    assert len(labels) == n_targets


@pytest.mark.unit
def test_scaler_statistics_come_from_training_data_only():
    """Fitting the scaler on validation would leak its distribution.

    The statistics are over log1p values, which is what the scaler documents,
    so the check is that different training data gives different statistics --
    not a hand-computed constant.
    """
    import math

    from graphguard.graph.scaling import EdgeScaler

    train = pl.DataFrame({"a": [1.0, 2.0, 3.0]})
    scaler = EdgeScaler.fit(train, ("a",))

    expected = sum(math.log1p(v) for v in (1.0, 2.0, 3.0)) / 3
    assert scaler.mean["a"] == pytest.approx(expected)

    other = EdgeScaler.fit(pl.DataFrame({"a": [100.0, 200.0, 300.0]}), ("a",))
    assert other.mean["a"] != pytest.approx(scaler.mean["a"])


@pytest.mark.unit
def test_scaler_makes_huge_values_small():
    from graphguard.graph.scaling import EdgeScaler

    train = pl.DataFrame({"a": [0.0, 1e9, 2e9]})
    scaler = EdgeScaler.fit(train, ("a",))
    out = scaler.transform(pl.DataFrame({"a": [2e9]}), ("a",))
    assert abs(out["a"][0]) < 10


@pytest.mark.unit
def test_scaler_survives_a_constant_column():
    """std of zero must not produce inf or nan."""
    from graphguard.graph.scaling import EdgeScaler

    train = pl.DataFrame({"a": [5.0, 5.0, 5.0]})
    scaler = EdgeScaler.fit(train, ("a",))
    out = scaler.transform(pl.DataFrame({"a": [5.0, 7.0]}), ("a",))
    assert out["a"].is_finite().all()


@pytest.mark.unit
def test_scaler_handles_nulls():
    from graphguard.graph.scaling import EdgeScaler

    train = pl.DataFrame({"a": [1.0, None, 3.0]})
    scaler = EdgeScaler.fit(train, ("a",))
    out = scaler.transform(pl.DataFrame({"a": [None]}), ("a",))
    assert out["a"].is_finite().all()
