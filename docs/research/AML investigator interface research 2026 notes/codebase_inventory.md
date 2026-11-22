# Codebase inventory for Phase 7 (the interface)

*Read-only survey of `/srv/graphguard` at commit `9c30342` (Phase 6 gate met), 2026-11-22.
No code was run against Postgres, Redis, Kafka, k3s or Docker; no tests were run. Line
numbers are for that commit. Box weak spots are deliberately left out (those go in `private/`).*

---

## 0. What matters most (the short version)

1. **The whole validation window is already scored and sitting in Postgres.** The S6.11 soak
   left 1,015,300 rows in `stream.decisions`, each with its score, rules, alert flag,
   cold policy and **the 15-value feature vector the model saw**. These scores are exactly the
   offline evaluation scores (0 mismatches, `docs/analysis/s6.11-soak-run2.json`). That
   gives the queue, the "why", and (joined with truth) the capacity curve, with no new modelling.
   **But any `soak start`, `e2e` or `chaos` run TRUNCATEs these tables** (`stream/db.py:166-171`,
   called from `stream/e2e.py:34-43`). The UI needs a stable copy or a rule against resets.
2. **No read-only role exists for the stream DB.** The only role is `stream_app`, which owns and
   writes it (`ops/pg_access.py:36`, `stream/db.py:29`). A UI must get its own SELECT-only role
   (new `SERVICES` entry, so pg_hba and backups follow automatically).
3. **The queue unit is undecided.** Everything is ranked **per transaction** (`evaluate()`,
   `alert`, the `alerts` topic). PLAN.md's Phase 7 says "ranked accounts". 5,000 alerts per
   ~50 h window = ~2,370 a day, while the label simulator assumes investigators work **100 a day**
   (`stream/labels.py:34`). Phase 7 has to choose transaction, account or case (connected group
   of alerts), and one capacity number, and say so.
4. **No SHAP anywhere** (grep: no `shap`, no `pred_contribs`). Not needed as a library:
   XGBoost's own `Booster.predict(..., pred_contribs=True)` gives exact TreeSHAP on the stored
   feature vectors. No new dependency.
5. **No ring list in the lakehouse.** Patterns come only from the raw `HI-Small_Patterns.txt`,
   which **also holds test-window rings**. ADR 0003 (`docs/adr/0003-lakehouse-governance.md:72-74`)
   lists moving it into the lakehouse (test part in `sealed`) as an open follow-up. Phase 7 needs it.
6. **The "cost" in `evaluate()` adds amounts across currencies** (Euro + Yuan + Bitcoin +...),
   see section 3. Not usable as-is for "money missed" on the slider.
7. **Memory: GraphGuard is already at about its ~4 GB budget** (measured anon memory ~4.1 GiB,
   section 9). A frontend and API must be small, or something else must shrink.

---

## 1. Data the UI can read today

### 1.1 Postgres database `stream` (written by the consumer pod)

Schema: `src/graphguard/stream/db.py:34-102`. Writes: `stream/consumer.py:288-421`.

| Table | Columns (what matters) | Notes for the UI |
|---|---|---|
| `decisions` (`db.py:35-52`) | `event_id` (= `source_row`, the transaction key, PK), `seq`, `event_time` (2022 time from the data), `from_account`, `to_account`, `amount_paid`, `score`, `cold_policy`, `rules text[]`, `alert bool`, `model_version`, `model_sha256`, `features float8[]`, `decided_at` (wall clock), `arrived_at` (Kafka arrival, wall clock; S6.11) | 1 row per validation transaction after the soak. **No `priority` column**: it is recomputed as `rules.priority(score, rules)` (`stream/rules.py:82-87`). **Not stored:** payment format, currencies, banks, `amount_received`, which rule thresholds/alert line were used. Get the missing fields by joining silver on `source_row = event_id`. **Only index is the PK**: queue (`alert`, priority), account lookups (`from_account`, `to_account`) and time range will need indexes. Those are consumer-owned schema changes. |
| `feature_sets` (`db.py:53-56`) | `version` (= model version), `names text[]` | Names for `decisions.features`, written at consumer start (`consumer.py:311-315`). Today 15 names (section 4). |
| `labels` (`db.py:83-90`) | `event_id`, `label`, `label_known_at`, `channel` (`investigation` / `external report`), `kafka_offset` | Late verdicts, **simulated** by `stream/labels.py`. Content depends on the last `labels publish` run. The soak's reset truncates it, so it may be empty now (not checked: that needs DB credentials). |
| `decisions_shadow` (`db.py:92-99`) | `event_id`, challenger `score`, `champion_score`, model version/hash | The soak run 2 filled all 1,015,300 rows. |
| `dead_letters` (`db.py:74-81,101`) | `event_id`, `kafka_offset` (unique), `reason` (`malformed: ...` / `late`), `raw` | 0 rows after soak run 2. |
| `consumer_offsets`, `outbox` | internal | `outbox` holds every published `decisions` / `alerts` message payload as text (the alert payload includes `priority` and `reasons`). It is a log, not a query surface. |

