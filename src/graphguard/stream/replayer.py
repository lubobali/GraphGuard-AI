"""The replayer (S6.5): sends the validation window into Kafka like a live bank would.

    python -m graphguard.stream.replayer --run demo --speed 600            # 10 min of data per s
    python -m graphguard.stream.replayer --run chaos --speed max --faults chaos

Only the validation window (`train_end <= t < val_end`, from silver), in training's order
(time, then `source_row`). The data is IBM's synthetic AMLworld: we imitate the **arrival**,
not the data.

**Pacing:** true time (`--speed 1`), accelerated (`--speed 600`), or `max`. Bursts compress
wall-clock gaps for a stretch of event time (paydays) -- event time itself never changes.

**Seeded real-world mess** (`Faults`), every one written to the run's fault log: duplicates
(the same event sent again a little later), late / out-of-order events (sent up to N
positions late), malformed records, and a schema change mid-stream (v2 adds a field). Faults
touch *delivery* only -- never event time, never labels (the message has none).

**Restart-safe:** after each flushed batch the next position is written to a checkpoint; a
restarted replayer resumes there. Kafka's idempotence removes duplicates only within one
producer session, so a restart may re-send up to one batch -- the consumer drops repeats by
`event_id` (S6.3, S6.6).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from graphguard.config import REPO_ROOT
from graphguard.stream import messages

RUNS = REPO_ROOT / "stream-runs"
TOPIC = "transactions"
_GARBAGE = (b"", b"not json at all", b"[1,2,3]", b'{"schema_version": 1, "event_id": "x"}',
            b'{"schema_version": 7}')  # fmt: skip


@dataclass(frozen=True)
class Faults:
    duplicate: float = 0.0
    late: float = 0.0
    late_max_shift: int = 20  # positions; the consumer's reorder buffer must be larger
    malformed: float = 0.0
    schema_v2_from: float | None = None  # fraction of the run where v2 messages start
    seed: int = 0


CHAOS = Faults(duplicate=0.01, late=0.01, late_max_shift=50, malformed=0.001,
               schema_v2_from=0.5, seed=42)  # fmt: skip


@dataclass(frozen=True)
class Send:
    kind: str  # event | duplicate | malformed
    index: int  # the row it belongs to
    schema_version: int = 1
    garbage: bytes = b""


@dataclass
class Plan:
    rows: object  # list of dicts, or a polars DataFrame
    sends: list[Send]
    log: list[dict] = field(default_factory=list)

    def row(self, i: int) -> dict:
        r = self.rows
        return r[i] if isinstance(r, list) else r.row(i, named=True)

    def body(self, s: Send) -> bytes:
        if s.kind == "malformed":
            return s.garbage
        return messages.encode(self.row(s.index), seq=s.index, schema_version=s.schema_version)

    def time(self, s: Send) -> dt.datetime:
        return self.row(s.index)["timestamp"]


def _n(rows) -> int:
    return len(rows) if isinstance(rows, list) else rows.height


def plan(rows, faults: Faults) -> Plan:
    """Where each send goes, deterministically for a seed. Pure."""
    rng = random.Random(faults.seed)
    n = _n(rows)
    v2_from = int(n * faults.schema_v2_from) if faults.schema_v2_from is not None else n
    keyed: list[tuple[float, Send]] = []
    log: list[dict] = []
    if v2_from < n:
        log.append({"fault": "schema_v2", "from_seq": v2_from})
    for i in range(n):
        version = 2 if i >= v2_from else 1
        key = float(i)
        if faults.late and rng.random() < faults.late:
            shift = rng.randint(1, faults.late_max_shift)
            key = i + shift + 0.5
            log.append({"fault": "late", "seq": i, "shift": shift})
        keyed.append((key, Send("event", i, version)))
        if faults.duplicate and rng.random() < faults.duplicate:
            shift = rng.randint(1, faults.late_max_shift)
            keyed.append((i + shift + 0.75, Send("duplicate", i, version)))
            log.append({"fault": "duplicate", "seq": i, "shift": shift})
        if faults.malformed and rng.random() < faults.malformed:
            keyed.append((i + 0.25, Send("malformed", i, garbage=rng.choice(_GARBAGE))))
            log.append({"fault": "malformed", "after_seq": i})
    keyed.sort(key=lambda kv: kv[0])
    return Plan(rows, [s for _, s in keyed], log)


Burst = tuple[dt.datetime, dt.datetime, float]  # (start, end, wall-clock speed-up)


def send_offsets(
    times: list[dt.datetime], speed: float | None, bursts: list[Burst] | None = None
) -> list[float]:
    """Seconds after the start at which each send goes out. Event time is not changed."""
    if speed is None:
        return [0.0] * len(times)
    out, total = [], 0.0
    for i, t in enumerate(times):
        if i:
            gap = max(0.0, (t - times[i - 1]).total_seconds()) / speed
            for start, end, factor in bursts or ():
                if start <= t < end:
                    gap /= factor
            total += gap
        out.append(total)
    return out


def _save(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data) + "\n")
    tmp.replace(path)


def send(p: Plan, producer, checkpoint: Path, speed: float | None, batch: int = 500,
         bursts=None, topic: str = TOPIC) -> int:  # fmt: skip
    """Send from the checkpoint on; returns how many were sent in this call."""
    start = json.loads(checkpoint.read_text())["next"] if checkpoint.exists() else 0
    if start >= len(p.sends):
        return 0
    offsets = send_offsets([p.time(s) for s in p.sends], speed, bursts)
    wall0 = time.monotonic() - offsets[start]  # a resumed run keeps its pacing
    errors: list = []

    def delivered(err, _msg):
        if err is not None:
            errors.append(err)

    sent = 0
    for b in range(start, len(p.sends), batch):
        for i in range(b, min(b + batch, len(p.sends))):
            if (wait := wall0 + offsets[i] - time.monotonic()) > 0:
                time.sleep(wait)
            s = p.sends[i]
            key = str(p.row(s.index)["source_row"]).encode()
            while True:
                try:
                    producer.produce(topic, p.body(s), key=key, on_delivery=delivered)
                    break
                except BufferError:
                    producer.poll(0.1)
            producer.poll(0)
            sent += 1
        producer.flush(60)
        if errors:
            raise RuntimeError(f"Kafka refused {len(errors)} records: {errors[0]}")
        _save(checkpoint, {"next": min(b + batch, len(p.sends)), "total": len(p.sends)})
    return sent


# --- the job ---------------------------------------------------------------------------
def load_rows(limit: int | None = None):
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.tables import assert_in_validation, validation_stream

    boundaries = frozen_boundaries()
    lf = validation_stream(open_catalog("reader"), boundaries)
    df = (lf.head(limit) if limit else lf).collect()
    assert_in_validation(df, boundaries)  # never training data, never the sealed window
    return df


def main(argv: list[str]) -> int:
    from confluent_kafka import Producer

    from graphguard.stream import kafka_admin as ka

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run name: checkpoint + fault log live here")
    ap.add_argument("--speed", default="600", help="1 = true time; 600; max")
    ap.add_argument("--faults", choices=("none", "chaos"), default="none")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv[1:])
    speed = None if args.speed == "max" else float(args.speed)
    faults = CHAOS if args.faults == "chaos" else Faults()
    if args.seed is not None:
        faults = Faults(**{**faults.__dict__, "seed": args.seed})

    run_dir = RUNS / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rows = load_rows(args.limit)
    p = plan(rows, faults)
    (run_dir / "faults.jsonl").write_text("".join(json.dumps(e) + "\n" for e in p.log))
    (run_dir / "run.json").write_text(json.dumps({
        "rows": rows.height, "sends": len(p.sends), "speed": args.speed,
        "faults": faults.__dict__, "first": str(rows["timestamp"].min()),
        "last": str(rows["timestamp"].max()),
    }) + "\n")  # fmt: skip
    print(f"plan: {rows.height:,} events, {len(p.sends):,} sends, {len(p.log)} faults "
          f"({time.time() - t0:.1f}s)", flush=True)  # fmt: skip
    producer = Producer({**ka.client_config("replayer"), **ka.PRODUCER})
    n = send(p, producer, run_dir / "checkpoint.json", speed)
    print(f"sent {n:,} ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
