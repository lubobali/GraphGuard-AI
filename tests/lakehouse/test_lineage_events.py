"""OpenLineage events (S5.6e): shape, failure handling, and the graph -- no services."""

import json

import pytest

from graphguard.lakehouse.lineage_events import latest_runs, lineage_run, read_events

pytestmark = pytest.mark.unit


def test_a_run_emits_start_then_complete_with_versioned_datasets(tmp_path):
    path = tmp_path / "events.jsonl"
    with lineage_run("build", path) as run:
        run.read("silver.transactions", 11)
        run.wrote("gold.labels", 22)
    start, done = read_events(path)
    assert (start["eventType"], done["eventType"]) == ("START", "COMPLETE")
    assert start["run"]["runId"] == done["run"]["runId"]
    assert start["inputs"] == [] and start["outputs"] == []  # known only at the end
    (i,), (o,) = done["inputs"], done["outputs"]
    assert (i["name"], i["facets"]["version"]["datasetVersion"]) == ("silver.transactions", "11")
    assert (o["name"], o["facets"]["version"]["datasetVersion"]) == ("gold.labels", "22")
    assert done["job"] == {"namespace": "graphguard", "name": "build", "facets": {}}


def test_a_failed_run_emits_fail_and_still_raises(tmp_path):
    path = tmp_path / "events.jsonl"
    with pytest.raises(ValueError, match="boom"):
        with lineage_run("load", path):
            raise ValueError("boom")
    start, fail = read_events(path)
    assert fail["eventType"] == "FAIL"
    assert fail["run"]["facets"]["errorMessage"]["message"] == "ValueError: boom"


def test_the_error_message_is_bounded(tmp_path):
    path = tmp_path / "events.jsonl"
    with pytest.raises(RuntimeError):
        with lineage_run("x", path):
            raise RuntimeError("y" * 5000)
    assert len(read_events(path)[-1]["run"]["facets"]["errorMessage"]["message"]) < 400


def test_runs_append_and_the_graph_keeps_the_newest_per_job(tmp_path):
    path = tmp_path / "events.jsonl"
    for sid in (1, 2):
        with lineage_run("build", path) as run:
            run.wrote("silver.transactions", sid)
    events = read_events(path)
    assert len(events) == 4  # append, never overwrite
    newest = latest_runs(events)["build"]
    assert newest["outputs"][0]["facets"]["version"]["datasetVersion"] == "2"


def test_an_unversioned_dataset_has_no_version_facet(tmp_path):
    path = tmp_path / "events.jsonl"
    with lineage_run("store-load", path) as run:
        run.wrote("db0/gg:acct", None, namespace="redis://127.0.0.1:6380")
    (o,) = read_events(path)[-1]["outputs"]
    assert o["namespace"] == "redis://127.0.0.1:6380" and "version" not in o.get("facets", {})


def test_events_carry_only_what_the_job_recorded(tmp_path):
    path = tmp_path / "events.jsonl"
    with lineage_run("build", path) as run:
        run.read("silver.transactions", 1)
    text = path.read_text()
    for leak in ("secret", "credential", "s3.access-key-id", "Bearer"):
        assert leak not in text, leak
    assert read_events(tmp_path / "missing.jsonl") == []
    assert json.loads(text.splitlines()[0])["producer"]
