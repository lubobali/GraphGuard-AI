# ADR 0001 — Serving runtime: keep Ray Serve on k3s

**Status:** accepted, 2026-11-18 (S5.3)
**Decided by:** Lubo, on the measurements below

## Context

The scorer serves one XGBoost model: fetch both accounts' point-in-time features from
Redis, add the transaction's own features, return a score. Budget: p99 under 50ms, and
GraphGuard as a whole must stay within ~4GB RAM on a box that runs LuBot production.

Ray Serve was chosen in August and deployed on k3s via KubeRay. Plan revision R-2 asked
for that choice to be re-checked against measured memory and 2026 security facts before
building Phase 6 on it.

## Options

| | Ray Serve (KubeRay) | FastAPI on k3s | BentoML on k3s |
|---|---|---|---|
| Memory for this model | **measured 1.9 GB** | est. 0.2-0.3 GB (not measured) | est. 0.4-0.6 GB (not measured) |
| Replicas, routing, restarts | built in | k8s Deployment + Service | built in |
| Scales to more models / GPUs / batch | yes, its purpose | by hand | partly |
| Attack surface | dashboard + GCS: unauthenticated job submission | one HTTP port | one HTTP port + its API |
| Named in 58 fraud/AML ML postings (R-2) | 0 (Ray itself 2, as a plus) | not counted | 0 |

## Measurements (2026-11-18, cgroup v2, not YAML)

- **Idle 1,920 MiB, peak 1,965 MiB** over 2,000 real validation transactions.
- Breakdown: the two model replicas are 2 × 377 MiB. The rest (~1.2 GB) is Ray itself:
  dashboard and its modules, ServeController, ProxyActor, DashboardAgent, raylet.
- **GraphGuard total ≈ 2.97 GB idle** (k3s 792 + Ray 1,965 + kube helpers ~40 + MLflow
  96 + MLflow Postgres 22 + Redis 32 + runner 21), ~3.6 GB with MLflow busy. Fits.
- **p99 7.57-7.83ms** through the k3s Service over HTTP (warm pod); 12.9ms on a pod
  seconds old.
- Ray **2.58.0**, which has the fix for CVE-2025-62593 (needs ≥ 2.52).

## Decision

**Keep Ray Serve.** It fits the budget with room, it is far inside the latency budget,
and it is real distributed-serving experience on real Kubernetes. Lubo chose it knowing
it costs ~1.6 GB more than a plain FastAPI service would, and that job postings ask for
the capability (production serving, latency budgets) rather than the brand.

Made safe and right-sized as part of the decision:

1. **NetworkPolicy** (`k8s/networkpolicy.yaml`): default-deny ingress; only the KubeRay
   operator and port 8000 allowed. Before it, `/api/jobs/` answered from a Docker
   container — any container on the box, LuBot's code sandboxes included, could have
   run code in the pod. After: blocked from Docker; scoring unchanged; the operator's
   serve-status checks run with zero errors.
2. **Memory limit 3Gi → 2560Mi** from the measured peak (+27% headroom). KubeRay rolled
   it out with no downtime (new cluster ready before the old one was removed).
3. **`just k8s-check`** alarms if the pod is not ready, the image is missing or unpinned,
   or the network policies disappear.

## Consequences

- ~1.2 GB of the budget is Ray overhead, not the model. If the budget gets tight (Kafka
  in Phase 6, Airflow/Dagster in Phase 8), **this is the first place to look**: replicas
  2 → 1 saves ~377 MiB; a FastAPI rewrite saves ~1.6 GB. Measure first, as here.
- The dashboard stays reachable from the **host** itself — kube-router always admits
  node-local traffic. Accepted: anyone on the host is already root.
- Ray must stay ≥ 2.52, and the dashboard must never be exposed outside the cluster.
  Re-check on every Ray upgrade.
- KubeRay operator is v1.2.2 (2024) against Ray 2.58. It works; upgrading the operator
  is a separate, deliberate change, not drift.
- Swapping the runtime later is cheap by design: the scoring logic lives in
  `ScoringService`, not in Ray-specific code.
