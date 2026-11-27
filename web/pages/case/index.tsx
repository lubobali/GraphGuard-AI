import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import DecisionPanel, { ReviewPanel } from "../../components/DecisionPanel";
import Explain from "../../components/Explain";
import RingGraph from "../../components/RingGraph";
import WhyBars from "../../components/WhyBars";
import { get } from "../../lib/api";
import { agentView, answerText, money, ownAccount, reasonText, whyFirst } from "../../lib/caseLogic.js";
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
  model_version: string;
  agent: { model: string; at: string; report: unknown }[];
  reviews?: { direction: string; model: string; review: { strength: string; summary: string; kept: { text: string; cites: number[] }[]; dropped: { text: string; cites: number[]; why: string }[] } }[];
  from_account: string; to_account: string; groups: Group[] | null;
};
type Group = { key: string; label: string; look: "sender" | "receiver" | null; contribution: number;
  direction: "up" | "against" | "artifact"; sentences: string[] };

const LOOK = { sender: ["#sender-history", "the sender's payments"], receiver: ["#receiver-history", "the receiver's payments"] };

// S7.13: the model's reasons as behaviours a person can check, up first, then against, the
// simulator's calendar effect last (counted, never a reason to investigate).
function Groups({ groups }: { groups: Group[] }) {
  const part = (d: Group["direction"]) => groups.filter((g) => g.direction === d);
  const item = (g: Group) => (
    <li key={g.key}>
      <strong>{g.label}.</strong> {g.sentences[0]}
      {g.look && <> <a href={LOOK[g.look][0]}>Check {LOOK[g.look][1]}</a></>}
      {g.sentences.length > 1 && <Explain label={`${g.sentences.length - 1} more`}><p>{g.sentences.slice(1).join(" ")}</p></Explain>}
    </li>
  );
  const up = part("up"), against = part("against"), art = part("artifact");
  return (
    <div className={s.groups}>
      <h3 className={s.h3}>What pushed the model&apos;s score up</h3>
      {up.length ? <ol className={s.reasons}>{up.map(item)}</ol>
        : <p className="muted">Nothing: the model&apos;s own score for this payment is low.</p>}
      {against.length > 0 && (<><h3 className={s.h3}>What pulled the model&apos;s score down</h3><ul className={s.against}>{against.map(item)}</ul></>)}
      {art.length > 0 && <Explain label="Not counted as a reason">{art.map((g) => <p key={g.key}>{g.label}: {g.sentences.join(" ")}</p>)}</Explain>}
    </div>
  );
}

type Claim = { text: string; cites: number[] };
type AgentReport = { model: string; label: string; typology: string; summary: string;
  kept: Claim[]; dropped: (Claim & { why: string })[]; seconds: number | null };

