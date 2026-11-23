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

test("the sentence says who finds what: the model ranks, the team checks (Lubo, 2026-11-23)", () => {
  const s = capacitySentence(100, R100);
  assert.equal(s.lead, "If your team checks the top 100 payments a day (about 5 people), " +
    "they find 167 of the 1,083 laundering payments, and 35 of the 168 laundering groups.");
  assert.equal(s.missed, "The other 916 are lower on the list, never checked.");
  assert.equal(s.rules, "With old-style fixed rules instead of the model, the same 100 checks " +
    "a day find 1 laundering payment and 0 groups.");
  assert.ok(!/[%$€]/.test(s.lead + s.missed + s.rules));
  assert.ok(!/catches/.test(s.lead), "the team does not catch; the model ranks");
});

test("team size and plural forms", () => {
  assert.equal(teamSize(10), 1);
  assert.equal(teamSize(1000), 50);
  assert.match(capacitySentence(10, R100).lead, /\(one person\)/);
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

test("line-end labels never overlap and keep their order", async () => {
  const { spreadLabels } = await import("../lib/logic.js");
  const ys = spreadLabels([40, 300, 304], 14, 0, 310); // system high, rules and random close
  assert.equal(ys[0], 40);
  assert.ok(ys[2] - ys[1] >= 14 && ys[1] < ys[2]);
  assert.ok(Math.max(...ys) <= 310);
  assert.deepEqual(spreadLabels([10, 100], 14, 0, 300), [10, 100]); // far apart: untouched
});
