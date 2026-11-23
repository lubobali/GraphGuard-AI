import Link from "next/link";
import { useEffect, useState } from "react";
import type { DecisionCase, Decisions } from "../../lib/api";
import { get } from "../../lib/api";
import { money, stateText } from "../../lib/caseLogic.js";
import { fmt } from "../../lib/logic.js";
import { visitorId } from "../../lib/visitor.js";
import s from "./review.module.css";

// The reviewer's start page (S7.15): decisions waiting for a second look (four eyes) --
// your own, and the seeded ones of Sam, the demo investigator -- then the ones you reviewed.
function Row({ c, me }: { c: DecisionCase; me: string }) {
  const owner = c.owner === "demo" ? "demo" : "mine";
  return (
    <tr>
      <td className="num"><Link href={`/case/?id=${c.event_id}&review=${owner}`}>#{fmt(c.rank)}</Link></td>
      <td><Link href={`/case/?id=${c.event_id}&review=${owner}`} className={s.who}>{c.from_name ?? "?"}</Link>
        <span className="muted"> → {c.to_name ?? "?"}</span>
        <div className="muted" style={{ fontSize: 12 }}>{money(c.amount_paid, c.payment_currency)}</div></td>
      <td>{c.owner === me ? "You" : "Sam (demo)"}</td>
      <td><strong>{c.decision === "escalate" ? "Suspicious" : c.decision === "close" ? "Close" : "—"}</strong>
        {c.reason && <div className="muted" style={{ fontSize: 13 }}>&ldquo;{c.reason}&rdquo;</div>}</td>
      <td>{stateText(c).title.replace("Saved: you", "Decided:").replace("Saved: ", "")}</td>
    </tr>
  );
}

export default function ReviewPage() {
  const [d, setD] = useState<Decisions | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [me, setMe] = useState("");
  useEffect(() => {
    setMe(visitorId());
    get<Decisions>(`/decisions?visitor=${visitorId()}`).then(setD).catch((e) => setErr(String(e)));
  }, []);
  const waiting = (d?.cases ?? []).filter((c) => c.state === "awaiting_review");
  const done = (d?.cases ?? []).filter((c) => c.state !== "awaiting_review" && c.acted && c.owner === "demo");
  return (
    <>
      <section className={s.hero}>
        <h1>Waiting for review</h1>
        <p className="ink2">
          In a bank, every decision gets a second look before it is final (&ldquo;four eyes&rdquo;). Open a case,
          read the investigator&apos;s reason, check the evidence, then approve it or send it back.
          Sam, a demo investigator, has decided 8 alerts. Some of Sam&apos;s decisions are wrong: can you find them?
        </p>
      </section>
      {err && <p role="alert">Could not load the cases ({err}).</p>}
      <section className="card">
        <h2 className={s.h2}>To review ({waiting.length})</h2>
        {waiting.length === 0 ? <p className="muted">Nothing waiting. Decide some alerts as an investigator, or come back later.</p> : (
          <div className={s.wrap}><table className={s.table}>
            <thead><tr><th scope="col">#</th><th scope="col">Payment</th><th scope="col">Decided by</th><th scope="col">Decision and reason</th><th scope="col">State</th></tr></thead>
            <tbody>{waiting.map((c) => <Row key={`${c.event_id}-${c.owner}`} c={c} me={me} />)}</tbody>
          </table></div>
        )}
      </section>
      {done.length > 0 && (
        <section className="card" style={{ marginTop: 16 }}>
          <h2 className={s.h2}>You reviewed ({done.length})</h2>
          <div className={s.wrap}><table className={s.table}>
            <thead><tr><th scope="col">#</th><th scope="col">Payment</th><th scope="col">Decided by</th><th scope="col">Decision and reason</th><th scope="col">State</th></tr></thead>
            <tbody>{done.map((c) => <Row key={`${c.event_id}-${c.owner}`} c={c} me={me} />)}</tbody>
          </table></div>
        </section>
      )}
    </>
  );
}
