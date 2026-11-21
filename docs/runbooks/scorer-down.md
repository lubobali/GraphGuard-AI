# Runbook — the k3s scorer is down

**Symptom:** a `[GraphGuard] scorer DOWN` email (S6.1), or `just k8s-check` exits 1, or
`just k8s-status` shows the scorer pod not `1/1 Running`.

**Blast radius:** GraphGuard scoring only. LuBot, Forgejo, Sentinel and every other app
on the box are separate. Nothing in this runbook touches them.

**Never run `k3s-killall.sh`.** It rewrites the whole iptables table and takes
lubot.ai offline. If it ever happens: `systemctl restart docker`.

---

## 0. The alert emails (S6.1)

Every 5 minutes `graphguard-alert.timer` runs the same check as `just k8s-check` plus the
scorer's own `/health` (asked from inside its pod). **It emails only when the state
changes**, after two checks in a row agree, so a one-check blip (a rolling upgrade)
emails nobody.

| Email | Means |
|---|---|
| `[GraphGuard] scorer DOWN since …` | two checks in a row failed; the email lists what failed |
| `[GraphGuard] scorer still DOWN since …` | still broken, once every 24 h |
| `[GraphGuard] scorer recovered (down N min)` | two checks in a row passed again |
| `[GraphGuard][DRILL] …` | `just alert-drill`; nothing is broken |

```
just alert-status      # last check, state, last email; exit 1 if stale, mail failing, or broken
just alert-check       # one check now
just health            # every health check: backups, edge, secrets, alert, k3s
just alert-pause 2h    # planned work: emails silenced, state still tracked (alert-resume)
journalctl -u graphguard-alert --since -1h
```

If the scorer is still broken when a pause ends, the DOWN email goes out then; an outage
that starts and ends inside a pause stays silent. A failed email is retried every check.

- **`alert-status` says stale:** the timer is not running —
  `systemctl status graphguard-alert.timer`; `just alert-install` re-installs it.
- **`alert-status` says mail failing:** check the key (`just secrets-status`), that the SES
  identity is still verified (AWS console → SES → Identities), and the journal.

How it works: `src/graphguard/ops/alert.py` (the judgement is the pure `step`). Email goes
through AWS SES with `.secrets/alerts-aws.env` (IAM user `graphguard-alerts`, allowed only
to send from the one verified address); the addresses are in `.secrets/alerts-mail.env`;
state in `private/alerts/state.json`. The unit is sandboxed and gets its two secrets as
systemd credentials. `just alert-drill` sends a DRILL "down" + "recovered" through the real
path without touching the scorer or the real state. Phase 8 monitoring replaces it.

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
| `scorer /health 503: feature store not loaded` | Redis restarted and is empty (S5.5: the scorer refuses cold scores) | `just store-load` (step 4) |
| `scorer /health 503: feature store unavailable` | Redis down or unreachable | `docker ps --filter name=graphguard-redis`, then `just store-load` |
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
made detectable and pinned in S5.2. Since S6.1 (2026-11-21) the check runs every 5 minutes
and emails on any change, so it cannot go unnoticed again.
