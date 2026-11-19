"""The latency budget, as code (S5.4).

p99 under 50 ms end to end is measured on the real k3s system (`graphguard.serving.
loadgen`, FINDING in docs/findings.md). CI cannot run k3s, so it guards the part of the
path that is ours: feature assembly + inference, in process. That part gets a fixed share
of the budget; network, Ray Serve and Redis get the rest.
"""

from __future__ import annotations

import time
from collections.abc import Callable

BUDGET_MS = 50.0
COMPUTE_SHARE_MS = 10.0  # feature assembly + inference; measured ~1-2 ms (S5.4)


def p99_ms(fn: Callable[[], object], n: int = 500, warmup: int = 50) -> float:
    """p99 of `fn` in milliseconds over `n` timed calls after `warmup` untimed ones."""
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    return times[min(len(times) - 1, int(0.99 * len(times)))]


def assert_within(
    fn: Callable[[], object], budget_ms: float = COMPUTE_SHARE_MS, n: int = 500, warmup: int = 50
) -> float:
    p99 = p99_ms(fn, n=n, warmup=warmup)
    if p99 >= budget_ms:
        raise AssertionError(f"p99 {p99:.2f} ms is over the {budget_ms} ms budget")
    return p99
