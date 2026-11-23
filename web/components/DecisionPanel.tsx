import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";
import { get } from "../lib/api";
import { closeCodes, reviewText, reviewView, stateText, strengthText, timeline, trainingText } from "../lib/caseLogic.js";
import R from "../lib/reviewerNumbers.json";
import { visitorId } from "../lib/visitor.js";
import s from "./DecisionPanel.module.css";

// The case workflow on the Case page (S7.15). Investigator: decide once, with a reason;
// then the case waits for a second review. Reviewer: approve or send back (own case, or
// Sam's seeded ones). Every step is a new row; the page never edits history.
type Row = { who: string; role: string; action: string; code: string | null; reason: string; at: string | null };
export type Case = { state: string; decision: string | null; code: string | null; reason: string | null;
  sar_due: string | null; history: Row[] };
type Cases = { mine: Case; sam: Case | null };
type AlertLite = { event_id: number; rank: number; event_time: string; rules: string[];
  agent: { model: string; at: string }[]; reviews?: Review[] };
type Review = { direction: string; model: string; review: { strength: string; summary: string;
  kept: { text: string; cites: number[] }[]; dropped: { text: string; cites: number[]; why: string }[] } };

// S7.17: the AI second reviewer, shown only AFTER a decision (it must not anchor the person).
function SecondOpinion({ reviews, decision }: { reviews?: Review[]; decision: string | null }) {
  const views = reviewView(reviews, decision, R.models);
  if (!views.length) return null;
  return (
    <div className={s.second}>
      <p className={s.secondHead}>AI second opinion: the case against {decision === "close" ? "closing" : "escalating"}</p>
      {views.map((v: { model: string; label: string; strength: string | null; note: string; summary: string;
        kept: { text: string; cites: number[] }[]; dropped: { text: string; why: string }[] }) => (
        <div key={v.model} className={s.opinion}>
          <p className={`${s.strength} ${v.strength ? s["st_" + v.strength] : ""}`}>{strengthText(v.strength, decision)} <span className="muted">({v.label})</span></p>
          {v.summary && <p className={s.lockedDetail}><span className="muted">Summary (not checked):</span> {v.summary}</p>}
          {v.kept.length > 0 && <ul className={s.claims}>{v.kept.map((c, i) => <li key={i}>{c.text} <span className="muted">· tx {c.cites.join(", ")}</span></li>)}</ul>}
          {v.dropped.length > 0 && (
            <details className={s.dropped}><summary>{v.dropped.length} claim{v.dropped.length === 1 ? "" : "s"} dropped by the checker</summary>
              <ul>{v.dropped.map((c, i) => <li key={i}><s>{c.text}</s> <span className="muted">· {c.why}</span></li>)}</ul></details>
          )}
          {v.note && <p className={s.note}>{v.note}</p>}
        </div>
      ))}
      <p className={s.note}>{R.note}</p>
    </div>
  );
}
const MAX = 500;

async function post(id: number, body: object) {
  const r = await fetch(`/api/alerts/${id}/actions`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `not saved (${r.status})`);
  return data;
}

function Decide({ a, onSaved, sentBack, onCancel }: { a: AlertLite; onSaved: (next: boolean) => Promise<void>; sentBack?: Row; onCancel?: () => void }) {
  const [choice, setChoice] = useState<"escalate" | "close" | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ready = choice && reason.trim() && (choice === "escalate" || code) && !busy;

  async function submit(next: boolean) {
    if (!ready) return;
    setBusy(true); setErr(null);
    try {
      await post(a.event_id, { visitor: visitorId(), role: "investigator", action: choice,
        code: choice === "close" ? code : null, reason: reason.trim() });
      await onSaved(next);
    } catch (e) { setErr(String((e as Error).message)); setBusy(false); }
  }

  return (
    <div>
      {sentBack && <p className={s.banner}>The reviewer sent this back: &ldquo;{sentBack.reason}&rdquo;</p>}
      <div className={s.choices} role="group" aria-label="Your decision">
        <button type="button" aria-pressed={choice === "escalate"} className={`${s.choice} ${choice === "escalate" ? s.onBad : ""}`}
          onClick={() => setChoice("escalate")}>Suspicious<span>escalate to a case</span></button>
        <button type="button" aria-pressed={choice === "close"} className={`${s.choice} ${choice === "close" ? s.onOk : ""}`}
          onClick={() => setChoice("close")}>False alarm<span>close, not suspicious</span></button>
      </div>
      {choice === "close" && (
        <fieldset className={s.codes}>
          <legend>Why close it?</legend>
          {closeCodes().map((c: { code: string; label: string }) => (
            <label key={c.code}><input type="radio" name="code" value={c.code} checked={code === c.code}
              onChange={() => setCode(c.code)} /> {c.label}</label>
          ))}
        </fieldset>
      )}
      {choice && (
        <>
          <label htmlFor="reason" className={s.label}>Your reason (required, one or two sentences)</label>
          <textarea id="reason" className={s.reason} maxLength={MAX} value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={choice === "escalate" ? "e.g. money split to 5 accounts in an hour, then gathered in one" : "e.g. a regular supplier payment, seen every week"} />
          <div className={s.count}>{reason.length} / {MAX}</div>
          <div className={s.actions}>
            <button type="button" className={s.primary} disabled={!ready} onClick={() => submit(true)}>Submit and next alert →</button>
            <button type="button" className={s.secondary} disabled={!ready} onClick={() => submit(false)}>Submit</button>
          </div>
        </>
      )}
      {onCancel && <button type="button" className={s.link} onClick={onCancel}>Cancel: keep my decision</button>}
      {err && <p role="alert" className={s.err}>{err}</p>}
    </div>
  );
}

