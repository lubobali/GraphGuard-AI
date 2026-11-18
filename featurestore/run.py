"""Materialise gold into Feast's online store and measure it (S5.6e).

    just feast-trial

Runs in Feast's own environment (featurestore/.venv). Steps:
1. log in to Dex as `reader` (client credentials) and hand Feast the token;
2. `apply` the feature repo, then `materialize` the gold snapshot into SQLite;
3. export every account's online values to a Parquet file, which the main project
   compares with its own store (`graphguard.lakehouse.feast_parity`);
4. time 1,000 two-account online lookups, the scorer's access pattern.

Writes nothing to the live Redis and nothing to the lakehouse tables.
"""

from __future__ import annotations

import base64
import json
import os
import random
import resource
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "lakehouse" / "feast"
FEATURES = (
    "n_sent",
    "n_received",
    "amount_sent",
    "amount_received",
    "distinct_out",
    "distinct_in",
    "sent_last_24h",
    "last_seen",
    "last_sent",
)
TOKEN_URL = os.environ.get("GRAPHGUARD_DEX_URL", "http://127.0.0.1:5556/dex") + "/token"


def reader_token() -> str:
    env = dict(
        line.split("=", 1)
        for line in (REPO / ".secrets" / "identity-reader.env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    basic = base64.b64encode(f"{env['GG_CLIENT_ID']}:{env['GG_CLIENT_SECRET']}".encode()).decode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(
            {"grant_type": "client_credentials", "scope": "openid"}
        ).encode(),
        headers={"Authorization": f"Basic {basic}"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


def peak_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ["GG_FEAST_TOKEN"] = reader_token()
    sys.path.insert(0, str(HERE / "feature_repo"))
    from feast import FeatureStore

    from features import account, account_state, gold_account_states

    store = FeatureStore(repo_path=str(HERE / "feature_repo"))
    results: dict[str, object] = {}

    t0 = time.perf_counter()
    store.apply([account, account_state])
    results["apply_s"] = round(time.perf_counter() - t0, 2)

    gold = gold_account_states.load_pyiceberg_table()
    as_of = gold.scan(selected_fields=("as_of",), limit=1).to_arrow()["as_of"][0].as_py()
    accounts = gold.scan(selected_fields=("account",)).to_arrow()["account"].to_pylist()
    results["accounts"] = len(accounts)
    results["as_of"] = as_of.isoformat()

    t0 = time.perf_counter()
    store.materialize(start_date=as_of - timedelta(days=1), end_date=as_of + timedelta(minutes=1))
    results["materialize_s"] = round(time.perf_counter() - t0, 1)
    results["peak_rss_mb_after_materialize"] = round(peak_mb())

    refs = [f"account_state:{f}" for f in FEATURES]
    t0 = time.perf_counter()
    batches = []
    for i in range(0, len(accounts), 20_000):
        rows = [{"account": a} for a in accounts[i : i + 20_000]]
        batches.append(
            pa.Table.from_pydict(
                store.get_online_features(features=refs, entity_rows=rows).to_dict()
            )
        )
    export = pa.concat_tables(batches, promote_options="permissive")
    pq.write_table(export, OUT / "online_export.parquet")
    results["export_s"] = round(time.perf_counter() - t0, 1)

    rng = random.Random(42)
    lat = []
    for _ in range(1_000):
        pair = [{"account": a} for a in rng.sample(accounts, 2)]
        t = time.perf_counter()
        store.get_online_features(features=refs, entity_rows=pair).to_dict()
        lat.append((time.perf_counter() - t) * 1000)
    lat.sort()
    results["online_2_accounts_ms"] = {
        "p50": round(lat[500], 2),
        "p99": round(lat[990], 2),
        "max": round(lat[-1], 2),
    }
    results["peak_rss_mb"] = round(peak_mb())
    results["online_db_mb"] = round((OUT / "online.db").stat().st_size / 1e6, 1)
    results["ran_at"] = datetime.now().isoformat(timespec="seconds")
    (OUT / "trial_results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
