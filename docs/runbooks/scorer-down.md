# Runbook — the k3s scorer is down

**Symptom:** `just k8s-check` exits 1, or `just k8s-status` shows the scorer pod not
`1/1 Running`.

**Blast radius:** GraphGuard scoring only. LuBot, Forgejo, Sentinel and every other app
on the box are separate. Nothing in this runbook touches them.

**Never run `k3s-killall.sh`.** It rewrites the whole iptables table and takes
lubot.ai offline. If it ever happens: `systemctl restart docker`.

---

## 1. See what is wrong

```
just k8s-check                      # one line per problem
just k8s-status                     # RayService + pods
k3s kubectl describe pod -n graphguard <pod> | tail -20   # the Events section
```

## 2. Fix by cause

| `k8s-check` says | Cause | Fix |
|---|---|---|
| `image … missing from k3s containerd` or pod `ImagePullBackOff` | Image deleted (k3s image GC, disk full). There is no registry, so k3s cannot pull it back | `just image-import` (re-imports from Docker **and pins**), then step 3. If Docker no longer has the image either: `just image-build` |
| `image … not pinned` | Imported without the pin | `just image-import` |
| pod `CrashLoopBackOff` | The app starts and dies | `just k8s-logs`. Usually the model bundle or Redis (step 4) |
| pod `not ready: Running` | Ray up, Serve app not healthy | `k3s kubectl get rayservice -n graphguard -o yaml \| grep -A5 applicationStatuses`, then `just k8s-logs` |
| `no pods running` | RayService/RayCluster gone, or the operator is down | `k3s kubectl get pods -n ray-system`; re-apply with `just k8s-deploy` |
| `could not query k3s for pods` | k3s itself is down | `systemctl status k3s`. Restart with `systemctl restart k3s` — **not** killall |

## 3. Restart the pod (after fixing the cause)

```
k3s kubectl delete pod -n graphguard <pod>   # KubeRay recreates it
just k8s-status                               # wait for 1/1 Running, Serve RUNNING
```

## 4. Prove it works, and that it reaches Redis

```
just k8s-check     # must print "healthy", exit 0
just k8s-smoke     # /health
```

If Redis was restarted or emptied (it keeps nothing on disk), refill it from the
lakehouse — **no retraining**, about 15 s, peak ~0.55 GB, in place so the store is
never empty mid-reload:

```
just store-load      # gold.account_features_asof -> Redis, 512,705 accounts
```

If the lakehouse itself is gone: `just lakehouse-build` (CSV -> Iceberg, ~10 s, peak
~1.2 GB), then `just store-load`. Do not run either while MLflow is busy with a big
training run (memory peaks would overlap).

Score one transaction between two **stored** accounts (pick two keys with
`docker exec graphguard-redis redis-cli --scan --count 100 | head -2`, strip `gg:acct:`).
Expect `"sender_cold": false`. If every account comes back cold, Redis is not reachable
from the pod — check `GRAPHGUARD_REDIS_URL` in `k8s/rayservice.yaml` and
`docker ps | grep graphguard-redis`.

## 5. Check the rest of the box is untouched

```
docker ps --format '{{.Names}}' | grep -cE '^(lubot|forgejo|sentinel)'   # same count as before
curl -sf https://lubot.ai/health && echo OK
df -h /            # k3s starts deleting images at ~85% disk
```

---

**History:** 2026-10-30 → 2026-11-18, the scorer sat in ImagePullBackOff for 18 days
after k3s image GC deleted `serving:0.1.2` during a disk-full period. Fixed in S5.1,
made detectable and pinned in S5.2. The email alert that runs this check on a schedule
is planned for the start of Phase 6, when the stream first depends on the scorer.
