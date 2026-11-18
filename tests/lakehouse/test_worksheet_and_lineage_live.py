"""The worksheet and the lineage log on the real lakehouse (S5.6e).

Needs Dex, Lakekeeper and S3; CI skips by the explicit flag, reason printed.
"""

import datetime as dt
import importlib.util
import json
import os

import pytest

from graphguard.config import REPO_ROOT

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("GRAPHGUARD_SKIP_LAKEKEEPER_TESTS") == "1",
        reason="GRAPHGUARD_SKIP_LAKEKEEPER_TESTS=1 (no Dex/Lakekeeper in this environment)",
    ),
]


@pytest.fixture(scope="module")
def notebook_defs():
    spec = importlib.util.spec_from_file_location(
        "lakehouse_nb", REPO_ROOT / "notebooks" / "lakehouse.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _, defs = mod.app.run()
    return defs


def test_the_worksheet_runs_and_sees_only_silver_and_gold(notebook_defs):
    counts = dict(notebook_defs["counts"].iter_rows())
    assert counts["silver.transactions"] > 4_000_000
    assert counts["gold.account_features_asof"] == 512_705


def test_the_worksheet_never_reaches_the_test_window(notebook_defs):
    from graphguard.evaluation.dataset import frozen_boundaries

    _, val_end = frozen_boundaries()
    last_day = notebook_defs["per_day"]["day"].max()
    assert last_day <= val_end.date()
    assert all(d < val_end for d in notebook_defs["senders"]["last_seen"])


def test_the_worksheet_shows_training_and_strict_time_disagree_on_ties(notebook_defs):
    t = notebook_defs["ties"]
    assert (t["sent_before_training_rule"] != t["sent_before_strict_time"]).any()


def test_trainings_lineage_names_only_silver_and_never_sealed():
    from graphguard.lakehouse.lineage_events import latest_runs, read_events

    runs = latest_runs(read_events())
    if "build-artifacts" not in runs:
        pytest.skip("no training run recorded yet on this box (run `just build-artifacts`)")
    train = runs["build-artifacts"]
    assert train["eventType"] == "COMPLETE"
    assert [i["name"] for i in train["inputs"]] == ["silver.transactions"]
    assert "sealed" not in json.dumps(train)


def test_the_build_records_every_layer_with_a_snapshot():
    from graphguard.lakehouse.lineage_events import latest_runs, read_events

    build = latest_runs(read_events()).get("lakehouse-build")
    if build is None:
        pytest.skip("no build recorded yet on this box (run `just lakehouse-build`)")
    outs = {o["name"]: o["facets"]["version"]["datasetVersion"] for o in build["outputs"]}
    assert {"bronze.transactions_raw", "silver.transactions", "gold.labels"} <= set(outs)
    assert all(v.isdigit() for v in outs.values())
    assert dt.datetime.fromisoformat(build["eventTime"]) <= dt.datetime.now(dt.UTC)
