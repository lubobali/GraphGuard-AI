"""The consumer (S6.6): every transaction scored once, in training's order, whatever arrives.

Pure parts and the whole step with fakes for Kafka's messages, Postgres and the model (Redis
is the real updater's memory store). The live run against Kafka/Redis/Postgres is
test_consumer_live.py; exactness of the features themselves is S6.3's proof.
"""

import datetime as dt
import json

import pytest

from graphguard.serving.online_features import account_states_frame, recent_sends_frame
from graphguard.stream import consumer as cs
from graphguard.stream import messages as msg
from graphguard.stream import updater as up

pytestmark = pytest.mark.unit

from graphguard.stream import rules as R  # noqa: E402

# Small thresholds so the fixture's few accounts can fire rules.
TH = R.Thresholds(velocity_24h=3, fan_out=2, fan_in=2, large_amount=40.0,
                  alert_priority=0.65, alert_capacity=5)  # fmt: skip

T0 = dt.datetime(2022, 9, 6, 13, 34)


def _row(i, minute):
    return {
        "source_row": 100 + i,
        "timestamp": T0 + dt.timedelta(minutes=minute),
        "from_bank": "010",
        "from_account": f"S{i % 5}",
        "to_bank": "011",
        "to_account": f"R{i % 3}",
        "amount_received": 10.0 + i,
        "receiving_currency": "US Dollar",
        "amount_paid": 10.0 + i,
        "payment_currency": "US Dollar",
        "payment_format": "ACH",
    }


