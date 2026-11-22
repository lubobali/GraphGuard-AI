import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import RingGraph from "../../components/RingGraph";
import WhyBars from "../../components/WhyBars";
import { get } from "../../lib/api";
import { agentView, money } from "../../lib/caseLogic.js";
import { fmt, topShare } from "../../lib/logic.js";
import s from "./case.module.css";

type Hist = { event_id: number; event_time: string; from_name: string | null; to_name: string | null;
  amount_paid: number; payment_currency: string; payment_format: string; rank: number };
type Alert = {
  event_id: number; event_time: string; from_name: string | null; from_bank_name: string | null;
  to_name: string | null; to_bank_name: string | null; amount_paid: number; payment_currency: string;
  amount_received: number; receiving_currency: string; payment_format: string; rank: number;
  percentile: number; alert: boolean; cold_policy: string; rules: string[]; rule_text: string[];
  reasons: string[] | null; contributions: { feature: string; value: number | null; contribution: number }[] | null;
  history: { from: Hist[]; to: Hist[] }; ring: Parameters<typeof RingGraph>[0]["graph"] | null;
  verdicts: { verdict: string; note: string; at: string }[]; model_version: string;
  agent: { model: string; at: string; report: unknown }[];
};

type Claim = { text: string; cites: number[] };
type AgentReport = { model: string; label: string; typology: string; summary: string;
  kept: Claim[]; dropped: (Claim & { why: string })[]; seconds: number | null };