Timestamps: `event_time` is the data's 2022 time. `decided_at` and `arrived_at` are 2026 wall
clock (the replay runs at 6×). The UI should show event time and treat the others as ops data.
Decision latency p50 5.3 s is almost entirely the reorder buffer (`consumer.py:95-122`, buffer 200).

### 1.2 Kafka topics (`stream/kafka_admin.py:53-63`)

`transactions`, `decisions` (score + features + names, `consumer.py:74-88`), **`alerts`**
(`event_id, event_time, from/to, amount, score, priority, reasons, cold_policy`;
`consumer.py:66-72`, published via the outbox `consumer.py:262-266`), `transactions.dlq`,
`decisions.shadow`, `labels`. **Nobody consumes `alerts` today.** No login has READ on it
(ACLs `kafka_admin.py:80-98`). A live queue fed from Kafka would need a new login + ACL,
added in `kafka_admin.py` only (`just kafka-setup` removes anything else). Postgres is the
simpler read path. Side note: the `shadow` login has WRITE on `decisions.shadow`, but the shadow
writes Postgres only (`shadow.py:187`). That grant looks unused.

### 1.3 Lakehouse (Iceberg via Lakekeeper; identities in `lakehouse/governance.py:33-37`)

- `silver.transactions`: train + validation, all 11 raw columns + `source_row`
  (`lakehouse/tables.py:187-200`). **This is the only place with full edge history (time, amount,
  currency, format, banks) before any alert.** Reader-readable.
- `gold.account_features_asof` (states as of `train_end`), `gold.account_recent_sends`,
  `gold.account_edges` (distinct pairs before `train_end`, **no time, no amount**), all
  snapshot seeds for the stream (`tables.py:203-248`).
- `gold.labels`: `source_row, timestamp, from, to, amount_paid, is_laundering, label_known_at`
  for **train + validation** (`tables.py:251-262`, schema `lakehouse/schemas.py:63-77`).
  `label_known_at` is set by `labels.record_in_gold` (`labels.py:145-162`) and reset to null by
  every `lakehouse-build`. **`is_laundering` here is the full answer key**, which a bank would
  not have on the day (FINDING-017).
- `sealed.transactions`: the test window. UI must never touch it.
- Access: `reader` (select silver + gold) is the right *kind* of identity for a UI. The project
  rule is one identity per job, so a long-running UI backend should get its own identity in
  `governance.py`, run as its own job user (`ops/jobs.py`). Reads go through DuckDB with vended
  1-hour keys (`lakehouse/sql.py:78-160`). That is fine for batch precompute, too slow and heavy
  for per-click queries (DuckDB job capped at 512 MB). **Recommend: precompute what the UI
  needs into Postgres (or a local Parquet the API reads), not live lakehouse queries.**
- Unused raw file: `data/raw/HI-Small_accounts.csv` (bank name, bank id, account number,
  **entity id, entity name** such as "Sole Proprietorship #50438"). `config.ACCOUNTS_FILE` is defined
  (`config.py:24`) and never read. It would give the UI human-readable account owners and
  group accounts by entity. It is raw-CSV territory (trainer/reader cannot see raw files, per
  `docs/runbooks/job-users.md:16-18`). It would need a lakehouse table.

### 1.4 MLflow

Experiments `graphguard` (training/tuning runs with flattened `evaluate()` metrics: `pr_auc`,
`precision_at_{k}`, `lift_at_{k}`, `pattern_recall_at_{k}`, `pattern_hit_rate_at_{k}`, at
k ∈ {50,100,500,1000,5000}; `models/train_tabular.py:31-44`), `graphguard-perf`,
`graphguard-tests`. Users `admin`, `trainer`, `research` only (`ops/mlflow_auth.py:37-43`). No
UI/agent user. **`build-artifacts` (the production model) logs lineage params only, not its
evaluation metrics** (`serving/build_artifacts.py`, `_train`). The 0.28155 numbers live in the
Phase 3 tuning run and `docs/analysis/s6.8-rules.json`. No model registry or aliases yet (Phase 8).
The agent eval (PLAN Phase 7) will need its own experiment + grant.

