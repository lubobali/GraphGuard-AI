import Head from "next/head";
import Link from "next/link";
import { useEffect, useState } from "react";
import RingGraph from "../../components/RingGraph";
import { strengthText } from "../../lib/caseLogic.js";
import R from "../../lib/reviewerNumbers.json";
import TOUR from "../../lib/tour.json";
import { limitLine, paymentLine, scoreText, verdict } from "../../lib/tourLogic.js";
import s from "./try.module.css";

// S7.18: "Try one case" -- four steps, started by the visitor. Everything comes from the static
// tour file: no API call, no AI call, nothing saved on the server.
type Claim = { text: string; cites: number[] };
type Case = (typeof TOUR.cases)[number];
const STEPS = ["Look", "Decide", "Answer", "Second opinion"];
const SONNET = R.models["anthropic/claude-sonnet-5.5"];

function Steps({ at }: { at: number }) {
  return (
    <ol className={s.steps} aria-label="Steps">
      {STEPS.map((name, i) => (
        <li key={name} className={i === at ? s.stepOn : i < at ? s.stepDone : s.step}
          aria-current={i === at ? "step" : undefined}>{i + 1}. {name}</li>
      ))}
    </ol>
  );
}

function Opinion({ c, choice }: { c: Case; choice: string }) {
  const r = c.reviews.find((x) => x.direction === choice);
  if (!r) return null;
  const kept = (r.review.kept ?? []) as Claim[];
  return (
    <div className={s.opinion}>
      <p className={s.lead}>An AI read the same payments and argued <em>against</em> your choice:</p>
      <p className={s.strength}>{strengthText(r.review.strength, choice)}</p>
      {kept.length > 0 && <ul className={s.claims}>{kept.slice(0, 3).map((k, i) => <li key={i}>{k.text}</li>)}</ul>}
      <p className={s.note}>Every fact above was checked by code against the payments. {SONNET.note}</p>
    </div>
  );
}

export default function Try() {
  const [idx, setIdx] = useState(0);
  const [step, setStep] = useState(0);
  const [choice, setChoice] = useState<string | null>(null);
  const [results, setResults] = useState<(boolean | null)[]>([null, null, null]);
  const c = TOUR.cases[idx];
  const v = choice ? verdict(choice, c.answer) : null;
  const next = results.findIndex((r, i) => r === null && i !== idx);
  // each new step comes into view (step 0 is the top of the page)
  useEffect(() => {
    if (step > 0) document.getElementById(`step${step}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [step]);

  function decide(ch: string) {
    setChoice(ch);
    setResults((rs) => rs.map((r, i) => (i === idx ? verdict(ch, c.answer).right : r)));
    setStep(2);
  }
  function another() {
    setIdx(next); setStep(0); setChoice(null);
    window.scrollTo({ top: 0 });
  }

  return (
    <>
      <Head><title>Try one case · GraphGuard</title></Head>
      <div className={s.page}>
        <p className={s.kicker}>Case {idx + 1} of {TOUR.cases.length} · {scoreText(results)}</p>
        <Steps at={step} />

        {step <= 1 && (
          <section className="card">
            <h1 className={s.h1}>A bank&apos;s computer flagged this payment out of a million. You are the investigator.</h1>
            <p className={s.payment}>{paymentLine(c.payment)}</p>
            <p className={s.lead}>Why the computer flagged it:</p>
            <ul className={s.reasons}>{c.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            <p className={s.lead}>Where the money went (press Play all):</p>
            <RingGraph graph={c.ring} ringTx={null} compact />
            {step === 0 && <button type="button" className={s.go} onClick={() => setStep(1)}>I&apos;ve looked: decide →</button>}
          </section>
        )}

        {step === 1 && (
          <section id="step1" className={`card ${s.decide}`} aria-label="Your call">
            <p className={s.h2}>Your call: is this money laundering?</p>
            <div className={s.choices}>
              <button type="button" className={s.bad} onClick={() => decide("escalate")}>Suspicious<span>send it to a case</span></button>
              <button type="button" className={s.ok} onClick={() => decide("close")}>Normal<span>close the alert</span></button>
            </div>
          </section>
        )}

        {step >= 2 && v && choice && (
          <section id="step2" className="card" aria-live="polite">
            <p className={v.right ? s.right : s.wrong}>{v.headline}</p>
            <p className={s.h2}>{v.what}</p>
            {v.shape && <p>{v.shape}</p>}
            {c.answer.ring_tx.length > 0 && (
              <>
                <p className={s.lead}>The red arrows are the scheme&apos;s payments:</p>
                <RingGraph graph={c.ring} ringTx={new Set(c.answer.ring_tx)} compact />
              </>
            )}
            <p className={s.limit}>{limitLine(TOUR.limits)}</p>
            {step === 2 && <button type="button" className={s.go} onClick={() => setStep(3)}>What does the AI say? →</button>}
          </section>
        )}

        {step === 3 && choice && (
          <section id="step3" className="card">
            <Opinion c={c} choice={choice} />
            <div className={s.end}>
              {next >= 0
                ? <button type="button" className={s.go} onClick={another}>Try another case →</button>
                : <p className={s.h2}>Done: {scoreText(results)}.</p>}
              <Link href="/" className={s.full}>See the full tool: the whole list, worst first</Link>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