function AgentDraft({ reports }: { reports: Alert["agent"] }) {
  const views: AgentReport[] = agentView(reports);
  if (views.length === 0) return null;
  return (
    <section className={`card ${s.agentCard}`} aria-labelledby="agent-h">
      <h2 id="agent-h" className={s.h2}>AI draft, checked</h2>
      <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>Facts checked by code. The AI drafts, you decide.</p>
      <Explain>
        <p>Written by an AI from the same read-only data you see here (never the answer key). A checker
        kept only the claims it could match to a payment; the rest are shown as dropped.</p>
        <p>Measured on 64 test alerts never used to build the checker: before checking, 4-6% of the AI&apos;s claims
        were unsupported. Its ring-type guesses were right for only 7-8 of 40 laundering alerts, about as often
        as a guess. Treat the type as a hint, not a finding (FINDING-019).</p>
      </Explain>
      <div className={s.agentGrid}>
        {views.map((v) => (
          <div key={v.model}>
            <h3 className={s.h3}>{v.label} · <span className="ink2">guess: {v.typology === "none evident" ? "no clear pattern" : v.typology.toLowerCase()} (a hint)</span></h3>
            <Explain label="AI summary (not checked)"><p className={s.agentSummary}>{v.summary}</p></Explain>
            {v.kept.length > 0 && (
              <ul className={s.claims}>
                {v.kept.slice(0, 2).map((c, i) => (
                  <li key={i}>{c.text} <span className="muted">· tx {c.cites.join(", ")}</span></li>
                ))}
              </ul>
            )}
            {v.kept.length > 2 && (
              <Explain label={`${v.kept.length - 2} more checked facts`}>
                <ul className={s.claims}>
                  {v.kept.slice(2).map((c, i) => (
                    <li key={i}>{c.text} <span className="muted">· tx {c.cites.join(", ")}</span></li>
                  ))}
                </ul>
              </Explain>
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

function HistoryTable({ rows, title, id }: { rows: Hist[]; title: string; id: string }) {
  return (
    <div id={id}>
      <h3 className={s.h3}>{title}</h3>
      {/* S8b.1: an investigator found AI facts citing payments this table cannot show */}
      <p className={`muted ${s.histNote}`}>From 6 Sep 13:34 only, the start of the data shown here, newest first. Earlier payments can still appear in the money picture and the AI&apos;s facts.</p>
      {rows.length === 0 ? <p className="muted">No earlier payments in the window.</p> : (
        <table className={s.hist}>
          <thead><tr><th scope="col">When</th><th scope="col">From → to</th><th scope="col">Amount</th><th scope="col">Its rank in the list</th></tr></thead>
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
  const review = query.review === "demo" || query.review === "mine" ? (query.review as "demo" | "mine") : null;
  const [a, setA] = useState<Alert | null>(null);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady) return;
    if (!Number.isInteger(id)) { setError("no alert chosen"); return; }
    setAnswer(null);
    get<Alert>(`/alerts/${id}`).then(setA).catch((e) => setError(String(e)));
  }, [isReady, id]);

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
          <p className="muted">{a.from_bank_name} → {a.to_bank_name} · due {a.event_time.slice(5, 10)} + 24 h</p>
        </div>
      </section>

      <div className={s.grid}>
        <section className="card" aria-labelledby="why-h">
          <h2 id="why-h" className={s.h2}>Why this alert</h2>
          {whyFirst(a) && <p className={s.firstWhy}>{whyFirst(a)}</p>}
          {ownAccount(a) && (
            <p className={s.own}><span className={s.ownChip}>{ownAccount(a)!.label}</span> {ownAccount(a)!.text}</p>
          )}
          {a.groups ? <Groups groups={a.groups} /> : a.reasons ? (
            <ol className={s.reasons}>{a.reasons.map((r) => <li key={r}>{r}</li>)}</ol>
          ) : <p className="muted">Explanations are kept for the top 20,000 of the queue.</p>}
          {a.rule_text.length > 0 && (
            <div className={s.rules}>{a.rule_text.map((r) => <p key={r}>{reasonText(r)}</p>)}</div>
          )}
          {a.contributions && (
            <details className={s.detail}><summary>Model detail: every feature</summary><p className="muted">Model {a.model_version}</p><WhyBars contributions={a.contributions} /></details>
          )}
        </section>

        <section className="card" aria-labelledby="decide-h">
          {review ? (<>
            <h2 id="decide-h" className={s.h2}>Second review</h2>
            <ReviewPanel a={a} owner={review} />
          </>) : (<>
            <h2 id="decide-h" className={s.h2}>Your decision</h2>
            <DecisionPanel a={a} />
          </>)}
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
          ) : null}
        </div>
        {answer && (() => {
          const t = answerText(answer);
          return (
            <div className={answer.is_laundering ? s.answerYes : s.answerNo} role="status">
              <p className={s.answerHead}><span className={s.verdict}>{t.verdict}</span> {t.headline}</p>
              {t.detail && <p className={s.answerDetail}>{t.detail}</p>}
              <p className={s.answerNote}>Answer key = the simulator&apos;s truth. A real bank would not know this on the day: labels arrive days to weeks later.</p>
            </div>
          );
        })()}
        {a.ring ? <RingGraph graph={a.ring} ringTx={answer ? new Set(answer.ring_hops) : null} /> :
          <p className="muted">The picture is kept for the top 20,000 of the queue.</p>}
      </section>

      <section className={`card ${s.histCard}`}>
        <div className={s.grid}>
          <HistoryTable rows={a.history.from} title="Sender's recent payments" id="sender-history" />
          <HistoryTable rows={a.history.to} title="Receiver's recent payments" id="receiver-history" />
        </div>
      </section>
    </>
  );
}
