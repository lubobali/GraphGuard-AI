"""Shadow scoring (S6.10): a challenger model scores the same live inputs and decides nothing.

    python -m graphguard.stream.shadow train      # the challenger bundle -> models/challenger
    python -m graphguard.stream.shadow publish    # to S3, content-addressed (S5.7); prints the pin
    python -m graphguard.stream.shadow report     # champion vs challenger on what the stream saw
    python -m graphguard.stream.shadow            # the shadow consumer (its own k3s pod)

**Identical inputs.** The champion's consumer computes each transaction's exact features
once (S6.3) and puts them in its `decisions` message. The shadow consumer -- its own group
(`graphguard-shadow`), its own login (`shadow`), its own pod -- scores those same vectors with
the challenger and writes `decisions_shadow`. It never writes Redis, never alerts, never
touches the champion's decisions: shadow mode as Uber describes it (identical live inputs,
outputs logged, not acted on).

**The challenger** is the production pipeline with honest alternative settings (shallower,
fewer trees, another seed) -- the kind of cheaper candidate a team would try. Trained on the
training window only, published to S3 and pinned by hash like the champion. Promotion is
Phase 8's job; this story only measures.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import numpy as np

from graphguard.config import REPO_ROOT

log = logging.getLogger("graphguard.shadow")
CHALLENGER_DIR = REPO_ROOT / "models" / "challenger"
GROUP = "graphguard-shadow"
TOPIC = "decisions"
CHALLENGER_PARAMS = {
    "max_depth": 6,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 1.0,
    "reg_lambda": 1.0,
}
CHALLENGER_TREES, CHALLENGER_SEED = 200, 7


def train() -> Path:
    """Same features, same window, same category maps as production -- other settings."""
    import polars as pl

    from graphguard.config import TRANSACTIONS_FILE
    from graphguard.data.loader import load_transactions
    from graphguard.evaluation.dataset import frozen_boundaries
    from graphguard.models.pipeline import features_for_split
    from graphguard.models.tabular import build_matrix, fit_xgboost
    from graphguard.serving.model_bundle import ModelBundle

    champion = ModelBundle.load(REPO_ROOT / "models" / "production")
    b = frozen_boundaries()
    lf = load_transactions(TRANSACTIONS_FILE)
    lf = lf.lazy() if isinstance(lf, pl.DataFrame) else lf
    train_df = features_for_split(lf, "train", b)
    X, y = build_matrix(train_df, champion.category_maps)
    model = fit_xgboost(
        X.select(champion.feature_columns),
        y,
        CHALLENGER_PARAMS,
        seed=CHALLENGER_SEED,
        n_estimators=CHALLENGER_TREES,
    )
    bundle = ModelBundle(
        model=model,
        feature_columns=champion.feature_columns,
        category_maps=champion.category_maps,
        trained_on=f"train window ending {b[0].isoformat()} (challenger)",
    )
    bundle.save(CHALLENGER_DIR)
    return CHALLENGER_DIR


def publish() -> tuple[str, str]:
    import datetime as dt

    from graphguard.config import secrets_dir
    from graphguard.serving import model_store as ms

    s3 = ms.client(ms._env_file(secrets_dir() / "models-publisher-aws.env"))
    extra = {
        "role": "challenger",
        "params": CHALLENGER_PARAMS,
        "trees": CHALLENGER_TREES,
        "seed": CHALLENGER_SEED,
        "published_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    }
    return ms.publish(s3, CHALLENGER_DIR, extra)


# --- the shadow consumer -----------------------------------------------------------------
def score_payloads(bundle, payloads: list[dict]) -> list[dict]:
    """Challenger scores for the champion's own feature vectors (pure given the bundle)."""
    rows = [dict(zip(p["feature_names"], p["features"], strict=True)) for p in payloads]
    scores = bundle.score_rows(rows)
    return [
        {"event_id": p["event_id"], "score": float(s), "champion_score": p["score"]}
        for p, s in zip(payloads, scores, strict=True)
    ]