function AgentDraft({ reports }: { reports: Alert["agent"] }) {
  const views: AgentReport[] = agentView(reports);
  if (views.length === 0) return null;
  return (
    <section className={`card ${s.agentCard}`} aria-labelledby="agent-h">
      <h2 id="agent-h" className={s.h2}>AI draft, checked</h2>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
        Written by an AI from the same read-only data you see here (never the answer key). A checker
        kept only the claims it could match to a payment; the rest are shown as dropped. The AI drafts, you decide.
      </p>
      <div className={s.agentGrid}>
        {views.map((v) => (
          <div key={v.model}>
            <h3 className={s.h3}>{v.label} · <span className="ink2">ring type: {v.typology}</span></h3>
            <p className={s.agentSummary}>{v.summary}</p>
            {v.kept.length > 0 && (
              <ul className={s.claims}>
                {v.kept.map((c, i) => (
                  <li key={i}>{c.text} <span className="muted">· tx {c.cites.join(", ")}</span></li>
                ))}
              </ul>
            )}
            {v.dropped.length > 0 && (
              <details className={s.dropped}>
                <summary>{v.dropped.length} claim{v.dropped.length === 1 ? "" : "s"} dropped by the checker</summary>
                <ul>
                  {v.dropped.map((c, i) => (
                    <li key={i}><s>{c.text}</s> <span className="muted">· {c.why}</span></li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
type Answer = { is_laundering: boolean; pattern_id: number | null; pattern_type: string | null;
  hop: number | null; ring_hops: number[] };

function HistoryTable({ rows, title }: { rows: Hist[]; title: string }) {
  return (
    <div>
      <h3 className={s.h3}>{title}</h3>
      {rows.length === 0 ? <p className="muted">No earlier payments in the window.</p> : (
        <table className={s.hist}>
          <thead><tr><th scope="col">When</th><th scope="col">From → to</th><th scope="col">Amount</th><th scope="col">Rank</th></tr></thead>
          <tbody>
            {rows.map((h) => (
              <tr key={h.event_id}>
                <td className="num">{h.event_time.slice(5, 16).replace("T", " ")}</td>
                <td>{h.from_name ?? "?"} → {h.to_name ?? "?"}</td>
                <td className="num">{money(h.amount_paid, h.payment_currency)}</td>
                <td className="num">{fmt(h.rank)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function CasePage() {
  const { query, isReady } = useRouter();
  const id = Number(query.id);
  const [a, setA] = useState<Alert | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady) return;
    if (!Number.isInteger(id)) { setError("no alert chosen"); return; }
    setAnswer(null);
    get<Alert>(`/alerts/${id}`).then(setA).catch((e) => setError(String(e)));
  }, [isReady, id]);

  async function verdict(v: "escalate" | "close") {
    const r = await fetch(`/api/alerts/${id}/verdict`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ verdict: v, note }),
    });
    if (r.ok) {
      setSaved(v === "escalate" ? "Escalated to a case." : "Closed as not suspicious.");
      setNote("");
      setA(await get<Alert>(`/alerts/${id}`));
    } else setSaved(`Not saved (${r.status}).`);
  }

  if (error) return <p role="alert" className={s.error}>{error} · <Link href="/">back to the queue</Link></p>;
  if (!a) return <p className="muted" style={{ padding: "32px 0" }}>Loading the case…</p>;

  return (
    <>
      <p className={s.back}><Link href="/">← Queue</Link></p>
      <section className={`card ${s.head}`}>
        <div className={s.rankBox}>
          <div className={s.rank}>#{fmt(a.rank)}</div>
          <div className="muted">{topShare(a.percentile)}</div>
        </div>
        <div className={s.headMain}>
          <h1 className={s.h1}>{a.from_name ?? "unknown"} <span className="muted">→</span> {a.to_name ?? "unknown"}</h1>
          <p className="ink2">
            <strong className="num">{money(a.amount_paid, a.payment_currency)}</strong>
            {a.receiving_currency !== a.payment_currency && <> · received as {money(a.amount_received, a.receiving_currency)}</>}
            {" "}· {a.payment_format} · {a.event_time.replace("T", " ").slice(0, 16)}
          </p>
          <p className="muted">{a.from_bank_name} → {a.to_bank_name} · due {a.event_time.slice(5, 10)} + 24 h · model {a.model_version}</p>
        </div>
      </section>

      <div className={s.grid}>
        <section className="card" aria-labelledby="why-h">
          <h2 id="why-h" className={s.h2}>Why this alert</h2>
          {a.reasons ? (
            <ol className={s.reasons}>{a.reasons.map((r) => <li key={r}>{r}</li>)}</ol>
          ) : <p className="muted">Explanations are kept for the top 20,000 of the queue.</p>}
          {a.rule_text.length > 0 && (
            <div className={s.rules}>{a.rule_text.map((r) => <p key={r}>{r}</p>)}</div>
          )}
          {a.contributions && <WhyBars contributions={a.contributions} />}
        </section>

        <section className="card" aria-labelledby="decide-h">
          <h2 id="decide-h" className={s.h2}>Your decision</h2>
          <label htmlFor="note" className="ink2">Note (optional)</label>
          <textarea id="note" className={s.note} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="What you saw, what you checked" />
          <div className={s.buttons}>
            <button type="button" className={s.escalate} onClick={() => verdict("escalate")}>Escalate to a case</button>
            <button type="button" className={s.close} onClick={() => verdict("close")}>Close: not suspicious</button>
          </div>
          {saved && <p role="status" className={s.saved}>{saved}</p>}
          {a.verdicts.length > 0 && (
            <ul className={s.audit}>
              {a.verdicts.map((v, i) => <li key={i}><strong>{v.verdict}</strong> · {String(v.at).slice(0, 16).replace("T", " ")}{v.note ? ` · ${v.note}` : ""}</li>)}
            </ul>
          )}
          <p className="muted" style={{ fontSize: 13 }}>Decisions are logged for the audit trail. They never train the model directly.</p>
        </section>
      </div>

      <AgentDraft reports={a.agent} />

      <section className={`card ${s.ringCard}`} aria-labelledby="ring-h">
        <div className={s.ringHead}>
          <h2 id="ring-h" className={s.h2}>The money around it</h2>
          {!answer ? (
            <button type="button" className={s.keyBtn}
              onClick={() => get<Answer>(`/alerts/${id}/answer`).then(setAnswer).catch((e) => setError(String(e)))}>
              Show the answer key
            </button>
          ) : (
            <span className={answer.is_laundering ? s.yes : s.no}>
              {answer.is_laundering ? "Laundering" : "Not laundering"}
              {answer.pattern_type ? ` · ring type ${answer.pattern_type} · ${answer.ring_hops.length} payments in the window` : ""}
            </span>
          )}
        </div>
        {answer && <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>The answer key is the simulator&apos;s truth. A bank would not know this on the day (labels arrive days to weeks later).</p>}
        {a.ring ? <RingGraph graph={a.ring} ringTx={answer ? new Set(answer.ring_hops) : null} /> :
          <p className="muted">The picture is kept for the top 20,000 of the queue.</p>}
      </section>

      <section className={`card ${s.histCard}`}>
        <div className={s.grid}>
          <HistoryTable rows={a.history.from} title="Sender's recent payments" />
          <HistoryTable rows={a.history.to} title="Receiver's recent payments" />
        </div>
      </section>
    </>
  );
}