export default function DecisionPanel({ a }: { a: AlertLite }) {
  const router = useRouter();
  const [cases, setCases] = useState<Cases | null>(null);
  const [changing, setChanging] = useState(false);
  const [answer, setAnswer] = useState<boolean | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    const c = await get<Cases>(`/alerts/${a.event_id}/case?visitor=${visitorId()}`);
    setCases(c);
    return c;
  }, [a.event_id]);
  useEffect(() => { setChanging(false); setAnswer(null); load().catch((e) => setErr(String(e))); }, [load]);

  const mine = cases?.mine;
  const decided = mine && mine.history.some((h) => h.role === "investigator");
  // training mode: the answer key, only once you have decided
  useEffect(() => {
    if (!decided) return;
    get<{ is_laundering: boolean }>(`/alerts/${a.event_id}/answer`).then((x) => setAnswer(x.is_laundering)).catch(() => {});
  }, [decided, a.event_id]);

  async function nextAlert() {
    const n = await get<{ event_id: number | null }>(`/next?visitor=${visitorId()}&after=${a.rank}`);
    if (n.event_id) router.push(`/case/?id=${n.event_id}`);
    else router.push("/");
  }
  async function onSaved(next: boolean) {
    setChanging(false);
    await load();
    if (next) await nextAlert();
  }

  if (err) return <p role="alert" className={s.err}>Could not load your case ({err}).</p>;
  if (!mine) return <p className="muted">Loading your case…</p>;
  const st = stateText(mine);
  const open = mine.state === "new" || mine.state === "sent_back" || changing;
  const sentBack = mine.state === "sent_back" ? [...mine.history].reverse().find((h) => h.action === "send_back") : undefined;
  const lastDecision = [...mine.history].reverse().find((h) => h.role === "investigator");
  const t = trainingText(lastDecision?.action ?? null, answer);

  return (
    <div>
      {open ? <Decide a={a} onSaved={onSaved} sentBack={sentBack} onCancel={changing ? () => setChanging(false) : undefined} /> : (
        <div className={`${s.locked} ${mine.state === "escalated" || mine.decision === "escalate" ? s.lockedBad : s.lockedOk}`} role="status">
          <p className={s.lockedTitle}>✓ {st.title}</p>
          <p className={s.lockedDetail}>{st.detail}</p>
          {mine.reason && <p className={s.lockedDetail}>Your reason: &ldquo;{mine.reason}&rdquo;</p>}
          <div className={s.actions}>
            <button type="button" className={s.primary} onClick={nextAlert}>Next alert →</button>
            <button type="button" className={s.link} onClick={() => setChanging(true)}>Change decision</button>
          </div>
        </div>
      )}
      {t && !open && (
        <div className={t.right ? s.right : s.wrong} role="status">
          <strong>{t.right ? "✓ " : "✗ "}{t.title}.</strong> {t.detail}
          <div className={s.note}>Training mode: the data is synthetic, so the answer is known. A real bank would not know it today.</div>
        </div>
      )}
      {!open && <SecondOpinion reviews={a.reviews} decision={mine.decision ?? lastDecision?.action ?? null} />}
      <History a={a} rows={mine.history} />
    </div>
  );
}

