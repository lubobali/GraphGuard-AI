"""OpenLineage events for every lakehouse job (S5.6e).

    with lineage_run("lakehouse-build") as run:
        ...                                  # the job's work
        run.read("silver.transactions", snapshot_id)
        run.wrote("gold.labels", snapshot_id)

Each run emits START, then COMPLETE with its input and output datasets -- each
pinned to the Iceberg snapshot id it read or wrote (a `datasetVersion` facet) -- or
FAIL with the error. Events are OpenLineage's standard JSON, appended one per line to
`lakehouse/lineage/events.jsonl` (no service: Marquez OOMs on this box). `just lineage`
prints the graph; a training run also logs its events to its MLflow run.

This answers "which data trained this model?" from a record, in the format Marquez,
DataHub, Atlan or Databricks' lineage UI can import.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from openlineage.client import OpenLineageClient
from openlineage.client.event_v2 import InputDataset, Job, OutputDataset, Run, RunEvent, RunState
from openlineage.client.facet_v2 import dataset_version_dataset, error_message_run
from openlineage.client.transport.file import FileConfig, FileTransport

from graphguard.config import REPO_ROOT

LINEAGE_FILE = REPO_ROOT / "lakehouse" / "lineage" / "events.jsonl"
JOB_NAMESPACE = "graphguard"
ICEBERG_NAMESPACE = "iceberg://lakekeeper/graphguard"
PRODUCER = "https://github.com/lubobali/GraphGuard-AI"


@dataclass
class LineageRun:
    job: str
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    inputs: dict[tuple[str, str], str | None] = field(default_factory=dict)
    outputs: dict[tuple[str, str], str | None] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    def read(self, table: str, snapshot_id: int | None, namespace: str = ICEBERG_NAMESPACE):
        self.inputs[(namespace, table)] = None if snapshot_id is None else str(snapshot_id)

    def wrote(self, table: str, snapshot_id: int | None, namespace: str = ICEBERG_NAMESPACE):
        self.outputs[(namespace, table)] = None if snapshot_id is None else str(snapshot_id)


def _facets(version: str | None) -> dict:
    return (
        {}
        if version is None
        else {"version": dataset_version_dataset.DatasetVersionDatasetFacet(datasetVersion=version)}
    )


def _event(run: LineageRun, state: RunState, error: BaseException | None = None) -> RunEvent:
    run_facets = {}
    if error is not None:
        # Type and message only, never a traceback with locals.
        run_facets["errorMessage"] = error_message_run.ErrorMessageRunFacet(
            message=f"{type(error).__name__}: {str(error)[:300]}", programmingLanguage="python"
        )
    done = state is not RunState.START
    return RunEvent(
        eventType=state,
        eventTime=dt.datetime.now(dt.UTC).isoformat(),
        producer=PRODUCER,
        run=Run(runId=run.run_id, facets=run_facets),
        job=Job(namespace=JOB_NAMESPACE, name=run.job),
        inputs=[
            InputDataset(namespace=ns, name=n, facets=_facets(v))
            for (ns, n), v in sorted(run.inputs.items())
        ]
        if done
        else [],
        outputs=[
            OutputDataset(namespace=ns, name=n, facets=_facets(v))
            for (ns, n), v in sorted(run.outputs.items())
        ]
        if done
        else [],
    )


@contextmanager
def lineage_run(job: str, path: Path = LINEAGE_FILE) -> Iterator[LineageRun]:
    """Wrap one job run: START now, COMPLETE or FAIL when the block ends."""
    path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenLineageClient(
        transport=FileTransport(FileConfig(log_file_path=str(path), append=True))
    )
    run = LineageRun(job)

    def emit(event: RunEvent) -> None:
        client.emit(event)
        run.events.append(json.loads(json.dumps(event, default=_jsonable)))

    emit(_event(run, RunState.START))
    try:
        yield run
    except BaseException as e:
        emit(_event(run, RunState.FAIL, e))
        raise
    emit(_event(run, RunState.COMPLETE))


def _jsonable(o):
    import attr

    return attr.asdict(o, filter=lambda a, v: v is not None) if attr.has(type(o)) else str(o)


def read_events(path: Path = LINEAGE_FILE) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def latest_runs(events: list[dict]) -> dict[str, dict]:
    """The newest finished (COMPLETE or FAIL) event per job."""
    out: dict[str, dict] = {}
    for e in events:
        if e.get("eventType") in ("COMPLETE", "FAIL"):
            job = e["job"]["name"]
            if job not in out or e["eventTime"] >= out[job]["eventTime"]:
                out[job] = e
    return out


def _ds(d: dict) -> str:
    v = d.get("facets", {}).get("version", {}).get("datasetVersion")
    return f"{d['name']}" + (f" @{v}" if v else "")


def main() -> int:
    runs = latest_runs(read_events())
    if not runs:
        print(f"no lineage yet ({LINEAGE_FILE.relative_to(REPO_ROOT)})")
        return 0
    for job, e in sorted(runs.items(), key=lambda kv: kv[1]["eventTime"]):
        print(f"{e['eventTime'][:19]}  {job}  [{e['eventType']}]  run {e['run']['runId'][:8]}")
        for d in e.get("inputs", []):
            print(f"    in   {_ds(d)}")
        for d in e.get("outputs", []):
            print(f"    out  {_ds(d)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
