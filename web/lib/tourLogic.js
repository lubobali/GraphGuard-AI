// S7.18: "Try one case" -- the words of each step, pure and tested. The data is web/lib/tour.json
// (built from the database; no API call, no AI call, nothing saved on the server).
import { typeHow } from "./caseLogic.js";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const money = (v) => Number(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** "Corp A paid Corp B 9,539.79 Euro on 6 Sep at 14:02." (an own-account payment says so) */
export function paymentLine(p) {
  const [d, t] = String(p.event_time).split(/[ T]/);
  const [, m, day] = d.split("-").map(Number);
  const to = p.to_name === p.from_name ? "its own account at another bank" : p.to_name;
  return `${p.from_name} paid ${to} ${money(p.amount_paid)} ${p.payment_currency} on ${day} ${MONTHS[m - 1]} at ${t.slice(0, 5)}.`;
}

/** The answer after a tap: right or not, what it was, its shape in plain words. */
export function verdict(choice, answer) {
  const said = choice === "escalate";
  const right = said === answer.is_laundering;
  const how = typeHow(answer.pattern_type);
  return {
    right,
    headline: right ? "You were right." : "Not this time.",
    what: answer.is_laundering ? "This was money laundering." : "This was a normal payment.",
    shape: answer.is_laundering
      ? (how ? `The scheme: ${how}.` : null)
      : "It looked unusual, so it was flagged — but it was fine. Investigators close many alerts like this.",
  };
}

/** One honest line on what the system cannot do (the home page's own numbers). */
export function limitLine(l) {
  return `The system is not perfect: of the top ${l.checked} payments it flags, ${l.false_alarms} are false alarms, and it finds ${l.found} of the ${fmt(l.total)} laundering payments.`;
}
const fmt = (n) => n.toLocaleString("en-US");

export function scoreText(results) {
  const done = results.filter((r) => r !== null);
  return `${done.filter(Boolean).length} of ${done.length} right`;
}
