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

test("the agent's report keeps checked claims and shows dropped ones with the reason", async () => {
  const { agentView } = await import("../lib/caseLogic.js");
  const view = agentView([{
    model: "anthropic/claude-sonnet-5.5", at: "2026-11-22",
    report: { summary: "s", typology: "CYCLE", seconds: 9.5,
      kept: [{ text: "A paid B 9,500 Euro.", cites: [10], amount: { value: 9500, currency: "Euro" } }],
      dropped: [{ text: "A sent 12,000 Euro.", cites: [2], why: "number 12,000 in the text is in no cited payment" }] },
  }]);
  assert.equal(view[0].label, "Claude Sonnet 5.5");
  assert.deepEqual(view[0].kept, [{ text: "A paid B 9,500 Euro.", cites: [10] }]);
  assert.match(view[0].dropped[0].why, /no cited payment/);
  assert.deepEqual(agentView(undefined), []);
});

test("the answer key says YES or NO in plain words", async () => {
  const { answerText } = await import("../lib/caseLogic.js");
  const yes = answerText({ is_laundering: true, pattern_type: "SCATTER-GATHER", ring_hops: new Array(17) });
  assert.equal(yes.verdict, "YES");
  assert.match(yes.detail, /one of 17 payments/);
  assert.match(yes.detail, /split to many accounts, then collected into one/);
  assert.equal(answerText({ is_laundering: false, pattern_type: null, ring_hops: [] }).verdict, "NO");
});

// ---- S7.13: reasons a person can trust ----------------------------------------------
import { ownAccount, typeText, whyFirst } from "../lib/caseLogic.js";

test("own account: same owner, two accounts; same account; or not", () => {
  const base = { from_name: "Corporation #1", to_name: "Corporation #1", from_account: "A", to_account: "B" };
  assert.equal(ownAccount(base).label, "Own account");
  assert.match(ownAccount(base).text, /same owner/);
  assert.equal(ownAccount({ ...base, to_account: "A" }).label, "Same account");
  assert.equal(ownAccount({ ...base, to_name: "Corporation #2" }), null);
  assert.equal(ownAccount({ ...base, from_name: null, to_name: null }), null);
});

test("why it is first: two rules or two new accounts beat the score, said in words", () => {
  assert.match(whyFirst({ rules: ["fan_in", "structuring"], cold_policy: "warm" }), /Two rules fired/);
  assert.match(whyFirst({ rules: ["both_new"], cold_policy: "review: both accounts new" }), /brand new/);
  assert.equal(whyFirst({ rules: ["structuring"], cold_policy: "warm" }), null);
});

test("ring types in plain words, always a pattern, not proof", () => {
  assert.match(typeText("SCATTER-GATHER"), /split to many accounts, then collected/);
  assert.match(typeText("SCATTER-GATHER"), /a pattern, not proof/);
  assert.match(typeText("none evident"), /no clear pattern/);
});

// ---- S7.14: the money picture, step by step -----------------------------------------
import { moreText, nodeRole, roleText, stepCaption, stepNumbers } from "../lib/caseLogic.js";

const EDGES = [
  { id: "e30", tx: 30, t: "2022-09-07 10:00:00", role: "alert", source: "S", target: "R", amount: 9500, currency: "Euro" },
  { id: "e12", tx: 12, t: "2022-09-07 09:00:00", role: "upstream", source: "U", target: "S", amount: 9612.34, currency: "Euro" },
  { id: "e11", tx: 11, t: "2022-09-07 09:00:00", role: "receiver's other payers", source: "P", target: "R", amount: 50, currency: "Euro" },
  { id: "m-x", tx: null, t: null, role: "more", source: "S", target: "more:S:out" },
];

test("payments are numbered by time, then id; '+N more' links get no number", () => {
  const n = stepNumbers(EDGES);
  assert.deepEqual([n.get("e11"), n.get("e12"), n.get("e30")], [1, 2, 3]);
  assert.equal(n.has("m-x"), false);
});

test("the table and the arrows read the same numbers (one source)", () => {
  const n = stepNumbers(EDGES);
  const arrows = EDGES.filter((e) => e.tx !== null).map((e) => n.get(e.id));
  const table = [...n.entries()].sort((a, b) => a[1] - b[1]).map(([, v]) => v);
  assert.deepEqual([...arrows].sort(), table);
});