ROWS = [_row(i, i // 2) for i in range(60)]


class Msg:
    def __init__(self, value, offset):
        self._v, self._o = value, offset

    def value(self):
        return self._v

    def offset(self):
        return self._o

    def error(self):
        return None


def _msgs(bodies, start=0):
    return [Msg(b, start + i) for i, b in enumerate(bodies)]


class FakeSink:
    def __init__(self):
        self.decisions, self.dead, self.offset, self.outbox, self.commits = {}, [], None, [], 0

    def decided(self, ids):
        return {i for i in ids if i in self.decisions}

    def commit(self, decisions, dead, next_offset, outbox):
        for d in decisions:
            self.decisions.setdefault(d.event_id, d)
        self.dead += dead
        self.offset = next_offset
        self.outbox += outbox
        self.commits += 1


class FakeModel:
    feature_columns = ("sender_n_sent_before", "receiver_n_received_before", "log_amount")
    category_maps = {"payment_currency": {"US Dollar": 0}}

    def score_rows(self, rows):
        return [round(r["log_amount"] / 10 + r["sender_n_sent_before"] / 1000, 9) for r in rows]


def _consumer(buffer=10):
    store = up.MemoryStore()
    empty = account_states_frame(_empty(), T0)
    up.seed(store, empty, recent_sends_frame(_empty(), T0), up.edges_frame(_empty(), T0), T0)
    sink = FakeSink()
    c = cs.Consumer(
        store=store,
        sink=sink,
        model=FakeModel(),
        model_info={"version": "test", "sha256": "0" * 64},
        buffer_size=buffer,
        thresholds=TH,
    )
    return c, sink, store


def _empty():
    import polars as pl

    return pl.LazyFrame(
        schema={
            "timestamp": pl.Datetime("us"),
            "from_account": pl.String,
            "to_account": pl.String,
            "amount_paid": pl.Float64,
        }
    )


def _bodies(rows):
    return [msg.encode(r, seq=i) for i, r in enumerate(rows)]


# --- the reorder buffer ------------------------------------------------------------------
def test_the_buffer_releases_in_training_order_once_it_is_full():
    buf = cs.ReorderBuffer(3)
    out = []
    for off, key in enumerate([(2, 0), (1, 0), (3, 0), (0, 0), (4, 0), (5, 0)]):
        out += buf.push(key, f"e{key[0]}", off)
    out += buf.drain()
    assert out == ["e0", "e1", "e2", "e3", "e4", "e5"]


def test_resume_offset_is_the_oldest_held_message():
    buf = cs.ReorderBuffer(2)
    buf.push((5, 0), "a", 10)
    buf.push((1, 0), "b", 11)
    buf.push((9, 0), "c", 12)  # releases "b" (offset 11)
    assert buf.resume_offset(last=12) == 10  # "a" at offset 10 is still held
    buf.drain()
    assert buf.resume_offset(last=12) == 13


# --- the whole step ----------------------------------------------------------------------
def test_every_transaction_gets_exactly_one_decision():
    c, sink, _ = _consumer()
    c.step(_msgs(_bodies(ROWS)))
    c.flush()
    assert sorted(sink.decisions) == [r["source_row"] for r in ROWS]
    assert sink.offset == len(ROWS)


def test_shuffled_late_arrivals_inside_the_buffer_give_the_same_decisions():
    c1, s1, _ = _consumer(buffer=10)
    c1.step(_msgs(_bodies(ROWS)))
    c1.flush()
    late = _bodies(ROWS)
    late.insert(25, late.pop(18))  # event 18 arrives 7 positions late
    c2, s2, _ = _consumer(buffer=10)
    c2.step(_msgs(late))
    c2.flush()
    assert {k: v.score for k, v in s1.decisions.items()} == {
        k: v.score for k, v in s2.decisions.items()
    }
    assert s2.dead == []


def test_a_late_record_inside_one_batch_is_still_applied_in_order():
    late = _bodies(ROWS)
    late.append(late.pop(3))  # late, but every record arrives in the same batch
    c, sink, _ = _consumer(buffer=10)
    c.step(_msgs(late))
    c.flush()
    c1, s1, _ = _consumer(buffer=10)
    c1.step(_msgs(_bodies(ROWS)))
    c1.flush()
    assert {k: v.score for k, v in sink.decisions.items()} == {
        k: v.score for k, v in s1.decisions.items()
    }


def test_too_late_for_the_buffer_goes_to_dead_letters_not_a_wrong_score():
    late = _bodies(ROWS)
    late.append(late.pop(3))  # 56 positions late, buffer 10
    c, sink, _ = _consumer(buffer=10)
    records = _msgs(late)
    for i in range(0, len(records), 5):  # Kafka hands them over in small batches
        c.step(records[i : i + 5])
    c.flush()
    assert [d["reason"] for d in sink.dead] == ["late"]
    assert 103 not in sink.decisions


def test_duplicates_are_dropped_whenever_they_arrive():
    bodies = _bodies(ROWS)
    dup = bodies + [bodies[5], bodies[40]]
    c, sink, _ = _consumer()
    c.step(_msgs(dup))
    c.flush()
    assert len(sink.decisions) == len(ROWS) and sink.dead == []


def test_a_restart_from_the_stored_offset_changes_nothing():
    bodies = _bodies(ROWS)
    c, sink, store = _consumer()
    c.step(_msgs(bodies[:35]))  # crash here: 25 decided, 10 still in the buffer
    held_from = sink.offset
    scores = {k: v.score for k, v in sink.decisions.items()}
    c2 = cs.Consumer(
        store=store,
        sink=sink,
        model=FakeModel(),
        model_info={"version": "test", "sha256": "0" * 64},
        buffer_size=10,
        thresholds=TH,
    )
    c2.step(_msgs(bodies[held_from:], start=held_from))  # Kafka redelivers from there
    c2.flush()
    assert sorted(sink.decisions) == [r["source_row"] for r in ROWS]
    assert all(sink.decisions[k].score == v for k, v in scores.items())
    assert sink.dead == []


def test_malformed_records_become_dead_letters_and_the_stream_goes_on():
    bodies = _bodies(ROWS)
    bodies.insert(10, b"not json")
    c, sink, _ = _consumer()
    c.step(_msgs(bodies))
    c.flush()
    assert [d["reason"].split(":")[0] for d in sink.dead] == ["malformed"]
    assert len(sink.decisions) == len(ROWS)


def test_each_decision_records_the_model_and_the_features_it_saw():
    c, sink, _ = _consumer()
    c.step(_msgs(_bodies(ROWS[:12])))
    c.flush()
    d = sink.decisions[105]
    assert d.model_version == "test" and len(d.features) == len(FakeModel.feature_columns)
    assert d.cold_policy in {
        "warm",
        "scored: sender new",
        "scored: receiver new",
        "review: both accounts new",
    }


def test_decisions_are_published_through_the_outbox():
    c, sink, _ = _consumer()
    c.step(_msgs(_bodies(ROWS[:12])))
    c.flush()
    topics = {o["topic"] for o in sink.outbox}
    assert topics <= {"decisions", "alerts"}  # alerts: S6.8
    assert {
        json.loads(o["payload"])["event_id"] for o in sink.outbox if o["topic"] == "decisions"
    } == {r["source_row"] for r in ROWS[:12]}


def test_the_score_uses_the_features_before_the_transaction():
    c, sink, _ = _consumer()
    c.step(_msgs(_bodies(ROWS)))
    c.flush()
    first_of_s0 = sink.decisions[100]  # S0's first send: nothing sent before
    later_of_s0 = sink.decisions[105]  # S0 again: one send before
    names = FakeModel.feature_columns
    assert first_of_s0.features[names.index("sender_n_sent_before")] == 0
    assert later_of_s0.features[names.index("sender_n_sent_before")] == 1


def test_a_crash_between_redis_and_postgres_loses_and_doubles_nothing():
    bodies = _bodies(ROWS)
    c1, s1, _ = _consumer()
    c1.step(_msgs(bodies))
    c1.flush()
    want = {k: v.score for k, v in s1.decisions.items()}

    c, sink, store = _consumer()
    c.crash_at = 130  # inside the second released batch
    records = _msgs(bodies)
    with pytest.raises(cs.ChaosCrash):
        for i in range(0, len(records), 15):
            c.step(records[i : i + 15])
    assert 130 not in sink.decisions  # Redis has it, Postgres does not
    resume = sink.offset or 0
    c2 = cs.Consumer(
        store=store,
        sink=sink,
        model=FakeModel(),
        model_info={"version": "test", "sha256": "0" * 64},
        buffer_size=10,
        thresholds=TH,
        crash_after_redis_at=130,
    )  # the hook is still set: must not fire twice
    c2.step(_msgs(bodies[resume:], start=resume))
    c2.flush()
    assert {k: v.score for k, v in sink.decisions.items()} == want
    assert sink.dead == []


def test_a_redelivered_dead_letter_is_not_published_twice():
    outbox = [{"topic": "decisions", "key": "1", "payload": "{}"},
              {"topic": "transactions.dlq", "key": "None",
               "payload": json.dumps({"kafka_offset": 7, "reason": "malformed"})},
              {"topic": "transactions.dlq", "key": "None",
               "payload": json.dumps({"kafka_offset": 9, "reason": "malformed"})}]  # fmt: skip
    kept = cs.only_new_dead_letters(outbox, inserted_offsets={9})
    assert [o["topic"] for o in kept] == ["decisions", "transactions.dlq"]
    assert json.loads(kept[1]["payload"])["kafka_offset"] == 9


def test_rules_fire_live_and_alerts_go_to_their_own_topic_with_reasons():
    c, sink, _ = _consumer()
    c.step(_msgs(_bodies(ROWS)))
    c.flush()
    fired = [d for d in sink.decisions.values() if d.rules]
    assert fired, "the fixture should trip at least one rule"
    for d in sink.decisions.values():
        assert d.alert == (R.priority(d.score, d.rules) >= TH.alert_priority)
    alerts = [json.loads(o["payload"]) for o in sink.outbox if o["topic"] == "alerts"]
    assert {a["event_id"] for a in alerts} == {
        d.event_id for d in sink.decisions.values() if d.alert
    }
    assert all(a["reasons"] for a in alerts)
