import Explain from "../components/Explain";
import Link from "next/link";
import { useEffect, useState } from "react";
import CapacityChart from "../components/CapacityChart";
import type { Capacity, Curve, Decisions, Queue } from "../lib/api";
import { get } from "../lib/api";
import N from "../lib/aboutNumbers.json";
import { ownAccount, whyFirst } from "../lib/caseLogic.js";
import { visitorId } from "../lib/visitor.js";
import { flowCounts, fmt, peopleFor, plural, topShare } from "../lib/logic.js";
import s from "./index.module.css";

const STATE_CHIP: Record<string, string> = {
  awaiting_review: "you decided · waiting for review", escalated: "escalated", closed: "closed", sent_back: "sent back to you",
};
const COLD: Record<string, string> = {
  "scored: sender new": "new sender",
  "scored: receiver new": "new receiver",
  "review: both accounts new": "both new",
};

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

type Flow = ReturnType<typeof flowCounts>;

function GuessFirst({ flow }: { flow: Flow }) {
  const [pick, setPick] = useState<number | null>(null);
  const options = [flow.total, Math.round(flow.total / 2), flow.found];
  return (
    <details className={`card ${s.fold}`}>
      <summary>Guess first: how many will they find?</summary>
      <div className={s.guess}>
        {options.map((o) => (
          <button key={o} type="button" onClick={() => setPick(o)} aria-pressed={pick === o}>about {fmt(o)}</button>
        ))}
      </div>
      {pick !== null && (
        <p role="status">
          {pick === flow.found ? "Right: " : "Not quite: "}<strong className="num">{fmt(flow.found)}</strong>. The top of the
          list is mostly laundering ({fmt(flow.found)} of {fmt(flow.checked)}), but most laundering looks normal and sits
          lower, where nobody has time to look.
        </p>
      )}
    </details>
  );
}

function WhereFrom() {
  const p = N.split;
  const rows = [
    { name: "Learn", what: "the model studies these, with the answers", ...p.learn },
    { name: "Shown here", what: "scored without the answers; the answers only grade the result", ...p.shown },
    { name: "Locked", what: "never opened; replayed once later as the go-live day", ...p.locked },
  ];
  return (
    <details className={`card ${s.fold}`}>
      <summary>Where the numbers come from</summary>
      <p>
        The data is <strong>made up by a simulator</strong> (IBM AMLworld): no real people or banks. It is one file of{" "}
        {fmt(p.file_rows.value)} payments, and because the simulator made the laundering itself, every row carries an
        answer: laundering or not. The file is cut by date into three parts:
      </p>
      <div className={s.tableWrap}>
        <table className={s.split}>
          <thead><tr><th scope="col">Part</th><th scope="col">Days (Sep 2022)</th><th scope="col">Payments</th><th scope="col">Laundering</th><th scope="col">Used for</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name}>
                <th scope="row">{r.name}</th>
                <td className="num">{r.first.slice(8)} to {r.last.slice(8)}</td>
                <td className="num">{fmt(r.transactions)}</td>
                <td className="num">{fmt(r.laundering)}</td>
                <td>{r.what}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={`muted ${s.small}`}>
        The last {fmt(p.tail_rows_dropped.value)} rows were left out: a simulator flaw made most of them laundering (FINDING-001).
        A real bank has no answer column; it learns from the cases its investigators confirmed.
      </p>
    </details>
  );
}

