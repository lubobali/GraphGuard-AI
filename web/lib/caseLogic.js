// Pure helpers for the Case page (S7.8). No React, no React Flow: Node's runner tests them.

/** Plain names for the model's 15 features (what an investigator reads). */
export const FEATURE_NAMES = {
  hour: "Hour of the payment",
  weekday: "Day of the week (simulator pattern, FINDING-018)",
  log_amount: "Size of the amount",
  amount_ratio: "Paid vs received currency",
  is_same_bank: "Same bank or not",
  payment_currency_code: "Payment currency",
  sender_n_sent_before: "Sender's payments before",
  sender_amount_sent_before: "Sender's volume before (mixed currencies)",
  sender_distinct_out_before: "Different accounts the sender paid",
  sender_sent_last_24h: "Sender's payments in the last 24 h",
  sender_seconds_since_last_send: "Time since the sender's last payment",
  receiver_n_received_before: "Receiver's payments received before",
  receiver_amount_received_before: "Receiver's volume before (mixed currencies)",
  receiver_distinct_in_before: "Different accounts that paid the receiver",
  in_out_ratio_before: "Receiver's incoming vs sender's outgoing",
};

/** Contribution bars: the n biggest pushes, split up/down, on one symmetric scale. */
export function contributionBars(contribs, n = 8) {
  const top = [...contribs].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)).slice(0, n);
  const max = Math.max(1e-9, ...top.map((c) => Math.abs(c.contribution)));
  return top.map((c) => ({
    feature: c.feature,
    label: FEATURE_NAMES[c.feature] ?? c.feature,
    value: c.value,
    contribution: c.contribution,
    direction: c.contribution >= 0 ? "up" : "down",
    share: Math.abs(c.contribution) / max, // 0..1 of the half-width
  }));
}

/** The ring graph (API) -> flow nodes and edges, before layout. */
export function toFlow(graph) {
  const nodes = graph.nodes.map((n) => ({
    id: n.id,
    kind: n.seed ?? "account",
    name: n.name ?? n.id.split(":")[1],
    bank: n.bank ?? `bank ${n.id.split(":")[0]}`,
  }));
  const edges = graph.edges.map((e) => ({
    id: `e${e.id}`,
    tx: e.id,
    source: e.from,
    target: e.to,
    t: e.t,
    amount: e.amount,
    currency: e.currency,
    format: e.format,
    role: e.role,
    alert: e.role === "alert",
    rank: e.rank ?? null,
  }));
  for (const m of graph.more) {
    const id = `more:${m.node}:${m.direction}`;
    nodes.push({ id, kind: "more", name: `+${m.count} more`,
      bank: m.direction === "in" ? "paid this one, not drawn" : "this one paid, not drawn" });
    edges.push({
      id: `m-${id}`, tx: null, source: m.direction === "in" ? id : m.node,
      target: m.direction === "in" ? m.node : id, t: null, amount: null, currency: null,
      format: null, role: "more", alert: false, rank: null,
    });
  }
  return { nodes, edges };
}

/** Play order: transactions in time order (the alert last), "+N more" links never animated. */
export function playOrder(edges) {
  return edges.filter((e) => e.tx !== null)
    .sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : a.tx - b.tx))
    .map((e) => e.id);
}

export function money(amount, currency) {
  return `${amount.toLocaleString("en-US", { maximumFractionDigits: 2 })} ${currency}`;
}

/** Plain labels for the agent's models (S7.10). */
const MODEL_LABELS = {
  "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
  "anthropic/claude-sonnet-5.5": "Claude Sonnet 5.5",
};

/** The agent's checked reports (API `agent`) -> what the page shows. Kept claims first;
 *  dropped claims are shown as dropped, with the checker's reason, never silently hidden. */
export function agentView(reports) {
  return (reports ?? []).map((r) => ({
    model: r.model,
    label: MODEL_LABELS[r.model] ?? r.model,
    typology: r.report.typology,
    summary: r.report.summary,
    kept: r.report.kept.map((c) => ({ text: c.text, cites: c.cites })),
    dropped: r.report.dropped.map((c) => ({ text: c.text, cites: c.cites ?? [], why: c.why })),
    seconds: r.report.seconds ?? null,
  }));
}