### 1.5 Scorer HTTP API (Ray Serve on k3s, `serving/app.py`)

- `POST /`: body needs `from_account, to_account, amount_paid, amount_received, from_bank,
  to_bank, payment_currency, timestamp` (`app.py:57-66`). Returns `score, sender_cold,
  receiver_cold, cold_policy, *_staleness_seconds, model_trained_on, model_version`
  (`app.py:129-138`). 422 on bad input, 503 when the store is down or not loaded.
- `GET .../health` (`app.py:140-148`).
- **Not useful for the queue or for "why":** no rules, no priority, no features, no
  explanation in the response. **It reads the same Redis keys the stream mutates** (`gg:acct:*`,
  `serving/store.py:159`, `stream/updater.py:273`). A re-score today uses account state *at the
  end of the replay*, not as of the alert, so it will not reproduce the stored decision. **The UI
  should show stored decisions, never re-score.** Reachable only inside the cluster (scoring port
  open, everything else denied, `k8s/networkpolicy.yaml`). The namespace is default-deny egress,
  so a UI pod needs its own policies.

---

## 2. Rules, priority, alert line (ADR 0007), cold accounts

- Six rules, as-of inputs only: `stream/rules.py:63-79`. Thresholds generated from the
  **training** window into `stream/rule_thresholds.py` (velocity 25,752/24 h, fan-out 14,230,
  fan-in 48, large amount top-1%).
- `priority(score, rules) = 1 + score` if `both_new` or ≥2 rules, else `score`
  (`rules.py:82-87`).
- **Alert line** `alert_priority = 0.22587…` = the priority at rank 5,000 **on validation**
  (`rules.py:160`, generated value `rule_thresholds.py:9`). `alert` is decided live at
  `consumer.py:254`. Because the line was set on the same window the stream replays, "exactly
  5,000 alerts" in the soak is circular by construction. That is OK (validation is the tuning
  window), but it should be said that way, not shown as an independent result.
- Measured (FINDING-016, `docs/analysis/s6.8-rules.json`): rules-only p@5000 0.0042 vs model
  0.1084. Fire rates: structuring ~1% (precision 0.34%), fan-in 0.1% (precision 0), velocity /
  fan-out / new_account_large **never fire** on validation. On this data, "reasons" in the queue
  will be "model score" for nearly every alert. The "why" must come from SHAP, not rules.
- **Cold-account inconsistency to know about.** FINDING-014 / `serving/service.py:48-58` say
  both-new is 63 validation transactions (~27/day). That was measured against the **static**
  `train_end` snapshot (`analysis/cold_accounts.py:66-79`). The live stream (and the offline rules
  measurement, `rules.py:112-125`) warms accounts as they appear, so `both_new` fires only a
  handful of times (fire rate rounds to 0.0; precision 0.2 ⇒ ~5 hits). Live `cold_policy` values
  in `decisions` follow the stream definition. The "~27 a day to review" sentence is stale for the
  live system.

## 3. Evaluation outputs for the capacity slider

- `evaluate()` (`evaluation/evaluate.py:24-86`) returns `pr_auc`, `precision_at_k`,
  `lift_at_k`, and optionally `pattern[k]` (ring recall at ≥50% of hops flagged + any-hop hit rate,
  `metrics.py:181-220`) and `cost[k]` (`investigator_hours = k × 0.5 h` hard-coded default,
  `laundering_value_caught/missed`; `evaluate.py:75-84`). Default k = (50, 100, 500, 1000, 5000)
  (`evaluate.py:17`). It takes any `k_values`, so a dense curve is one call.
