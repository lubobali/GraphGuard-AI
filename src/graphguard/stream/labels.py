"""Late labels (S6.9): the truth about a transaction arrives days or weeks after it.

In a bank, nobody knows at payment time whether it was laundering. A label appears later,
through one of two doors -- and most transactions never get one:

    investigation     an alert is worked by an investigator. Capacity is limited: each day
                      the top `capacity_per_day` alerts by queue priority (ADR 0007) are
                      investigated; the verdict arrives 1-14 days after the alert.
                      (Dal Pozzolo et al., IEEE TNNLS 2018: investigators check ~100 cards a
                      day; feedback within about a week.)
    external report   laundering the system missed is reported from outside -- another
                      bank, law enforcement, a SAR -- 30-60 days later. (US SAR deadline:
                      30 days after detection, at most 60; 31 CFR 1020.320.)

A transaction that was never alerted and never reported has NO label: unknown, not
innocent. The verdict is assumed correct (a simplification, said here).

`known_as_of(labels, t)` is the only way anything that learns (Phase 8) may see labels:
those with `label_known_at <= t`.
"""

from __future__ import annotations

import datetime as dt
import json
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Policy:
    capacity_per_day: int = 100
    investigation_days: tuple[float, float] = (1.0, 14.0)
    external_days: tuple[float, float] = (30.0, 60.0)
    seed: int = 0


DEFAULT_POLICY = Policy()


@dataclass(frozen=True)
class Tx:
    event_id: int
    event_time: dt.datetime
    laundering: bool
    alert: bool
    priority: float


@dataclass(frozen=True)
class Label:
    event_id: int
    event_time: dt.datetime
    label: bool
    label_known_at: dt.datetime
    channel: str


def _days(rng: random.Random, lo_hi: tuple[float, float]) -> dt.timedelta:
    return dt.timedelta(days=rng.uniform(*lo_hi))


def simulate(txs: list[Tx], policy: Policy) -> list[Label]:
    """Who learns the truth, and when. Deterministic for a seed; pure."""
    rng = random.Random(policy.seed)
    by_day: dict[dt.date, list[Tx]] = defaultdict(list)
    for t in txs:
        if t.alert:
            by_day[t.event_time.date()].append(t)
    investigated: set[int] = set()
    out: list[Label] = []
    for day in sorted(by_day):
        queue = sorted(by_day[day], key=lambda t: (-t.priority, t.event_id))
        for t in queue[: policy.capacity_per_day]:
            investigated.add(t.event_id)
            out.append(Label(t.event_id, t.event_time, t.laundering,
                             t.event_time + _days(rng, policy.investigation_days),
                             "investigation"))  # fmt: skip
    for t in sorted(txs, key=lambda t: t.event_id):
        if t.laundering and t.event_id not in investigated:
            out.append(Label(t.event_id, t.event_time, True,
                             t.event_time + _days(rng, policy.external_days),
                             "external report"))  # fmt: skip
    return sorted(out, key=lambda lab: (lab.label_known_at, lab.event_id))


def known_as_of(labels: list[Label], when: dt.datetime) -> list[Label]:
    """The labels anyone could know at `when`. The only door for training (Phase 8)."""
    return [lab for lab in labels if lab.label_known_at <= when]


def message(lab: Label) -> bytes:
    return json.dumps({"event_id": lab.event_id, "label": lab.label, "channel": lab.channel,
                       "event_time": lab.event_time.isoformat(),
                       "label_known_at": lab.label_known_at.isoformat()}).encode()  # fmt: skip


# --- the jobs (admin, on the host) -------------------------------------------------------
def _truth(event_ids: list[int]) -> dict[int, bool]:
    import polars as pl

    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.tables import GOLD_LABELS, _scan

    df = (_scan(open_catalog("reader"), GOLD_LABELS)
          .filter(pl.col("source_row").is_in(event_ids))
          .select("source_row", "is_laundering").collect())  # fmt: skip
    return {r: bool(v) for r, v in df.iter_rows()}


def publish(policy: Policy = DEFAULT_POLICY, as_of: dt.datetime | None = None) -> dict:
    """Simulate labels for the decisions the stream made; send the ones already known at
    the stream's 'now' (its last event) to the `labels` topic; record every simulated
    `label_known_at` in gold.labels (the offline record of when each truth was known)."""
    from confluent_kafka import Producer

    from graphguard.config import REPO_ROOT
    from graphguard.stream import db
    from graphguard.stream import kafka_admin as ka
    from graphguard.stream.rules import priority

    secrets = REPO_ROOT / ".secrets"
    with db.connect(secrets_dir=secrets) as conn, conn.cursor() as cur:
        cur.execute("SELECT event_id, event_time, score, rules, alert FROM decisions")
        rows = cur.fetchall()
    truth = _truth([r[0] for r in rows])
    txs = [Tx(e, t, truth[e], a, priority(s, tuple(rl))) for e, t, s, rl, a in rows]
    labels = simulate(txs, policy)
    # 'now' = the stream's last event, unless a later clock is given (--as-of): verdicts take
    # days, so a short replay alone would never see one.
    now = as_of or max(t.event_time for t in txs)
    known = known_as_of(labels, now)
    producer = Producer({**ka.client_config("labeler", secrets_dir=secrets), **ka.PRODUCER})
    for lab in known:
        producer.produce("labels", message(lab), key=str(lab.event_id).encode())
        producer.poll(0)
    producer.flush(60)
    record_in_gold(labels)
    return {"decisions": len(txs), "labels_simulated": len(labels),
            "known_at_stream_end": len(known), "stream_end": now.isoformat()}  # fmt: skip


