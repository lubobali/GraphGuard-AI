"""Why this alert (S7.4): one plain sentence per feature, never a summed amount."""

import math

import pytest

from graphguard.demo import reasons as R

pytestmark = pytest.mark.unit

FEATURES = ["hour", "weekday", "log_amount", "amount_ratio", "is_same_bank",
            "payment_currency_code", "sender_n_sent_before", "sender_amount_sent_before",
            "sender_distinct_out_before", "sender_sent_last_24h",
            "sender_seconds_since_last_send", "receiver_n_received_before",
            "receiver_amount_received_before", "receiver_distinct_in_before",
            "in_out_ratio_before"]  # fmt: skip
TX = {"amount_paid": 9500.0, "payment_currency": "US Dollar", "amount_received": 9500.0,
      "receiving_currency": "US Dollar", "payment_format": "ACH"}  # fmt: skip
VALUES = dict(zip(FEATURES, [14, 3, math.log1p(9500), 1.0, 0, 12, 42, 1.2e9, 17, 9,
                             3700.0, 3, 5.5e6, 2, 0.1], strict=True))  # fmt: skip
PCT = {"sender_amount_sent_before": 97.5, "receiver_amount_received_before": 40.0}


def test_every_model_feature_has_a_sentence():
    from graphguard.config import REPO_ROOT
    from graphguard.serving.model_bundle import ModelBundle

    assert set(R.TEMPLATES) == set(FEATURES)
    bundle_dir = REPO_ROOT / "models" / "production"
    if (bundle_dir / "metadata.json").exists():  # the served model has no feature without one
        assert set(ModelBundle.load(bundle_dir).feature_columns) <= set(R.TEMPLATES)


@pytest.mark.parametrize("feature", FEATURES)
def test_each_sentence_is_plain_and_never_prints_a_summed_amount(feature):
    text = R.sentence(feature, VALUES[feature], TX, PCT)
    assert text and text[0].isupper() and text.endswith(".")
    assert "1,200,000,000" not in text and "5,500,000" not in text  # the mixed-currency sums
    assert "1.2e" not in text and "e+0" not in text


def test_sums_are_said_as_a_share_of_the_window():
    assert "97%" in R.sentence("sender_amount_sent_before", 1.2e9, TX, PCT)


def test_counts_timings_and_currencies_read_naturally():
    assert "9 payments in the 24 hours" in R.sentence("sender_sent_last_24h", 9, TX, PCT)
    assert "1 hour" in R.sentence("sender_seconds_since_last_send", 3700.0, TX, PCT)
    assert "9,500.00 US Dollar" in R.sentence("log_amount", VALUES["log_amount"], TX, PCT)
    assert "different banks" in R.sentence("is_same_bank", 0, TX, PCT)


def test_never_sent_before_reads_correctly():
    assert "never" in R.sentence("sender_seconds_since_last_send", float("nan"), TX, PCT)


def test_top_three_are_the_largest_upward_pushes():
    contribs = {"hour": 0.1, "sender_sent_last_24h": 2.0, "is_same_bank": -3.0,
                "receiver_distinct_in_before": 0.9, "weekday": 0.5}  # fmt: skip
    assert R.top_features(contribs, n=3) == ["sender_sent_last_24h",
                                             "receiver_distinct_in_before", "weekday"]  # fmt: skip


def test_rule_hits_are_said_in_the_rules_own_words():
    from graphguard.stream.rules import RULES

    assert set(R.RULE_TEXT) == set(RULES)
    assert "9,000" in R.RULE_TEXT["structuring"]


def test_the_weekday_reason_says_it_is_a_simulator_pattern():
    text = R.sentence("weekday", 3, TX, PCT)
    assert "Wednesday" in text and "simulator" in text and "FINDING-018" in text
