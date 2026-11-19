# Runbook — the model on S3 (S5.7)

The scorer downloads its model at startup from
`s3://graphguard-lakehouse-0dcd18/models/xgboost/<version>/`, checks the manifest against
the SHA-256 pinned in `k8s/rayservice.yaml` and every file against the manifest, and
**refuses to start** on any difference. The image carries no model.

| | |
|---|---|
| Version | `xgb-` + 12 hex of the model files' hashes: same bytes, same version |
| Immutable | uploads use `If-None-Match: *`; the publisher's IAM policy refuses any write without it, and S3 refuses an existing key |
| Publisher key | `.secrets/models-publisher-aws.env` (user `graphguard-models-publisher`): put new versions under `models/`, read; no delete, no overwrite, no `lakehouse/` |
| Reader key | `.secrets/models-reader-aws.env` (user `graphguard-models-reader`): get `models/*` only → Kubernetes Secret `graphguard-model` |
| Egress | `k8s/networkpolicy-s3.yaml`: S3 us-east-1 ranges on 443, generated from AWS's `ip-ranges.json` — the rest of the internet is refused |
| Code | `src/graphguard/serving/model_store.py` (publish / verify), `model_k8s.py` (Secret, egress) |
| Proof | `tests/serving/test_model_store.py` (fake S3), `test_startup.py` (CI's startup stage), `test_model_store_live.py` (the real keys) |

## A new model

```
just build-artifacts        # as gg-trainer: models/production
just model-publish          # prints the two lines to pin
# edit k8s/rayservice.yaml: GRAPHGUARD_MODEL_VERSION + GRAPHGUARD_MODEL_SHA256
k3s kubectl apply -f k8s/rayservice.yaml   # zero-downtime: the new cluster verifies, then takes over
curl -s http://10.43.3.216:8000/health     # model_version / model_sha256
```

Commit the two lines: git is the record of which model ran when.

## Roll back

Put the previous two lines back and apply. Every published version stays on S3.

## If a new scorer will not start

`k3s kubectl logs` on the new head pod, or its Serve logs under
`/tmp/ray/session_latest/logs/serve/`: a `ModelVerificationError` names what differs
(pinned hash, a file, a missing manifest). The old scorer keeps serving meanwhile —
proven in S5.7's drill (a wrong hash pending for minutes: 1,071 requests, 0 errors).
Fix the pin and apply again: KubeRay updates the pending cluster, verifies it, and
promotes it — no outage.

If S3 cannot be reached (AWS moved its ranges): `just k8s-s3-egress`, apply the policy,
commit the regenerated file.

## Keys

Typed in with `just secret-set models-publisher-aws.env` / `models-reader-aws.env`; after a
reader change, `just k8s-model-secret` and a roll. Both are in `just secrets-status`.