- **Missing:** recall@k (number of launderers caught / 1,083) is not returned. Easy to derive,
  but `evaluate()` is the single entry point, so add it there, test-first. **Minority-class F1
  (R-2 change #2) is still not implemented.**
- **Currency bug for the slider:** `amounts=val_df["amount_paid"]` (e.g. `models/train_tabular.py:83`)
  sums raw amounts across 15 currencies including Bitcoin and Yen. `laundering_value_*` is
  therefore meaningless as money. The history features `sender_amount_sent_before` /
  `receiver_amount_received_before` (`features/graph.py`) are mixed-currency sums too. That is fine
  for a tree (order only). It is **not** fine to display as "total sent". A slider in money needs
  an FX table (none in the repo) or should report counts and rings only.
- **Window vs day:** k counts over the whole validation window (2022-09-06 13:34 → 09-08 16:09,
  ~50.6 h; `data/splits/frozen_split.json`). The slider says "per day", so it must convert, and
  a global top-k over the window uses hindsight on the score distribution. The live, causal
  version is "priority ≥ line", and the label simulator ranks **per calendar day**
  (`labels.py:65-87`). Pick one definition and show it.
- **The data for a live recompute already exists:** `decisions.score` / priority (1,015,300 rows) ⨝
  `gold.labels.is_laundering` (+ ring ids from the patterns file) → precompute the full curve
  once (a few thousand k points, a small table), then interpolate in the browser. Ring ids are
  attached by a key join on (timestamp, from, to, amount_paid) with `keep="first"` on duplicates
  (`evaluation/dataset.py:24-48`). Ring denominators: 168 validation rings; 38% of laundering is in no
  ring (FINDING-003), and the UI must show that denominator.
- Reference numbers (production model, validation): PR-AUC 0.28155; p@50 0.96, p@100 0.95,
  p@500 0.506, p@1000 0.332, p@5000 0.1084 (542 launderers); rings caught @5000 127/168
  (`docs/leakage_audit.md`, `s6.8-rules.json`).

## 4. Explanations ("why this alert")

- Production features (15, `models/production/metadata.json`; = `FEATURE_COLUMNS` minus
  `ARTIFACT_FEATURES` `models/train_tabular.py:51`, `serving/build_artifacts.py:83`):
  `hour, weekday, log_amount, amount_ratio, is_same_bank, payment_currency_code,
  sender_n_sent_before, sender_amount_sent_before, sender_distinct_out_before,
  sender_sent_last_24h, sender_seconds_since_last_send, receiver_n_received_before,
  receiver_amount_received_before, receiver_distinct_in_before, in_out_ratio_before`.
  Definitions: `features/basic.py:14-39` (row-level), `features/graph.py:35-131`
  (point-in-time history, current row excluded). Meaning and justification:
  `docs/leakage_audit.md` (note: gain table there is for the **18-feature full model**, not the
  served 15. No importance for the served model is recorded anywhere).
- Plain-language direction worth surfacing: launderers have *fewer* counterparties and sends
  than ordinary accounts (FINDING-005). "Busy = suspicious" is wrong here.
- **SHAP: not implemented anywhere.** Path: load the bundle (`serving/model_bundle.py:53-69`),
  take `decisions.features` in `feature_sets.names` order, cast to float32 exactly like
  `to_vector` (`model_bundle.py:78`), call `model.get_booster().predict(DMatrix, pred_contribs=True)`.
  15 contributions + bias, in **log-odds**, summing to the margin. Test: sum of contributions →
  sigmoid = stored `score`. Precompute for the 5,000 alerts (cheap) rather than per click.
- **Two caveats the UI copy must respect:** (a) the score is **not a probability**. The model
  was trained with `scale_pos_weight` ≈ 1,326 (`models/tabular.py:111-120`), so 0.23 does not
  mean 23%. Show rank / percentile. (b) `payment_currency_code` is a category code, and
  `hour`/`weekday` are simulator-time features, so explain them carefully. TreeSHAP's default
  (path-dependent) splits credit across correlated counts (n_sent vs amount_sent). Say
  "contributed", not "caused".
- GNNExplainer is scoped to the GNN arm (R-1). Not relevant to the served path.

## 5. Drawing the ring / subgraph around an alert

- **Can be reconstructed, but nothing does it today.** Sources:
  - `silver.transactions`: every train+val edge with time, amount, currency, format. Neighbourhood
    query: `timestamp < T` (or `(timestamp, source_row) < (T, event_id)` because of minute ties,
    FINDING-010), accounts within 1-2 hops, ordered by (timestamp, source_row).
  - `stream.decisions`: validation-window edges only, but with each edge's own score/alert, which
    is nice for colouring edges. Needs indexes on `from_account`/`to_account`.
  - `gold.account_edges` and Redis `gg:edge:*`: pairs only, no time or amount. Not enough.
  - `graph/build.py` builds day snapshots as torch tensors (GNN arm, needs the `gnn` extra).
    Wrong shape for a UI.
- **Hub problem:** FINDING-002. Some accounts have >100k transfers (one sent 168,672). A 2-hop
  neighbourhood can explode, so cap by degree, time window (rings span a median of 3.1 days, max
  8.4) and top-N by amount or score.
- **"The labelled ring" is answer-key data.** Showing "this is a FAN-OUT ring" uses
  `pattern_id`/type from the patterns file. That is hindsight (truth), not what the system knows.
  It must be shown as a clearly separate "answer key" view, and **the investigator agent must not
  see it** (typology recall is measured against it).
- **Graph-as-of-T is a leakage-contract rule (rule 2)**: the drawn graph must contain only edges
  before the alert. Test that the way `features/graph.py` is tested.

## 6. Labels, delay, shadow

- `labels.known_as_of(t)` (`stream/labels.py:89-91`) is the only door for anything that learns.
  Policy defaults: 100 investigations/day, verdict 1-14 days, external report 30-60 days
  (`labels.py:33-38`). Only 5 labels are known by window end (FINDING-017).
- The UI needs two truths, clearly separated: **"known by now"** (Postgres `labels` / `known_as_of`)
  vs the **offline answer key** (`gold.labels.is_laundering`, used for the slider's evaluation numbers).
- Investigator actions (escalate/close, the "what would you do next" of the Phase 7 gate) have
  **no table and no topic**. If Phase 7 records them, they are new labels and must enter via the
  same delayed door, never straight into training.
- Shadow: `stream/shadow.py:219-262` (`compare`) / `report` (`:264`). Segments only by
  `cold_policy` because `decisions` lacks currency/format (S6.10's story asked for those).
  Challenger `xgb-1eaf6e7157f8` lost (PR-AUC 0.2266 vs 0.2816). The labelled comparison is biased
  toward the champion (FINDING-017). `docs/analysis/s6.10-shadow.json`.

## 7. Test set

- Sealed: `sealed.transactions` (only `lakehouse/catalog.py`, `tables.py`, `governance.py` may name
  it); `load_split("test")` allowed only in `src/graphguard/evaluation/final_report.py`, which
  **does not exist yet** (`scripts/guards/test_set_touch_check.py:39-57`). The final evaluation
  will need a one-time `evaluator` identity with a grant on `sealed` (ADR 0003 last bullet).
  The stream asserts validation-only (`tables.py:317-326`).
- **Guard gaps relevant to Phase 7:** the guard counts `load_split("test")` and the word
  `sealed`. It does **not** catch (a) reading the raw CSV and filtering `timestamp >= val_end`,
  (b) `features_for_split(..., "test")` (`models/pipeline.py:37-50`), (c) the patterns file's
  test-window rings. Any UI precompute that touches raw files must filter `< val_end` explicitly,
  with a test. Better: build the ring table in the lakehouse first (gold for train+val, sealed for
  test).

## 8. Gaps, stale docs, inconsistencies

| # | Item | Where |
|---|---|---|
| 1 | Stream tables wiped by every soak/e2e/chaos reset. UI demo data not durable | `stream/db.py:166-171`, `stream/e2e.py:34-43`, `stream/soak.py:98-104` |
| 2 | No read-only DB role, no UI MLflow user, no UI lakehouse identity, no UI Kafka login | `ops/pg_access.py:27-37`, `ops/mlflow_auth.py:37-43`, `lakehouse/governance.py:33-37`, `stream/kafka_admin.py:80-98` |
| 3 | `decisions` has no priority, no payment format/currency/banks, no thresholds version, only a PK index | `stream/db.py:35-52` |
| 4 | Queue unit mismatch: PLAN says accounts, code ranks transactions | PLAN.md Phase 7 vs `evaluate.py`, `consumer.py:254` |
| 5 | Capacity mismatch: alert line = 5,000 per ~50 h (~2,370/day) vs label sim 100/day | `rule_thresholds.py:10`, `labels.py:34` |
| 6 | Mixed-currency money sums in `evaluate()` cost and in history features | `evaluate.py:75-84`, `features/graph.py` |
| 7 | `evaluate()` lacks recall@k and minority-class F1 (R-2 #2 still open) | `evaluate.py` |
| 8 | No SHAP. No served-model importance on record | grep; `docs/leakage_audit.md` covers the 18-feature model |
| 9 | Ring list not in the lakehouse; patterns file includes test rings; trainer reads raw file | ADR 0003:72-74, `serving/build_artifacts.py` (`attach_pattern_ids(..., parse_patterns(PATTERNS_FILE))`) |
| 10 | FINDING-014's "~27 both-new a day to review" is from the static snapshot; live stream yields ~5 per window | `analysis/cold_accounts.py:66-79` vs `rules.py:112-125`, `s6.8-rules.json` |
| 11 | `docs/leakage_audit.md` says both "quote 0.28155" and "the number that should be quoted is 0.248" | `docs/leakage_audit.md` (headline vs two later paragraphs) |
| 12 | README status says "Phase 5 (serving) next"; phase table stale | `README.md:6-8, 215-225` |
| 13 | `pyproject.toml` description still says "with a graph neural network" (R-1: XGBoost serves) | `pyproject.toml:4` |
| 14 | CLAUDE.md: "Postgres 256M" (compose now 384m since S6.11), "1 worker" vs "2 web workers" for MLflow (compose: `--workers 1`), "~96GB disk free" (now ~36 GB free on `/`), "swap ~99%" (now ~2.1/4 GB) | CLAUDE.md lines ~87, 94, 158, 182; `docker-compose.yml:59,89` |
| 15 | `k8s/networkpolicy.yaml` header comment says egress is not restricted. The same file then denies egress by default (stale comment) | `k8s/networkpolicy.yaml` top comment |
| 16 | Kafka `alerts` topic has no consumer; `decisions.shadow` topic write grant seems unused | `kafka_admin.py:53-98`, `shadow.py:187` |
| 17 | `HI-Small_accounts.csv` (entity names) unused | `config.py:24` |
| 18 | Production model's evaluation not logged in its own MLflow run | `serving/build_artifacts.py` |
| 19 | PLAN says "same stack as LuBot's frontend". `/srv/lubot-*` is off limits here, so confirm the stack with Lubo rather than reading it | PLAN.md Phase 7 |
| 20 | No NIM/MCP code, key, or secret registry entry yet for the agent (new secret ⇒ `secrets_registry.py` entry; Lubo types it himself with `just secret-set`) | grep; CLAUDE.md "Secrets" |

## 9. Memory / box budget facts

Measured 2026-11-22 (cgroup `memory.stat`, read-only), after the soak, stream idle:

| | anon (excl. page cache) |
|---|---|
| k3s pods total | ~2.37 GiB (scorer ~2.0 GiB of it; consumer ~316 MiB; shadow ~194 MiB) |
| k3s service itself | ~0.70 GiB |
| GraphGuard Docker containers | ~1.0 GiB (Kafka ~483 MiB, Redis ~300, Postgres ~244, MLflow ~176, Lakekeeper/OpenFGA/Dex ~85) |
| **Total** | **~4.1 GiB**, against a CLAUDE.md budget of ~4 GB |

Box: ~20 GiB available, swap ~2.1/4 GiB used, `/` ~36 GB free, repo ~5.2 GB (2.7 GB is `.venv`).
Caps: scorer 2560Mi, consumer 640Mi, shadow 384Mi, Postgres 384m, Redis 448m, Kafka 768m, MLflow
640m. **Room for Phase 7 has to be made or agreed:**
- The biggest lever is Ray Serve: ~1.2 GB of the scorer is Ray overhead (ADR 0001, FINDING-013), and
  the stream no longer uses the HTTP scorer at all. Moving it to plain FastAPI on k3s was estimated
  at 0.2-0.3 GB (not measured). That is a Lubo decision (ADR 0001 revisit).
- The shadow pod is only needed during comparisons (~200 MiB).
- A small API (FastAPI/uvicorn are already in the lock transitively; psycopg2 and xgboost are
  direct deps) plus a **static-built** frontend served by an existing web server keeps the
  footprint to one Python process. A Node SSR server would be a second always-on process.
- The agent's LLM runs remotely (NVIDIA NIM per PLAN), so no local model memory.
- Every new compose service must pass `tests/test_compose_hardening.py`. Every new pod must run
  under the `restricted` Pod Security level with its own NetworkPolicies (`just k8s-check` fails
  without them). Publishing a public URL means nginx/TLS: a box-wide change that goes to the
  LuBot session first, then `just edge-baseline`.
- Don't run heavy lakehouse precompute while MLflow is busy training (CLAUDE.md lakehouse note).