/** The answer key in plain words (screenshot 2026-11-22: "Laundering · ring type
 *  SCATTER-GATHER · 17 payments" read as jargon). */
const TYPE_TEXT = {
  "FAN-OUT": "one account sent money out to many accounts",
  "FAN-IN": "many accounts sent money into one account",
  CYCLE: "money went around in a circle back to where it started",
  "GATHER-SCATTER": "money was collected into one account, then sent out to many",
  "SCATTER-GATHER": "money was split to many accounts, then collected into one",
  STACK: "money was passed on through layers of accounts",
  BIPARTITE: "a group of accounts paid another group of accounts",
  RANDOM: "money hopped through a random chain of accounts",
};

export function answerText(answer) {
  if (!answer.is_laundering) {
    return { verdict: "NO", headline: "This payment was not money laundering.",
      detail: "A normal payment that the model ranked high. Closing it would be the right call." };
  }
  const how = TYPE_TEXT[answer.pattern_type];
  const n = answer.ring_hops.length;
  return {
    verdict: "YES",
    headline: "This payment was money laundering.",
    detail: [
      n > 1 ? `It is one of ${n} payments in the same laundering scheme.` : null,
      how ? `The scheme's shape: ${how}.` : null,
      n > 1 ? "The red arrows are the scheme's payments in this picture." : null,
    ].filter(Boolean).join(" "),
  };
}

// ---- S7.13: reasons a person can trust ----------------------------------------------

/** One owner paying itself (names come from the accounts file: one name = one owner).
 *  Common in real banks and also a way to layer money, so it is labelled, not hidden. */
export function ownAccount(tx) {
  if (!tx.from_name || tx.from_name !== tx.to_name) return null;
  if (tx.from_account && tx.from_account === tx.to_account)
    return { label: "Same account", text: "The account paid itself." };
  return { label: "Own account",
    text: "The same owner moved money between two of its own accounts. Common, and sometimes used to layer money." };
}

/** Why an alert sits above the model's own order (ADR 0007 `priority()`): the hard rule
 *  (both accounts new) or two rules at once go above every model-only alert. */
export function whyFirst(row) {
  const rules = row.rules || [];
  if (rules.includes("both_new"))
    return "Both accounts are brand new, so a person always checks it (a fixed rule, not the model's score).";
  if (rules.length >= 2)
    return `Two rules fired (${rules.map((r) => r.replace("_", " ")).join(", ")}), so it is checked first, whatever the model's score.`;
  return null;
}

/** A ring type (the simulator's 8, or "none evident") in plain words. */
export function typeText(type) {
  if (!type || type === "none evident") return "no clear pattern";
  const how = TYPE_TEXT[type];
  return how ? `${how} (${type}): a pattern, not proof` : `${type}: a pattern, not proof`;
}

// ---- S7.14: the money picture, step by step -----------------------------------------

/** Step numbers 1..n by (time, id) -- the one source for the arrow labels and the table.
 *  "+N more" links (tx null) get none. */
export function stepNumbers(edges) {
  const order = playOrder(edges);
  return new Map(order.map((id, i) => [id, i + 1]));
}

const ROLE_TEXT = {
  alert: "the flagged payment",
  upstream: "paid the sender",
  "upstream 2": "paid someone who paid the sender",
  downstream: "the receiver paid it on",
  "downstream 2": "paid on again",
  "sender's other payees": "the sender also paid",
  "receiver's other payers": "also paid the receiver",
};

/** The data's edge roles in words (every edge is BEFORE the alert, S7.5). */
export function roleText(role) {
  return ROLE_TEXT[role] ?? role;
}

export function nodeRole(kind) {
  return kind === "sender" ? "Sender (this alert)" : kind === "receiver" ? "Receiver (this alert)" : null;
}

export function moreText(direction, n) {
  const acc = n === 1 ? "account" : "accounts";
  return direction === "out" ? `${n} more ${acc} this one paid, not drawn`
    : `${n} more ${acc} that paid this one, not drawn`;
}