def run(stop=lambda: False, max_idle_s: float | None = None) -> int:
    from confluent_kafka import OFFSET_BEGINNING, Consumer, TopicPartition
    from psycopg2.extras import execute_values

    from graphguard.serving.app import load_model
    from graphguard.stream import db
    from graphguard.stream import kafka_admin as ka

    m = load_model(
        version=os.environ.get("GRAPHGUARD_SHADOW_MODEL_VERSION"),
        manifest_sha256=os.environ.get("GRAPHGUARD_SHADOW_MODEL_SHA256"),
    )
    conn = db.connect(os.environ.get("GRAPHGUARD_STREAM_DB", db.HOST_DSN))
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT next_offset FROM consumer_offsets WHERE grp=%s AND topic=%s AND part=0",
            (GROUP, TOPIC),
        )
        row = cur.fetchone()
    kc = Consumer(
        {
            **ka.client_config(
                "shadow", os.environ.get("GRAPHGUARD_KAFKA_BOOTSTRAP", ka.HOST_BOOTSTRAP)
            ),
            "group.id": GROUP,
            "enable.auto.commit": False,
        }
    )
    kc.assign([TopicPartition(TOPIC, 0, row[0] if row else OFFSET_BEGINNING)])
    log.info("shadow up: challenger %s, resume at %s", m["version"], row)
    done, idle = 0, time.monotonic()
    try:
        while not stop():
            records = [r for r in kc.consume(1000, 1.0) if not r.error()]
            if not records:
                if max_idle_s is not None and time.monotonic() - idle > max_idle_s:
                    break
                continue
            idle = time.monotonic()
            payloads = [json.loads(r.value()) for r in records]
            scored = score_payloads(m["bundle"], [p for p in payloads if "features" in p])
            with conn, conn.cursor() as cur:  # one transaction: rows + position
                if scored:
                    execute_values(
                        cur,
                        "INSERT INTO decisions_shadow (event_id, score, "
                        "champion_score, model_version, model_sha256) VALUES %s "
                        "ON CONFLICT (event_id) DO NOTHING",
                        [
                            (
                                s["event_id"],
                                s["score"],
                                s["champion_score"],
                                m["version"],
                                m["sha256"] or "",
                            )
                            for s in scored
                        ],
                    )
                cur.execute(
                    "INSERT INTO consumer_offsets (grp, topic, part, next_offset) "
                    "VALUES (%s, %s, 0, %s) ON CONFLICT (grp, topic, part) DO UPDATE "
                    "SET next_offset = EXCLUDED.next_offset, updated_at = now()",
                    (GROUP, TOPIC, records[-1].offset() + 1),
                )
            done += len(scored)
    finally:
        kc.close()
    return done


# --- the comparison --------------------------------------------------------------------
def _rank_corr(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = a.argsort().argsort(), b.argsort().argsort()
    return float(np.corrcoef(ra, rb)[0, 1])


def compare(rows: list[tuple], k_share: float = 0.01) -> dict:
    """rows: (event_id, champion, challenger, label or None, segment). Pure, tested."""
    if not rows:
        return {"n": 0}
    ids = np.array([r[0] for r in rows])
    champ = np.array([r[1] for r in rows], dtype=float)
    chall = np.array([r[2] for r in rows], dtype=float)
    k = max(1, int(len(rows) * k_share))
    top_c = set(ids[np.argsort(-champ, kind="stable")[:k]].tolist())
    top_h = set(ids[np.argsort(-chall, kind="stable")[:k]].tolist())
    out = {
        "n": len(rows),
        "k": k,
        "rank_correlation": round(_rank_corr(champ, chall), 4),
        "top_k_overlap": round(len(top_c & top_h) / k, 4),
        "mean_abs_score_diff": round(float(np.mean(np.abs(champ - chall))), 6),
    }
    labelled = [(r[1], r[2], r[3]) for r in rows if r[3] is not None]
    out["labelled"] = len(labelled)
    if len(labelled) >= 5:
        # Top 20% of the labelled rows: a k as large as the labelled set would rank all of
        # them and say nothing. And the labels are only what investigators worked -- the
        # CHAMPION's alerts (FINDING-017) -- so this comparison is biased toward it.
        lab = np.array([x[2] for x in labelled], dtype=int)
        kk = max(1, len(labelled) // 5)
        for name, col in (("champion", 0), ("challenger", 1)):
            s = np.array([x[col] for x in labelled], dtype=float)
            top = np.argsort(-s, kind="stable")[:kk]
            out[f"{name}_precision_top20pct_labelled"] = round(float(lab[top].mean()), 4)
        out["labelled_note"] = ("labels exist only for investigated champion alerts (plus late "
                                "external reports): biased toward the champion")  # fmt: skip
    segs: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        segs.setdefault(r[4], []).append(i)
    out["by_segment"] = {
        s: {
            "n": len(ix),
            "mean_abs_score_diff": round(float(np.mean(np.abs(champ[ix] - chall[ix]))), 6),
            "rank_correlation": round(_rank_corr(champ[ix], chall[ix]), 4) if len(ix) > 2 else None,
        }
        for s, ix in sorted(segs.items())
    }
    return out


def report() -> dict:
    from graphguard.stream import db

    with db.connect(secrets_dir=REPO_ROOT / ".secrets") as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT d.event_id, d.score, s.score, l.label, d.cold_policy FROM decisions d "
            "JOIN decisions_shadow s USING (event_id) LEFT JOIN labels l USING (event_id)"
        )
        rows = cur.fetchall()
        cur.execute("SELECT DISTINCT model_version FROM decisions_shadow")
        versions = [r[0] for r in cur.fetchall()]
    out = compare(rows)
    out["challenger_versions"] = versions
    return out


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "train":
        print(f"challenger saved to {train().relative_to(REPO_ROOT)}")
        return 0
    if cmd == "publish":
        version, sha = publish()
        print(
            f"published {version}\n  GRAPHGUARD_SHADOW_MODEL_VERSION: {version}\n"
            f"  GRAPHGUARD_SHADOW_MODEL_SHA256: {sha}"
        )
        return 0
    if cmd == "report":
        result = report()
        (REPO_ROOT / "docs" / "analysis" / "s6.10-shadow.json").write_text(
            json.dumps(result, indent=2) + "\n"
        )
        print(json.dumps(result, indent=2))
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stopping = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stopping.__setitem__("now", True))
    log.info("shadow stopped after %d", run(stop=lambda: stopping["now"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