def record_in_gold(labels: list[Label]) -> int:
    """gold.labels.label_known_at for every simulated label (null = never labelled)."""
    import polars as pl

    from graphguard.lakehouse.catalog import open_catalog
    from graphguard.lakehouse.tables import GOLD_LABELS, _overwrite_streaming, _scan

    catalog = open_catalog("builder")
    known = pl.DataFrame({"source_row": [lab.event_id for lab in labels],
                          "_known": [lab.label_known_at for lab in labels]},
                         schema={"source_row": pl.Int64, "_known": pl.Datetime("us")})  # fmt: skip
    current = _scan(catalog, GOLD_LABELS).collect()
    updated = (current.join(known, on="source_row", how="left")
               .with_columns(pl.coalesce("_known", "label_known_at").alias("label_known_at"))
               .drop("_known").select(current.columns))  # fmt: skip
    _overwrite_streaming(catalog, GOLD_LABELS, updated.lazy(), by_day=False)
    return known.height


def measure(policy: Policy = DEFAULT_POLICY) -> dict:
    """The whole validation window, offline: with these delays, how much truth is known
    by the time the window ends? Alerts = the live policy (ADR 0007) on validation."""
    import numpy as np
    import polars as pl

    from graphguard.config import REPO_ROOT, TRANSACTIONS_FILE
    from graphguard.data.loader import load_transactions
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.models.pipeline import features_for_split
    from graphguard.models.tabular import build_matrix
    from graphguard.serving.model_bundle import ModelBundle
    from graphguard.stream import rules as R

    b = frozen_boundaries()
    lf = load_transactions(TRANSACTIONS_FILE)
    lf = (lf.lazy() if isinstance(lf, pl.DataFrame) else lf).with_row_index("source_row")
    val = features_for_split(lf, "validation", b)
    flags = R.cold_flags(lf.filter(pl.col("timestamp") < b[1])
                         .sort("timestamp", maintain_order=True).collect()
                         .select("source_row", "from_account", "to_account"))  # fmt: skip
    val = val.join(flags.select("source_row", "sender_cold", "receiver_cold"), on="source_row")
    bundle = ModelBundle.load(REPO_ROOT / "models" / "production")
    X, y = build_matrix(val, bundle.category_maps)
    scores = bundle.model.predict_proba(X.select(bundle.feature_columns).to_numpy())[:, 1]
    th = R.load()
    txs = []
    for r, s, lab in zip(val.iter_rows(named=True), scores, y.to_numpy(), strict=True):
        fired = R.fire(r, r["amount_paid"], r["sender_cold"], r["receiver_cold"], th)
        p = R.priority(float(s), fired)
        txs.append(Tx(r["source_row"], r["timestamp"], bool(lab), p >= th.alert_priority, p))
    labels = simulate(txs, policy)
    end = b[1]
    known = known_as_of(labels, end)
    laundering = int(np.sum(y.to_numpy()))
    by_channel = lambda ls: {c: sum(1 for x in ls if x.channel == c)  # noqa: E731
                             for c in ("investigation", "external report")}  # fmt: skip
    return {
        "policy": asdict(policy), "validation_rows": len(txs), "laundering": laundering,
        "alerts": sum(t.alert for t in txs),
        "labels_eventually": len(labels), "labels_eventually_by_channel": by_channel(labels),
        "known_by_window_end": len(known), "known_by_channel": by_channel(known),
        "laundering_known_by_window_end": sum(1 for x in known if x.label),
        "share_of_laundering_known_by_end": round(sum(1 for x in known if x.label) / laundering, 4),
        "window_end": end.isoformat(),
    }  # fmt: skip


def main(argv: list[str]) -> int:
    from graphguard.config import REPO_ROOT

    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "publish":
        as_of = (
            dt.datetime.fromisoformat(argv[argv.index("--as-of") + 1])
            if "--as-of" in argv
            else None
        )
        print(json.dumps(publish(as_of=as_of)))
        return 0
    if cmd == "measure":
        result = measure()
        (REPO_ROOT / "docs" / "analysis" / "s6.9-labels.json").write_text(
            json.dumps(result, indent=2) + "\n")  # fmt: skip
        print(json.dumps(result, indent=2))
        return 0
    print(f"usage: {argv[0]} publish|measure")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
