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
    nodes.push({ id, kind: "more", name: `+${m.count} more`, bank: m.direction === "in" ? "payers" : "payees" });
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
