import assert from "node:assert/strict";
import test from "node:test";
import { FEATURE_NAMES, contributionBars, playOrder, toFlow } from "../lib/caseLogic.js";

const GRAPH = {
  alert: 10,
  nodes: [{ id: "1:S", seed: "sender", name: "Corp A", bank: "Bank 1" },
          { id: "1:R", seed: "receiver", name: "Corp B", bank: "Bank 1" },
          { id: "1:U", seed: null, name: null, bank: null }],
  edges: [{ id: 10, from: "1:S", to: "1:R", t: "2022-09-07 12:00:00", amount: 9500, currency: "Euro", format: "ACH", role: "alert", rank: 3 },
          { id: 2, from: "1:U", to: "1:S", t: "2022-09-07 11:00:00", amount: 9600, currency: "Euro", format: "ACH", role: "upstream" }],
  more: [{ node: "1:S", direction: "in", count: 14 }],
};

test("every one of the model's 15 features has a plain name", () => {
  assert.equal(Object.keys(FEATURE_NAMES).length, 15);
  assert.match(FEATURE_NAMES.weekday, /simulator/);
});

test("contribution bars keep the biggest pushes, split up and down on one scale", () => {
  const bars = contributionBars([
    { feature: "hour", value: 3, contribution: 0.5 },
    { feature: "weekday", value: 3, contribution: -2.0 },
    { feature: "log_amount", value: 9, contribution: 1.0 },
  ], 2);
  assert.deepEqual(bars.map((b) => b.feature), ["weekday", "log_amount"]);
  assert.deepEqual(bars.map((b) => b.direction), ["down", "up"]);
  assert.deepEqual(bars.map((b) => b.share), [1, 0.5]);
});

test("the ring becomes flow nodes and edges, the alert marked, hubs as +N more", () => {
  const f = toFlow(GRAPH);
  assert.equal(f.nodes.length, 4);
  assert.equal(f.nodes.find((n) => n.id === "1:S").kind, "sender");
  assert.equal(f.nodes.find((n) => n.id === "1:U").name, "U"); // unnamed -> its account number
  assert.equal(f.edges.find((e) => e.tx === 10).alert, true);
  const more = f.nodes.find((n) => n.kind === "more");
  assert.equal(more.name, "+14 more");
  assert.ok(f.edges.some((e) => e.source === more.id && e.target === "1:S"));
});

test("play reveals the money in time order and skips the +N more links", () => {
  assert.deepEqual(playOrder(toFlow(GRAPH).edges), ["e2", "e10"]);
});
