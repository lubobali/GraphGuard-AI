# Runbook — the box's front door (S5b.4)

Two things, both GraphGuard's own:

1. **The guard.** k3s on one node has no reason to be reachable from the internet. Its
   ports are dropped in GraphGuard's own chain `GRAPHGUARD-EDGE` (IPv4 and IPv6), reached
   by one jump first in `INPUT` that matches **the public interface only** — pods,
   Tailscale, localhost and Docker never enter it, and Docker's published ports never pass
   `INPUT`. Nothing was restarted to add it. Code: `src/graphguard/ops/edge.py`.
2. **The watchdog.** Daily (06:00 UTC, `graphguard-edge-check.timer`), read-only: the cloud
   firewall attached to this server is unchanged, the box's public listeners match a
   private baseline, and the guard is still in place. Its details (the baseline, the
   status file) live only in `private/edge/`.

| | |
|---|---|
| Boot | `graphguard-edge.service` re-applies the guard after k3s and Docker start |
| Cloud token | `.secrets/hetzner-readonly.env` — **Read** only (a write is refused, checked) |
| Health | `just edge-status` — exit 1 if the last check failed or is > 2 days old, or the guard is missing |

## Everyday

```
just edge-status        # last check, packets dropped so far, problems
just edge-check         # run the watchdog now
journalctl -u graphguard-edge-check --since -2d
```

## When `edge-status` says FAIL

- **guard missing / changed** → `just edge-dry-run` shows what would be fixed, then
  `systemctl restart graphguard-edge` (idempotent).
- **new public listener** → find its owner (`ss -lntup`). GraphGuard's: bind it to
  127.0.0.1. Another project's: tell its session; do not change it. If it is wanted,
  accept it on purpose: `just edge-baseline`.
- **cloud firewall changed** → look in the cloud console first. If the change was meant,
  `just edge-baseline`.
- **could not check** → token expired or revoked, or the cloud API down: a failed check,
  never a pass.

## Removing the guard (one command)

```
just edge-remove                      # now
systemctl disable graphguard-edge     # and not at the next boot
```

Changing it: edit `GUARDED` in `edge.py`, then `just edge-dry-run`, then `just edge-apply`
(arms a 5-minute automatic undo; `just edge-confirm` keeps it after checking every site).

**Never** use `iptables-restore`, `iptables -F` on a chain that is not ours,
`nft flush ruleset`, or `k3s-killall.sh` — Docker's and k3s's rules live in the same tables.

The full host firewall for the box is S5b.4b, planned together with the LuBot session.
