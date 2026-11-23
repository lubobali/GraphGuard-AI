import Link from "next/link";
import { useEffect, useState } from "react";
import type { Capacity, Manager, Performance } from "../../lib/api";
import { get } from "../../lib/api";
import { closeCodes } from "../../lib/caseLogic.js";
import { flowCounts, fmt, peopleFor, plural } from "../../lib/logic.js";
import { visitorId } from "../../lib/visitor.js";
import s from "./manager.module.css";

// The manager's view (S7.16): the team's work and its quality, then planning the team.
// Counts, never money; "All visitors" never shows an id or another visitor's words.
const CODE: Record<string, string> = Object.fromEntries(closeCodes().map((c: { code: string; label: string }) => [c.code, c.label]));

function Tile({ n, label, tone }: { n: number | string; label: string; tone?: "good" | "bad" }) {
  return <div className={`${s.tile} ${tone ? s[tone] : ""}`}><strong className="num">{n}</strong><span>{label}</span></div>;
}

export default function ManagerPage() {
  const [scope, setScope] = useState<"me" | "all">("me");
  const [m, setM] = useState<Manager | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [perDay, setPerDay] = useState(100);
  const [cap, setCap] = useState<Capacity | null>(null);
  const [perf, setPerf] = useState<Performance | null>(null);

  useEffect(() => {
    setM(null);
    get<Manager>(`/manager?visitor=${visitorId()}&scope=${scope}`).then(setM).catch((e) => setErr(String(e)));
  }, [scope]);
  useEffect(() => {
    const t = setTimeout(() => {
      get<Capacity>(`/capacity?per_day=${perDay}`).then(setCap).catch(() => {});
      get<Performance>(`/performance?per_day=${perDay}`).then(setPerf).catch(() => {});
    }, 200);
    return () => clearTimeout(t);
  }, [perDay]);
  const flow = cap ? flowCounts(cap.k, cap.rankings.system, cap.rankings.rules) : null;
  const who = scope === "me" ? "you" : "all visitors";

  return (
    <div className={s.page}>
      <section className={s.hero}>
        <h1>The manager&apos;s view</h1>
        <p className="ink2">How much work is done, how good it is, and how many people the team needs. Counts only; measured on the 2-day window.</p>
      </section>

      <div className={s.tabs} role="tablist" aria-label="Whose work">
        <button type="button" role="tab" aria-selected={scope === "me"} className={scope === "me" ? s.tabOn : s.tab} onClick={() => setScope("me")}>Your shift</button>
        <button type="button" role="tab" aria-selected={scope === "all"} className={scope === "all" ? s.tabOn : s.tab} onClick={() => setScope("all")}>All visitors</button>
      </div>
      {err && <p role="alert">Could not load the numbers ({err}).</p>}

      {m && (m.decided === 0 && m.reviews_done === 0 ? (
        <section className="card"><p style={{ margin: 0 }}>No decisions yet for {who}. Switch to <strong>Investigator</strong> (top of the page) and decide a few alerts, or review Sam&apos;s as <strong>Reviewer</strong>.</p></section>
      ) : (
        <>
          <section className="card" aria-labelledby="work-h">
            <h2 id="work-h" className={s.h2}>The work</h2>
            <div className={s.tiles}>
              <Tile n={m.decided} label="alerts decided" />
              <Tile n={m.waiting_review} label="waiting for a second review" />
              <Tile n={m.final_escalated} label="escalated after review (SAR recommended)" tone="bad" />
              <Tile n={m.final_closed} label="closed after review" />
              <Tile n={m.reviews_done} label="reviews done" />
            </div>
            <p className={s.line}>Of the decisions: <strong className="num">{m.escalated}</strong> suspicious, <strong className="num">{m.closed}</strong> closed{m.sent_back ? <>, <strong className="num">{m.sent_back}</strong> sent back to decide again</> : null}.</p>
          </section>

          <section className="card" aria-labelledby="quality-h">
            <h2 id="quality-h" className={s.h2}>The quality <span className="muted" style={{ fontWeight: 400 }}>(training mode: the answer key is known)</span></h2>
            <div className={s.tiles}>
              <Tile n={`${m.matched} of ${m.decided}`} label="decisions matched the answer key" tone="good" />
              <Tile n={`${m.model_right} of ${m.decided}`} label="of those alerts were really laundering (the model's flag was right)" />
              <Tile n={m.ai_agreement.cases ? `${m.ai_agreement.agree} of ${m.ai_agreement.cases}` : "—"} label="AI drafts agreed with the decision (where there was a draft)" />
              <Tile n={m.ai_strong_against.cases ? `${m.ai_strong_against.strong} of ${m.ai_strong_against.cases}` : "—"} label="decisions where the AI second reviewer (Claude, the one whose label held up in testing) found a strong case against" />
            </div>
            <h3 className={s.h3}>Quality check: {m.qa.length} closed alerts, re-checked blind</h3>
            {m.qa.length === 0 ? <p className="muted">Nothing closed yet.</p> : (
              <table className={s.table}>
                <thead><tr><th scope="col">Alert</th><th scope="col">Close reason</th>{scope === "me" && <th scope="col">Your words</th>}<th scope="col">Answer key</th></tr></thead>
                <tbody>{m.qa.map((q) => (
                  <tr key={q.event_id}>
                    <td><Link href={`/case/?id=${q.event_id}`}>{q.event_id}</Link></td>
                    <td>{CODE[q.code] ?? q.code}</td>
                    {scope === "me" && <td className="muted">&ldquo;{q.reason}&rdquo;</td>}
                    <td className={q.ok ? s.ok : s.bad}>{q.ok ? "✓ right to close" : "✗ it was laundering"}</td>
                  </tr>))}</tbody>
              </table>
            )}
          </section>
        </>
      ))}

      {m && (
        <section className="card" aria-labelledby="backlog-h">
          <h2 id="backlog-h" className={s.h2}>Backlog: alerts in the top 211 {scope === "me" ? "you have not decided" : "no visitor has decided"}</h2>
          <div className={s.tiles}>
            <Tile n={m.backlog.total} label="open alerts" />
            <Tile n={m.backlog.under_24h} label="under 24 hours old" />
            <Tile n={m.backlog.h24_48} label="24 to 48 hours: past the check-by time" tone="bad" />
            <Tile n={m.backlog.over_48h} label="over 48 hours" tone="bad" />
          </div>
          <p className="muted" style={{ fontSize: 13 }}>Ages at the end of the window ({String(m.as_of).slice(0, 16).replace("T", " ")}, the data&apos;s clock). Each alert should be checked within 24 hours.</p>
        </section>
      )}

      <section className="card" aria-labelledby="plan-h">
        <h2 id="plan-h" className={s.h2}>Plan the team</h2>
        <label htmlFor="mperday">The team checks the top <strong className="num">{fmt(perDay)}</strong> payments a day: {peopleFor(perDay)}</label>
        <input id="mperday" type="range" min={10} max={1000} step={10} value={perDay} onChange={(e) => setPerDay(Number(e.target.value))} className={s.range} />
        {flow && (
          <p aria-live="polite">Over the 2 days they check {fmt(flow.checked)} and find <strong className="num">{fmt(flow.found)}</strong> of {fmt(flow.total)} laundering payments
            ({fmt(flow.falseAlarms)} false alarms), and <strong className="num">{fmt(flow.groupsFound)}</strong> of {fmt(flow.groupsTotal)} laundering groups.
            Fixed rules, same checks: {plural(flow.rulesFound, "payment", "payments")}.</p>
        )}
        {perf && (
          <div className={s.late}>
            <h3 className={s.h3}>The catch: the truth comes late</h3>
            <p>On the day, investigators had confirmed only <strong className="num">{plural(perf.confirmed_so_far.known, "label", "labels")}</strong>{" "}
              ({fmt(perf.confirmed_so_far.laundering)} laundering). The rest of the laundering (<strong className="num">
              {(100 * (1 - perf.confirmed_so_far.laundering / perf.laundering_in_window)).toFixed(1)}%</strong>) is still unknown: verdicts take days, police reports weeks.
              The numbers above use the full answer key, which a real bank only gets much later.</p>
            <p className="muted" style={{ fontSize: 13 }}>Labels exist only for alerts someone checked, so they favour the model that chose them (FINDING-017).</p>
          </div>
        )}
      </section>
    </div>
  );
}