function History({ a, rows }: { a: AlertLite; rows: Row[] }) {
  const items = timeline(a, rows);
  if (!items.length) return null;
  return (
    <details className={s.history} open={rows.length > 0}>
      <summary>History ({items.length})</summary>
      <ol>
        {items.map((it: { i: number; kind: string; at: string; text: string }) => (
          <li key={it.i}><span className={`${s.tag} ${s[it.kind]}`}>{it.kind === "person" ? "person" : it.kind === "ai" ? "AI" : "rule"}</span>
            <span className="muted num">{it.at.slice(0, 16).replace("T", " ")}</span> {it.text}</li>
        ))}
      </ol>
      <p className="muted" style={{ fontSize: 12, margin: "6px 0 0" }}>Every step is kept; nothing is edited or deleted (the audit trail).</p>
    </details>
  );
}

const CODE_LABEL: Record<string, string> = Object.fromEntries(
  closeCodes().map((c: { code: string; label: string }) => [c.code, c.label]));

/** The reviewer's side (S7.15): the investigator's decision, then Approve or Send back. */
export function ReviewPanel({ a, owner }: { a: AlertLite; owner: "demo" | "mine" }) {
  const router = useRouter();
  const [cases, setCases] = useState<Cases | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [answer, setAnswer] = useState<boolean | null>(null);

  const load = useCallback(async () => setCases(await get<Cases>(`/alerts/${a.event_id}/case?visitor=${visitorId()}`)), [a.event_id]);
  useEffect(() => { setAnswer(null); load().catch((e) => setErr(String(e))); }, [load]);
  const c = owner === "demo" ? cases?.sam : cases?.mine;
  const reviewed = c?.history.find((h) => h.role === "reviewer" && h.who === "you");
  const lastReview = c ? [...c.history].reverse().find((h) => h.role === "reviewer" && h.who === "you") : undefined;
  const decisionRow = c ? [...c.history].reverse().find((h) => h.role === "investigator") : undefined;
  useEffect(() => {
    if (!reviewed) return;
    get<{ is_laundering: boolean }>(`/alerts/${a.event_id}/answer`).then((x) => setAnswer(x.is_laundering)).catch(() => {});
  }, [reviewed, a.event_id]);

  async function act(action: "approve" | "send_back") {
    setBusy(true); setErr(null);
    try {
      await post(a.event_id, { visitor: visitorId(), owner: owner === "demo" ? "demo" : visitorId(), role: "reviewer",
        action, reason: reason.trim() });
      await load();
    } catch (e) { setErr(String((e as Error).message)); }
    setBusy(false);
  }

  if (err && !c) return <p role="alert" className={s.err}>{err}</p>;
  if (!cases) return <p className="muted">Loading the case…</p>;
  if (!c || !decisionRow) return <p className="muted">There is no decision to review on this alert. <Link href="/review/">Back to the review list</Link></p>;
  const by = owner === "demo" ? "Sam (demo investigator)" : "You";
  const t = lastReview ? reviewText(lastReview.action, decisionRow.action, answer) : null;
  return (
    <div>
      <div className={s.under}>
        <p className={s.lockedTitle}>{by} decided: {decisionRow.action === "escalate" ? "suspicious, escalate" : `close (${CODE_LABEL[decisionRow.code ?? ""] ?? decisionRow.code})`}</p>
        <p className={s.lockedDetail}>Reason: &ldquo;{decisionRow.reason}&rdquo;</p>
        {owner === "mine" && <p className={s.note}>You are reviewing your own decision. In a bank this must be another person (four eyes).</p>}
      </div>
      {c.state === "awaiting_review" ? (
        <>
          <label htmlFor="rreason" className={s.label}>Your note (required to send back)</label>
          <textarea id="rreason" className={s.reason} maxLength={MAX} value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. the ring picture shows money coming back: look again" />
          <div className={s.actions}>
            <button type="button" className={s.primary} disabled={busy} onClick={() => act("approve")}>Approve</button>
            <button type="button" className={s.secondary} disabled={busy || !reason.trim()} onClick={() => act("send_back")}>Send back</button>
          </div>
        </>
      ) : (
        <div className={`${s.locked} ${s.lockedOk}`} role="status">
          <p className={s.lockedTitle}>✓ {stateText(c).title}</p>
          <p className={s.lockedDetail}>{stateText(c).detail}</p>
          <div className={s.actions}>
            <button type="button" className={s.primary} onClick={() => router.push("/review/")}>Next case to review →</button>
          </div>
        </div>
      )}
      {err && <p role="alert" className={s.err}>{err}</p>}
      {t && (
        <div className={t.right ? s.right : s.wrong} role="status">
          <strong>{t.right ? "✓ " : "✗ "}{t.title}.</strong> {t.detail}
          <div className={s.note}>Training mode: the data is synthetic, so the answer is known.</div>
        </div>
      )}
      <SecondOpinion reviews={a.reviews} decision={decisionRow.action} />
      <History a={a} rows={c.history} />
    </div>
  );
}
