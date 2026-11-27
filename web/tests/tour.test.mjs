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
  assert.equal(scoreText([null, null, null]), ""); // S8b.1: no score before the first answer
});

test("the shipped tour: three cases, a mix, an AI opinion against each choice", () => {
  assert.equal(TOUR.cases.length, 3);
  assert.deepEqual(TOUR.cases.map((c) => c.answer.is_laundering), [true, false, true]);
  for (const c of TOUR.cases) {
    assert.deepEqual(new Set(c.reviews.map((r) => r.direction)), new Set(["escalate", "close"]));
    assert.ok(c.ring.edges.length >= 3 && c.reasons.length >= 1);
  }
});

test("no score before the first answer, then counts (S8b.1)", () => {
  assert.equal(scoreText([null, null, null]), "");
  assert.equal(scoreText([true, null, null]), "1 of 1 right");
  assert.equal(scoreText([true, false, null]), "1 of 2 right");
});

test("a rule that flagged a case is its first reason (S8b.1)", () => {
  const c = TOUR.cases[0];
  assert.match(c.reasons[0], /^Rule: the amount is just under a reporting line/);
  for (const x of TOUR.cases) assert.ok(x.reasons.length >= 1 && x.reasons.length <= 4);
});

// S8b.1, from the AI stand-in test (a newcomer and an investigator, screenshots only)
import { opinionLesson, pictureLine } from "../lib/tourLogic.js";

test("the answer names its source: the simulator's answer key, not a fact anyone learns", () => {
  assert.match(verdict("escalate", { is_laundering: true, pattern_type: "FAN-IN" }).what,
    /^The simulator's answer key: this was money laundering\.$/);
  assert.match(verdict("close", { is_laundering: false, pattern_type: null }).what,
    /^The simulator's answer key: this was a normal payment\.$/);
});

test("the picture line says whether the flagged payment was in the scheme and that later payments are not drawn", () => {
  const ring = { is_laundering: true, ring_tx: [10, 11] };
  assert.match(pictureLine(ring, 10), /flagged payment \(blue\) was one of them/);
  assert.doesNotMatch(pictureLine(ring, 99), /was one of them/);
  assert.match(pictureLine(ring, 10), /only what happened up to the flagged payment/);
  assert.match(pictureLine({ is_laundering: false, ring_tx: [] }, 10), /none of these payments belongs to a scheme/);
});

test("the AI's case against you is right only when you were wrong, and the page says which", () => {
  assert.match(opinionLesson(true), /you were right, so this time the AI's case is wrong/i);
  assert.match(opinionLesson(false), /this time the AI pointed the right way/i);
});

test("every shipped case's picture line is true to its own data", () => {
  for (const c of TOUR.cases) {
    const line = pictureLine(c.answer, c.event_id);
    assert.equal(/was one of them/.test(line), c.answer.ring_tx.includes(c.event_id));
  }
});