export default function QueuePage() {
  const [perDay, setPerDay] = useState(100);
  const settled = useDebounced(perDay, 200);
  const [cap, setCap] = useState<Capacity | null>(null);
  const [curve, setCurve] = useState<Curve | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [mine, setMine] = useState<Decisions | null>(null);
  useEffect(() => {
    get<Decisions>(`/decisions?visitor=${visitorId()}`).then(setMine).catch(() => {});
  }, []);
  const myState = new Map((mine?.cases ?? []).filter((c) => c.owner !== "demo").map((c) => [c.event_id, c.state]));

  useEffect(() => {
    get<Curve>("/capacity/curve").then(setCurve).catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    setPage(1);
    Promise.all([
      get<Capacity>(`/capacity?per_day=${settled}`),
      get<Queue>(`/queue?per_day=${settled}&page=1`),
    ])
      .then(([c, q]) => { setCap(c); setQueue(q); })
      .catch((e) => setError(String(e)));
  }, [settled]);

  async function more() {
    if (!queue) return;
    const q = await get<Queue>(`/queue?per_day=${settled}&page=${page + 1}`);
    setQueue({ ...q, groups: [...queue.groups, ...q.groups] });
    setPage(page + 1);
  }

  const flow = cap ? flowCounts(cap.k, cap.rankings.system, cap.rankings.rules) : null;
  const shown = queue?.groups.length ?? 0;

  return (
    <>
      <section className={s.hero}>
        <h1>Find money laundering in a million payments</h1>
        <p className="ink2">
          A computer scores every payment. A small team checks the riskiest first and decides.
        </p>
        <p className={s.limit}>No system finds all of it.</p>
        <p className={s.tryRow}>
          <Link href="/try/" className={s.tryBtn}>Try one case — 2 minutes</Link>
        </p>
      </section>


      {error && <p role="alert" className={s.error}>Could not load the data ({error}).</p>}

      <section className={`card ${s.flowCard}`} aria-labelledby="slider-label">
        <label id="slider-label" htmlFor="perday" className={s.label}>
          Your team checks the top <strong className="num">{fmt(perDay)}</strong> payments a day
        </label>
        <input id="perday" type="range" min={10} max={1000} step={10} value={perDay}
          onChange={(e) => setPerDay(Number(e.target.value))} className={s.range}
          aria-valuetext={`${perDay} payments a day`} />
        <div className={s.scale} aria-hidden="true"><span>10</span><span>1,000</span></div>
        <p className={s.people}>= {peopleFor(perDay)}</p>
        {flow && (
          <div aria-live="polite">
            <p className="ink2" style={{ margin: "4px 0 10px" }}>
              Over 2 days: {fmt(N.split.shown.transactions)} payments, {fmt(flow.total)} laundering
            </p>
            <ol className={s.flow}>
              <li className={s.tile}><strong className="num">{fmt(flow.checked)}</strong><span>checked</span></li>
              <li className={`${s.tile} ${s.good}`}><strong className="num">{fmt(flow.found)}</strong><span>laundering found</span></li>
              <li className={s.tile}><strong className="num">{fmt(flow.falseAlarms)}</strong><span>false alarms</span></li>
              <li className={`${s.tile} ${s.bad}`}><strong className="num">{fmt(flow.missed)}</strong><span>laundering missed</span></li>
            </ol>
            <Explain label="What do these mean?"><p>Checked = the top of the list. Some laundering looks exactly like normal payments, so no list finds all of it. False alarms were checked and were fine. Missed = laundering lower on the list, never checked.</p></Explain>
            <p className={s.rulesLine}>
              Old fixed rules, same {fmt(flow.checked)} checks: <strong className="num">{plural(flow.rulesFound, "laundering payment", "laundering payments")}</strong> found. <Explain label="Why so few?"><p>The rules are the usual kind (many payments in a day, amounts just under a reporting line), with limits set on earlier data. The simulator&apos;s launderers rarely break simple rules, so here rules work as a safety net, not as the main alarm. That says more about this simulated data than about rules in general.</p></Explain>
            </p>
          </div>
        )}
      </section>

      <section className="card" style={{ marginBottom: 16 }}>{curve && <CapacityChart curve={curve} perDay={settled} />}</section>

      {flow && <GuessFirst flow={flow} />}
      <WhereFrom />

      <section className={`card ${s.queueCard}`} aria-labelledby="queue-h">
        <div className={s.queueHead}>
          <h2 id="queue-h" className={s.h2}>The list: most suspicious payments first</h2>
          {queue && (
            <span className="muted num">
              {fmt(queue.alerts)} payments from {fmt(queue.accounts)} senders
            </span>
          )}
        </div>
        {mine && mine.score.decided > 0 && (
          <p className={s.score} role="status">
            Your decisions: <strong className="num">{mine.score.decided}</strong> · matched the answer key:{" "}
            <strong className="num">{mine.score.right}</strong> · the model&apos;s flag was right on{" "}
            <strong className="num">{mine.score.model_right}</strong> of them <span className="muted">(training mode, synthetic data)</span>
          </p>
        )}
        <div className={s.tableWrap}>
          <table className={s.queue}>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Sender → receiver</th>
                <th scope="col">Amount</th>
                <th scope="col">Why flagged</th>
                <th scope="col">Check by</th>
              </tr>
            </thead>
            <tbody>
              {queue?.groups.map((g) => (
                <tr key={g.event_id}>
                  <td className="num">
                    <Link href={`/case/?id=${g.event_id}`} className={s.rank}>{fmt(g.rank)}</Link>
                    <div className={s.top}>{topShare(g.percentile)}</div>
                  </td>
                  <td>
                    <Link href={`/case/?id=${g.event_id}`} className={s.who}>{g.from_name ?? "unknown account"}</Link>
                    <span className="muted"> → {g.to_name ?? "unknown"}</span>
                    <div className={`muted ${s.small}`}>
                      {g.from_bank_name}{g.alerts > 1 ? ` · ${g.alerts} alerts from this sender` : ""}
                    </div>
                  </td>
                  <td className="num">
                    {g.amount_paid.toLocaleString("en-US", { maximumFractionDigits: 2 })}{" "}
                    <span className="muted">{g.payment_currency}</span>
                    <div className={`muted ${s.small}`}>{g.payment_format}</div>
                  </td>
                  <td>
                    <span className={s.reason}>{whyFirst(g) ?? g.top_reason ?? "Score from the model"}</span>
                    <div className={s.chips}>
                      {myState.has(g.event_id) && <span className={`${s.chip} ${s.mineChip}`}>{STATE_CHIP[myState.get(g.event_id)!] ?? "decided"}</span>}
                      {g.has_ai && <span className={`${s.chip} ${s.aiChip}`} title="An AI draft, checked by code, is on the case page">AI draft</span>}
                      {ownAccount(g) && <span className={s.chip} title={ownAccount(g)!.text}>{ownAccount(g)!.label}</span>}
                      {g.rules.map((r) => <span key={r} className={s.chip}>rule: {r.replace("_", " ")}</span>)}
                      {COLD[g.cold_policy] && <span className={s.chip}>{COLD[g.cold_policy]}</span>}
                    </div>
                  </td>
                  <td className={`num ${s.due}`}>{g.due.slice(5, 16).replace("T", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {queue && shown < queue.accounts && (
          <button type="button" onClick={more} className={s.more}>Show more ({fmt(queue.accounts - shown)} accounts left)</button>
        )}
        <Explain label="What is rank?">
          <p>The team has time for only so many checks a day, so the riskiest go
          first. Rank = place in the list (the model&apos;s score, with two-rule and both-new-account
          alerts first). It is not a probability. Check by = 24 hours after the payment.</p>
        </Explain>
      </section>
    </>
  );
}
