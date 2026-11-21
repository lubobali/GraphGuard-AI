"""The replayer (S6.5): a bank that sends like a real one, with real-world mess, deterministically.

Pure parts here (messages, pacing, the fault plan, checkpoints with a fake producer); the live
replay into Kafka is test_replayer_live.py.
"""

import datetime as dt
import json

import pytest

from graphguard.stream import messages as msg
from graphguard.stream import replayer as rp

pytestmark = pytest.mark.unit

T0 = dt.datetime(2022, 9, 6, 13, 34)


def _row(i, minutes=0):
    return {
        "source_row": 1000 + i,
        "timestamp": T0 + dt.timedelta(minutes=minutes),
        "from_bank": "010",
        "from_account": f"S{i % 7}",
        "to_bank": "011",
        "to_account": f"R{i % 5}",
        "amount_received": 10.5 + i,
        "receiving_currency": "US Dollar",
        "amount_paid": 10.5 + i,
        "payment_currency": "US Dollar",
        "payment_format": "ACH",
        "is_laundering": i % 2,
    }


ROWS = [_row(i, minutes=i // 3) for i in range(300)]  # 3 per minute: ties


# --- messages ----------------------------------------------------------------------------
def test_a_message_carries_the_transaction_but_never_its_label():
    body = json.loads(msg.encode(ROWS[0], seq=0))
    assert body["event_id"] == 1000 and body["seq"] == 0
    assert body["schema_version"] == 1
    assert "is_laundering" not in body  # labels arrive late, on their own stream (S6.9)
    assert body["timestamp"] == "2022-09-06T13:34:00"


def test_decode_round_trips_exactly():
    e = msg.decode(msg.encode(ROWS[5], seq=5))
    assert (e.event_id, e.timestamp, e.amount_paid, e.from_account) == (
        1005,
        ROWS[5]["timestamp"],
        ROWS[5]["amount_paid"],
        ROWS[5]["from_account"],
    )


def test_amounts_survive_json_bit_for_bit():
    row = {**ROWS[0], "amount_paid": 0.1 + 0.2}
    assert msg.decode(msg.encode(row, seq=0)).amount_paid == 0.1 + 0.2


@pytest.mark.parametrize("bad", [b"", b"not json", b"[]", b'{"schema_version": 1}',
                                 b'{"schema_version": 9, "event_id": 1}'])  # fmt: skip
def test_malformed_records_are_refused_with_a_reason(bad):
    with pytest.raises(msg.MalformedRecord):
        msg.decode(bad)


def test_schema_v2_adds_a_field_and_v1_readers_still_work():
    v2 = msg.encode(ROWS[0], seq=0, schema_version=2)
    assert json.loads(v2)["channel"] == "online"
    assert msg.decode(v2).event_id == 1000


# --- pacing ------------------------------------------------------------------------------
def test_true_time_keeps_the_real_gaps_and_speed_divides_them():
    times = [T0, T0 + dt.timedelta(minutes=1), T0 + dt.timedelta(minutes=3)]
    assert rp.send_offsets(times, speed=1) == [0.0, 60.0, 180.0]
    assert rp.send_offsets(times, speed=60) == [0.0, 1.0, 3.0]
    assert rp.send_offsets(times, speed=None) == [0.0, 0.0, 0.0]  # as fast as possible


def test_a_burst_compresses_wall_time_but_never_event_time():
    times = [T0 + dt.timedelta(minutes=m) for m in range(10)]
    plain = rp.send_offsets(times, speed=60)
    window = (T0 + dt.timedelta(minutes=2), T0 + dt.timedelta(minutes=6), 10.0)
    burst = rp.send_offsets(times, speed=60, bursts=[window])
    assert burst[-1] < plain[-1]
    assert all(b2 >= b1 for b1, b2 in zip(burst, burst[1:], strict=False))  # still monotone


# --- the fault plan ------------------------------------------------------------------------
FAULTS = rp.Faults(duplicate=0.02, late=0.02, late_max_shift=20, malformed=0.01,
                   schema_v2_from=0.5, seed=7)  # fmt: skip


def test_the_plan_is_deterministic_for_a_seed():
    a = rp.plan(ROWS, FAULTS)
    b = rp.plan(ROWS, FAULTS)
    assert [(s.kind, s.index) for s in a.sends] == [(s.kind, s.index) for s in b.sends]
    assert a.log == b.log


def test_every_event_is_sent_at_least_once_and_event_time_is_never_touched():
    p = rp.plan(ROWS, FAULTS)
    sent = [s.index for s in p.sends if s.kind in {"event", "duplicate"}]
    assert set(sent) == set(range(len(ROWS)))
    for s in p.sends:
        if s.kind != "malformed":
            assert json.loads(p.body(s))["timestamp"] == ROWS[s.index]["timestamp"].isoformat()


def test_faults_happen_and_are_logged():
    p = rp.plan(ROWS, FAULTS)
    kinds = {e["fault"] for e in p.log}
    assert {"duplicate", "late", "malformed", "schema_v2"} <= kinds


def test_late_events_move_at_most_the_allowed_number_of_positions():
    p = rp.plan(ROWS, FAULTS)
    order = [s.index for s in p.sends if s.kind == "event"]
    for pos, idx in enumerate(order):
        assert abs(pos - idx) <= FAULTS.late_max_shift + 1


def test_no_faults_means_exactly_the_rows_in_order():
    p = rp.plan(ROWS, rp.Faults())
    assert [s.index for s in p.sends] == list(range(len(ROWS)))
    assert p.log == []


# --- checkpoints ---------------------------------------------------------------------------
class FakeProducer:
    def __init__(self, fail_after=None):
        self.sent, self.fail_after = [], fail_after

    def produce(self, topic, value, key=None, on_delivery=None):
        if self.fail_after is not None and len(self.sent) >= self.fail_after:
            raise RuntimeError("crash")
        self.sent.append(value)

    def poll(self, _):
        return 0

    def flush(self, _=None):
        return 0


def test_a_restart_resumes_from_the_checkpoint_without_losing_anything(tmp_path):
    ck = tmp_path / "checkpoint.json"
    p = rp.plan(ROWS, rp.Faults())
    first = FakeProducer(fail_after=130)
    with pytest.raises(RuntimeError):
        rp.send(p, first, ck, speed=None, batch=50)
    assert json.loads(ck.read_text())["next"] == 100  # last fully flushed batch
    second = FakeProducer()
    rp.send(p, second, ck, speed=None, batch=50)
    got = {json.loads(b)["event_id"] for b in first.sent[:100] + second.sent}
    assert got == {r["source_row"] for r in ROWS}
    assert len(second.sent) == len(ROWS) - 100  # resumed, not restarted
    assert json.loads(ck.read_text())["next"] == len(p.sends)


def test_a_finished_run_sends_nothing_more(tmp_path):
    ck = tmp_path / "checkpoint.json"
    p = rp.plan(ROWS, rp.Faults())
    rp.send(p, FakeProducer(), ck, speed=None)
    again = FakeProducer()
    rp.send(p, again, ck, speed=None)
    assert again.sent == []
