// S7.7: the screen's arithmetic and words. node --test tests/
import assert from "node:assert/strict";
import test from "node:test";
import { capacitySentence, kFor, nearest, perDayFor, scale, teamSize, ticks, topShare } from "../lib/logic.js";

const R100 = {
  system: { caught: 167, missed: 916, rings_caught: 35, rings_total: 168 },
  rules: { caught: 1, rings_caught: 0 },
};

test("a daily workload maps to the same k as the API (100 a day -> 211)", () => {
  assert.equal(kFor(100), 211);
  assert.equal(kFor(0.01), 1);
  assert.equal(kFor(100000), 5000);
  assert.equal(Math.round(perDayFor(5000)), 2373);
});

test("the sentence speaks in counts, with the team and the rules", () => {
  const s = capacitySentence(100, R100);
  assert.equal(s.lead, "A team of about 5 investigators working 100 alerts a day catches " +
    "167 of 1,083 laundering transactions and 35 of 168 rings.");
  assert.equal(s.missed, "It misses 916.");
  assert.equal(s.rules, "Simple rules alone, same workload: 1 transaction and 0 rings.");
  assert.ok(!/[%$€]/.test(s.lead + s.missed + s.rules));
});

test("team size and plural forms", () => {
  assert.equal(teamSize(10), 1);
  assert.equal(teamSize(1000), 50);
  assert.match(capacitySentence(10, R100).lead, /^A team of one investigator/);
});

test("top share reads like a ranking, never a probability", () => {
  assert.equal(topShare(99.9997), "Top 0.01%");
  assert.equal(topShare(99.5), "Top 0.50%");
  assert.equal(topShare(90), "Top 10.0%");
});

test("scales and ticks", () => {
  const x = scale(0, 100, 0, 500);
  assert.equal(x(50), 250);
  assert.equal(x.invert(250), 50);
  assert.deepEqual(ticks(1000, 5), [0, 200, 400, 600, 800, 1000]);
  assert.deepEqual(ticks(542, 5), [0, 200, 400, 600]);
});

test("the crosshair snaps to the nearest point", () => {
  const pts = [{ perDay: 0 }, { perDay: 10 }, { perDay: 20 }];
  assert.equal(nearest(pts, 13).perDay, 10);
});
