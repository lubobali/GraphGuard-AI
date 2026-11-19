"""The load generator cannot flatter the result (S5.4)."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from graphguard.serving import loadgen

pytestmark = pytest.mark.unit


def test_percentile_is_nearest_rank():
    xs = [float(i) for i in range(1, 101)]
    assert loadgen.percentile(xs, 0.50) == 50.0
    assert loadgen.percentile(xs, 0.99) == 99.0
    assert loadgen.percentile(xs, 1.0) == 100.0


def test_warmup_is_excluded_and_latency_counts_from_the_intended_time():
    t0 = 100.0
    # (intended, started, ended, ok, timeout, cold_sides)
    recs = [
        (100.0, 100.0, 100.9, True, False, 0),  # warm-up: excluded
        (102.0, 102.5, 102.6, True, False, 1),  # started late: 600 ms, not 100 ms
        (103.0, 103.0, 103.01, True, False, 0),
        (104.0, 104.0, 106.0, False, True, 0),
    ]
    s = loadgen.summarise(recs, rate=1, warmup=1.0, t0=t0)
    assert s["sent"] == 3 and s["ok"] == 2 and s["timeouts"] == 1
    assert s["max_ms"] == pytest.approx(600.0)
    assert s["worst_send_lag_ms"] == pytest.approx(500.0)
    assert s["cold_side_rate"] == 0.25


class _StallingServer(BaseHTTPRequestHandler):
    """Answers at once, except that the whole server stalls for 0.5 s once (one worker,
    like a single busy replica)."""

    stall_at: float = 0.0
    gate = threading.Lock()

    def do_POST(self):  # noqa: N802
        self.rfile.read(int(self.headers["Content-Length"]))
        with self.gate:  # one request at a time
            now = time.perf_counter()
            if self.stall_at <= now < self.stall_at + 0.5:
                time.sleep(self.stall_at + 0.5 - now)
        body = json.dumps({"score": 0.1, "sender_cold": False, "receiver_cold": False}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def test_a_server_stall_shows_in_every_request_that_was_due_during_it():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StallingServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _StallingServer.stall_at = time.perf_counter() + 1.0
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        s = loadgen.run(url, [b"{}"], rate=50, warmup=0.2, duration=2.0, threads=4)
    finally:
        server.shutdown()
    # ~25 requests were due during the 0.5 s stall. Open loop counts them all from their
    # intended time, so p95 sits in the stall; a closed-loop client would show one slow
    # request and a clean p95.
    assert s["max_ms"] >= 400
    assert s["p95_ms"] >= 100, s
    assert s["errors"] == 0 and s["timeouts"] == 0
