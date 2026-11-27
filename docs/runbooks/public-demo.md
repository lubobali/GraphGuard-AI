# Runbook: the public demo (S8b.2, S8b.3)

The investigator demo at `graphguard.lubobali.com`: the box's shared nginx (owned by the LuBot
session) terminates HTTPS and forwards to the `graphguard-demo-api` container on
`127.0.0.1:8130`, which serves the static site and `/api`. The data is synthetic (IBM
AMLworld); nothing a visitor does reaches the stream, the scorer or the models.

## Turn it off / on

| | |
|---|---|
| Off (kill switch) | `just demo-api-down`: the site answers 502, nothing else changes |
| On | `just demo-api-up` |
| Logs | `just demo-api-logs` (errors are logged here, never shown to visitors) |
| Remove the site | ask the LuBot session to remove the nginx site (it owns nginx) |

## What protects it

- **Two layers of rate limits** per visitor address: nginx's, then the API's own. The API
  takes the address from `X-Real-IP` only when the request comes through the proxy
  (`GRAPHGUARD_TRUSTED_PROXY`, the Docker network's gateway). Otherwise every visitor
  would share one limit.
- **Daily write caps:** 300 saved actions per address, 20,000 for all visitors together, over 24
  hours. Over the cap the site still reads and says "the demo is full for today".
- **Bounded work:** the limiter forgets idle addresses; the manager's all-visitors view is
  linear and cached for 30 s; every query stops after 5 s; database connections are shared
  through a waiting pool (busy → 503, never a crash); at most 4 live streams, one per address.
- **Nothing inside leaks:** a crash answers `{"detail": "internal error"}`; strict security
  headers on every response; no API docs routes; read-only container, 256M cap.
- **The answer key is public on purpose.** It is a training demo on synthetic data. The key shows
  after a decision, in the tour, and through the case page's "Show the answer key" button.

## Visitor data

Visitors' decisions are rows in `case_actions` (append-only for the API). Clean up with
`just demo-visitors-clear DAYS` (deletes rows older than DAYS days; 0 = all). Sam's seeded
decisions live in code and are never deleted. Tests never run a short cut on the live
database: a 1-day cut once deleted a real visitor's row (restored from the nightly backup).

## Load, measured 2026-11-27 (image 0.1.24)

`uv run python scripts/ops/demo_load.py --visitors 50 --seconds 60`: 50 simulated visitors,
each from its own address, each clicking 3–4 times a second (much faster than a person). Result:
4,544 requests, **0 errors**, p50 395 ms, p95 696 ms, p99 901 ms; API memory 38 → 61 MiB of
256; LuBot's health unchanged before and after. The first run (0.1.23) failed 31% of requests:
the database pool raised instead of waiting once more than 4 requests ran at once. That is
fixed (`queries.WaitingPool`) and tested. The script marks its visitors' ids; delete their rows
by id afterwards, never by age.