export function stepCaption(edge, step, total, nameOf) {
  return `Step ${step} of ${total} · ${edge.t.slice(5, 16)} · ${nameOf(edge.source)} paid ${nameOf(edge.target)} ` +
    `${money(edge.amount, edge.currency)} · ${roleText(edge.role)}`;
}

// ---- S7.15: the decision workflow ------------------------------------------------------

const CLOSE_CODES = [
  ["explained", "Explained by normal activity"],
  ["duplicate", "Duplicate of another alert"],
  ["insufficient", "Not enough evidence"],
  ["other", "Other"],
];
export function closeCodes() {
  return CLOSE_CODES.map(([code, label]) => ({ code, label }));
}
const codeLabel = (c) => (CLOSE_CODES.find(([k]) => k === c) || [null, c])[1];

/** A case state (API) in words. */
export function stateText(c) {
  switch (c.state) {
    case "awaiting_review":
      return {
        title: c.decision === "escalate" ? "Saved: you marked this suspicious" : "Saved: you closed this as a false alarm",
        detail: `${c.decision === "close" ? `Close reason: ${codeLabel(c.code)}. ` : ""}Waiting for a second review (four eyes).`,
      };
    case "escalated":
      return { title: "Escalated: a suspicious activity report (SAR) is recommended",
        detail: `Approved by a second reviewer. SAR due by ${String(c.sar_due).slice(0, 10)} (30 days, FinCEN). Not filed: this is a demo.` };
    case "closed":
      return { title: "Closed: not suspicious", detail: `${codeLabel(c.code)}. Approved by a second reviewer.` };
    case "sent_back":
      return { title: "Sent back by the reviewer", detail: "Look again and decide." };
    default:
      return { title: "Not decided yet", detail: "Decide: suspicious, or a false alarm." };
  }
}

/** Training mode: the decision against the answer key (escalate = laundering). */
export function trainingText(decision, isLaundering) {
  if (!decision || isLaundering === null || isLaundering === undefined) return null;
  const right = (decision === "escalate") === isLaundering;
  return {
    right,
    title: right ? "You were right" : "Not this time",
    detail: isLaundering ? "The answer key says this payment was money laundering." :
      "The answer key says this payment was not money laundering.",
  };
}

const ACTION_TEXT = { escalate: "marked it suspicious", close: "closed it", approve: "approved the decision",
  send_back: "sent it back" };
const WHO = { you: "You", Sam: "Sam (demo investigator)", someone: "Someone" };

/** One history: the rules at the payment's time, the AI draft, then each person's step. */
export function timeline(alert, history) {
  const items = [];
  for (const r of alert.rules || [])
    items.push({ at: String(alert.event_time), kind: "rule", text: `Rule fired: ${r.replace("_", " ")}` });
  for (const a of alert.agent || [])
    items.push({ at: String(a.at), kind: "ai", text: `AI draft written (${MODEL_LABELS[a.model] ?? a.model}), checked by code` });
  for (const h of history || []) {
    const as = h.role === "reviewer" ? " as reviewer" : "";
    const code = h.code ? ` (${codeLabel(h.code)})` : "";
    items.push({ at: String(h.at ?? ""), kind: "person",
      text: `${WHO[h.who] ?? h.who}${as} ${ACTION_TEXT[h.action] ?? h.action}${code}${h.reason ? `: "${h.reason}"` : ""}` });
  }
  return items.map((it, i) => ({ ...it, i })).sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : a.i - b.i));
}

/** Training mode for a reviewer: approving a right decision or sending back a wrong one is right. */
export function reviewText(action, decision, isLaundering) {
  if (!decision || isLaundering === null || isLaundering === undefined) return null;
  const decisionRight = (decision === "escalate") === isLaundering;
  const right = action === "approve" ? decisionRight : !decisionRight;
  const what = decision === "escalate"
    ? (isLaundering ? "escalated real money laundering" : "escalated a normal payment")
    : (isLaundering ? "closed real money laundering" : "closed a normal payment");
  return { right, title: right ? "Good review" : "Not this time",
    detail: `The investigator ${what}; you ${action === "approve" ? "approved it" : "sent it back"}.` };
}
