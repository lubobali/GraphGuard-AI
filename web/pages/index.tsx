import Link from "next/link";
import { useEffect, useState } from "react";
import CapacityChart from "../components/CapacityChart";
import type { Capacity, Curve, Performance, Queue } from "../lib/api";
import { get } from "../lib/api";
import { capacitySentence, fmt, kFor, plural, teamSize, topShare } from "../lib/logic.js";
import s from "./index.module.css";

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

export default function QueuePage() {
  const [perDay, setPerDay] = useState(100);
  const settled = useDebounced(perDay, 200);
  const [cap, setCap] = useState<Capacity | null>(null);
  const [curve, setCurve] = useState<Curve | null>(null);
  const [perf, setPerf] = useState<Performance | null>(null);
  const [queue, setQueue] = useState<Queue | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    get<Curve>("/capacity/curve").then(setCurve).catch((e) => setError(String(e)));
  }, []);
  useEffect(() => {
    setPage(1);
    Promise.all([
      get<Capacity>(`/capacity?per_day=${settled}`),
      get<Performance>(`/performance?per_day=${settled}`),
      get<Queue>(`/queue?per_day=${settled}&page=1`),
    ])
      .then(([c, p, q]) => { setCap(c); setPerf(p); setQueue(q); })
      .catch((e) => setError(String(e)));
  }, [settled]);

  async function more() {
    if (!queue) return;
    const q = await get<Queue>(`/queue?per_day=${settled}&page=${page + 1}`);
    setQueue({ ...q, groups: [...queue.groups, ...q.groups] });
    setPage(page + 1);
  }

  const sentence = cap ? capacitySentence(perDay === settled ? perDay : settled, cap.rankings) : null;
  const shown = queue?.groups.length ?? 0;

  return (
    <>
      <section className={s.hero}>
        <h1>How many alerts can your team work?</h1>
        <p className="ink2">
          Move the slider. Every number comes from scoring all 1,015,300 transactions of a
          2.1-day validation window and checking them against the simulator&apos;s answer key.
        </p>
      </section>

      {error && <p role="alert" className={s.error}>Could not load the data ({error}).</p>}

      <section className={`card ${s.slider}`} aria-labelledby="slider-label">
        <label id="slider-label" htmlFor="perday" className={s.label}>
          My team works <strong className="num">{fmt(perDay)}</strong> alerts a day
          <span className="muted"> · about {plural(teamSize(perDay), "investigator", "investigators")}</span>
        </label>
        <input id="perday" type="range" min={10} max={1000} step={10} value={perDay}
          onChange={(e) => setPerDay(Number(e.target.value))} className={s.range}
          aria-valuetext={`${perDay} alerts a day`} />
        <div className={s.scale} aria-hidden="true"><span>10</span><span>1,000</span></div>
        {sentence && (
          <p className={s.sentence} aria-live="polite">
            {sentence.lead} <span className={s.missed}>{sentence.missed}</span>{" "}
            <span className="ink2">{sentence.rules}</span>
          </p>
        )}
        <p className={`muted ${s.small}`}>
          “Caught” = the transaction is in the alerts worked. A ring is caught when at least half
          of its transactions are. Team size assumes ~20 alerts per investigator a day.
        </p>
      </section>

      <div className={s.grid2}>
        <section className="card">{curve && <CapacityChart curve={curve} perDay={settled} />}</section>
        <section className="card" aria-labelledby="truth-h">
          <h2 id="truth-h" className={s.h2}>What we know, and when</h2>
          {perf?.measured_offline && (
            <div className={s.layer}>
              <div className={s.layerHead}><span className={s.solid} aria-hidden="true" />Measured afterwards</div>
              <p>With the full answer key: <strong className="num">{fmt(perf.measured_offline.caught)}</strong> of{" "}
                {fmt(perf.laundering_in_window)} laundering transactions in the alerts worked.</p>
            </div>
          )}
          {perf && (
            <div className={s.layer}>
              <div className={s.layerHead}><span className={s.dashed} aria-hidden="true" />Known on the day</div>
              <p>
                By the end of the window, investigators had confirmed{" "}
                <strong className="num">{plural(perf.confirmed_so_far.known, "label", "labels")}</strong>{" "}
                ({fmt(perf.confirmed_so_far.laundering)} laundering). The rest —{" "}
                <strong className="num">
                  {(100 * (1 - perf.confirmed_so_far.laundering / perf.laundering_in_window)).toFixed(1)}%
                </strong>{" "}
                of the laundering — is still unknown: verdicts take days, police reports weeks.
              </p>
              <p className={`muted ${s.small}`}>Labels exist only for alerts someone worked, so they favour the model that chose them (FINDING-017).</p>
            </div>
          )}
        </section>
      </div>

      <section className={`card ${s.queueCard}`} aria-labelledby="queue-h">
        <div className={s.queueHead}>
          <h2 id="queue-h" className={s.h2}>Today&apos;s queue</h2>
          {queue && (
            <span className="muted num">
              {fmt(queue.alerts)} alerts from {fmt(queue.accounts)} accounts · highest risk first
            </span>
          )}
        </div>
        <div className={s.tableWrap}>
          <table className={s.queue}>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Sender → receiver</th>
                <th scope="col">Amount</th>
                <th scope="col">Why</th>
                <th scope="col">Due</th>
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
                    <span className={s.reason}>{g.top_reason ?? "Score from the model"}</span>
                    <div className={s.chips}>
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
        <p className={`muted ${s.small}`}>
          Rank = place in the queue (the model&apos;s score, with two-rule and both-new-account
          alerts first). It is not a probability. Due = 24 hours after the payment.
        </p>
      </section>
    </>
  );
}
