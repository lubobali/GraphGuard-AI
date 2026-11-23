// S7.18: "Try one case" -- the words of each step, and the shipped tour file.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { limitLine, paymentLine, scoreText, verdict } from "../lib/tourLogic.js";

const TOUR = JSON.parse(readFileSync(new URL("../lib/tour.json", import.meta.url)));

test("a payment in one plain sentence; an own-account payment says so", () => {
  const p = { event_time: "2022-09-06 14:02:00", from_name: "Corp A", to_name: "Corp B",
    amount_paid: 9539.79, payment_currency: "Euro" };
  assert.equal(paymentLine(p), "Corp A paid Corp B 9,539.79 Euro on 6 Sep at 14:02.");
  assert.match(paymentLine({ ...p, to_name: "Corp A" }), /paid its own account at another bank/);
});

test("the verdict: right or not, what it was, the scheme in words", () => {
  const ring = { is_laundering: true, pattern_type: "FAN-IN" };
  const clean = { is_laundering: false, pattern_type: null };
  assert.equal(verdict("escalate", ring).right, true);
  assert.match(verdict("escalate", ring).shape, /many accounts sent money into one account/);
  assert.equal(verdict("close", ring).headline, "Not this time.");
  assert.equal(verdict("close", clean).right, true);
  assert.match(verdict("escalate", clean).what, /normal payment/);
});

test("the limit line and the score", () => {
  assert.equal(limitLine({ checked: 211, found: 167, false_alarms: 44, total: 1083 }),
    "The system is not perfect: of the top 211 payments it flags, 44 are false alarms, and it finds 167 of the 1,083 laundering payments.");
  assert.equal(scoreText([true, false, null]), "1 of 2 right");
  assert.equal(scoreText([null, null, null]), "0 of 0 right");
});

test("the shipped tour: three cases, a mix, an AI opinion against each choice", () => {
  assert.equal(TOUR.cases.length, 3);
  assert.deepEqual(TOUR.cases.map((c) => c.answer.is_laundering), [true, false, true]);
  for (const c of TOUR.cases) {
    assert.deepEqual(new Set(c.reviews.map((r) => r.direction)), new Set(["escalate", "close"]));
    assert.ok(c.ring.edges.length >= 3 && c.reasons.length >= 1);
  }
});