test("roles in words", () => {
  assert.equal(roleText("alert"), "the flagged payment");
  assert.equal(roleText("upstream"), "paid the sender");
  assert.equal(roleText("downstream"), "the receiver paid it on");
  assert.equal(roleText("receiver's other payers"), "also paid the receiver");
  for (const r of ["upstream 2", "downstream 2", "sender's other payees"]) assert.ok(roleText(r) && !/stream/.test(roleText(r)));
  assert.equal(nodeRole("sender"), "Sender (this alert)");
  assert.equal(nodeRole("account"), null);
  assert.equal(moreText("out", 4), "4 more accounts this one paid, not drawn");
  assert.equal(moreText("in", 1), "1 more account that paid this one, not drawn");
});

test("a step caption says when, who paid whom, how much, and the role", () => {
  const names = { S: "Corp S", R: "Corp R", U: "Corp U", P: "Corp P" };
  const c = stepCaption(EDGES[1], 2, 3, (id) => names[id]);
  assert.equal(c, "Step 2 of 3 · 09-07 09:00 · Corp U paid Corp S 9,612.34 Euro · paid the sender");
});

// ---- S7.15: the decision workflow ------------------------------------------------------
import { closeCodes, stateText, timeline, trainingText } from "../lib/caseLogic.js";
import { newVisitorId } from "../lib/visitor.js";

test("states in words, with the SAR due date when escalated", () => {
  assert.match(stateText({ state: "new" }).title, /Not decided yet/);
  assert.match(stateText({ state: "awaiting_review", decision: "escalate" }).title, /suspicious/);
  assert.match(stateText({ state: "awaiting_review", decision: "close" }).detail, /second review/);
  const e = stateText({ state: "escalated", decision: "escalate", sar_due: "2026-12-23T12:00:00+00:00" });
  assert.match(e.title, /Escalated/);
  assert.match(e.detail, /2026-12-23/);
  assert.match(stateText({ state: "closed", decision: "close", code: "explained" }).detail, /Explained by normal activity/);
  assert.match(stateText({ state: "sent_back" }).title, /Sent back/);
});

test("the four close codes, in the API's order", () => {
  assert.deepEqual(closeCodes().map((c) => c.code), ["explained", "duplicate", "insufficient", "other"]);
});

test("training feedback compares the decision with the answer key", () => {
  assert.match(trainingText("escalate", true).title, /right/);
  assert.match(trainingText("close", true).title, /Not this time/);
  assert.match(trainingText("close", true).detail, /was money laundering/);
  assert.match(trainingText("close", false).title, /right/);
  assert.equal(trainingText(null, true), null);
});

test("the history timeline: rules at the payment, the AI draft, then people, in time order", () => {
  const items = timeline(
    { event_time: "2022-09-07T10:28:00", rules: ["fan_in"], agent: [{ model: "deepseek/deepseek-v4.1-flash", at: "2026-11-22T15:00:00+00:00" }] },
    [{ who: "you", role: "investigator", action: "close", code: "other", reason: "fine", at: "2026-11-23T10:00:00+00:00" },
     { who: "you", role: "reviewer", action: "send_back", code: null, reason: "look again", at: "2026-11-23T11:00:00+00:00" }],
  );
  assert.deepEqual(items.map((i) => i.kind), ["rule", "ai", "person", "person"]);
  assert.match(items[2].text, /closed it/);
  assert.match(items[3].text, /sent it back/);
});

test("a visitor id is a version-4 UUID", () => {
  assert.match(newVisitorId(), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

import { reviewText } from "../lib/caseLogic.js";
import { ROLES, roleHome } from "../lib/role.js";

test("a reviewer is right to approve a right decision and to send back a wrong one", () => {
  assert.equal(reviewText("approve", "escalate", true).right, true);
  assert.equal(reviewText("send_back", "close", true).right, true);   // Sam closed real laundering
  assert.equal(reviewText("approve", "close", true).right, false);
  assert.match(reviewText("approve", "close", true).detail, /closed real money laundering/);
  assert.equal(reviewText("send_back", "escalate", true).right, false);
  assert.equal(reviewText("approve", "escalate", null), null);
});

test("roles: one control, three choices, each with its start page", () => {
  assert.deepEqual(ROLES.map((r) => r.key), ["investigator", "reviewer", "manager"]);
  assert.equal(roleHome("investigator"), "/");
  assert.equal(roleHome("reviewer"), "/review/");
  assert.equal(roleHome("manager"), "/manager/");
});
