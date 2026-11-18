"""The feature matrix must be built the same way for train and for scoring.

Category encodings are fitted on the training window only. An encoding fitted
on all the data would let a validation-only category influence the mapping,
which is a small but real leak, and exactly the kind that is invisible.
"""

import polars as pl
import pytest

from graphguard.models.tabular import (
    FEATURE_COLUMNS,
    UNSEEN_CATEGORY,
    build_matrix,
    fit_category_maps,
)


def _df(formats, currencies=None):
    n = len(formats)
    currencies = currencies or ["US Dollar"] * n
    data = {
        c: [0] * n
        for c in FEATURE_COLUMNS
        if c not in ("payment_format_code", "payment_currency_code")
    }
    data["payment_format"] = formats
    data["payment_currency"] = currencies
    data["is_laundering"] = [0] * n
    return pl.DataFrame(data)


@pytest.mark.unit
def test_category_map_is_built_from_training_values():
    maps = fit_category_maps(_df(["ACH", "Cheque", "ACH"]))
    assert set(maps["payment_format"]) == {"ACH", "Cheque"}


@pytest.mark.unit
def test_unseen_category_gets_the_sentinel_not_a_new_code():
    """A format that never appeared in training must not invent a code."""
    maps = fit_category_maps(_df(["ACH"]))
    X, _ = build_matrix(_df(["Wire"]), maps)
    assert X["payment_format_code"][0] == UNSEEN_CATEGORY


@pytest.mark.unit
def test_encoding_is_stable_across_calls():
    maps = fit_category_maps(_df(["ACH", "Cheque", "Wire"]))
    first, _ = build_matrix(_df(["Cheque"]), maps)
    second, _ = build_matrix(_df(["Cheque"]), maps)
    assert first["payment_format_code"][0] == second["payment_format_code"][0]


@pytest.mark.unit
def test_matrix_has_exactly_the_declared_feature_columns():
    maps = fit_category_maps(_df(["ACH"]))
    X, _ = build_matrix(_df(["ACH"]), maps)
    assert list(X.columns) == list(FEATURE_COLUMNS)


@pytest.mark.unit
def test_label_is_not_in_the_feature_matrix():
    """The most basic leak of all, and worth an explicit test."""
    maps = fit_category_maps(_df(["ACH"]))
    X, _ = build_matrix(_df(["ACH"]), maps)
    assert "is_laundering" not in X.columns


@pytest.mark.unit
def test_labels_are_returned_separately():
    maps = fit_category_maps(_df(["ACH", "ACH"]))
    df = _df(["ACH", "ACH"]).with_columns(pl.Series("is_laundering", [0, 1]))
    _, y = build_matrix(df, maps)
    assert y.to_list() == [0, 1]
