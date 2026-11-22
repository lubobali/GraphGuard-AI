import Architecture from "../../components/Architecture";
import N from "../../lib/aboutNumbers.json";
import { fmt } from "../../lib/logic.js";
import s from "./about.module.css";

const REPO = "https://github.com/lubobali/GraphGuard-AI";
const doc = (path: string) => `${REPO}/blob/main/${path}`;

const RESULTS = [
  { name: "XGBoost (this system's model)", pr: N.pr_auc.model.value, caught: N.caught_at_5000.model.value, strong: true },
  { name: "Graph neural network (GraphSAGE)", pr: N.pr_auc.gnn.value, caught: null, note: "lost — FINDING-007" },
  { name: "Six simple rules", pr: N.pr_auc.rules.value, caught: N.caught_at_5000.rules.value },
  { name: "Largest amounts first", pr: N.pr_auc.by_amount.value, caught: null },
  { name: "Random", pr: N.pr_auc.random.value, caught: N.caught_at_5000.random.value },
];

const FINDINGS = [
  ["The laundering is in the shape, not the row", "A ring spans ~8 accounts over ~3 days; each payment looks ordinary.", "FINDING-002/003"],
  ["Stale features cost 83%", "Account history refreshed in batch instead of per payment loses most of the signal.", "FINDING-008"],
  ["The graph neural network lost", "Same features, same budget: 0.045 vs 0.282 PR-AUC. Written up, not tuned away.", "FINDING-007"],
  ["Rules barely work on this data", "Thresholds set by hub accounts; 21 laundering payments in their top 5,000 vs 542.", "FINDING-016"],
  ["The truth arrives late", "By the end of the 2.1-day window, 0.28% of the laundering had a known label.", "FINDING-017"],
  ["\"Weekday\" was a simulator artifact", "Found by the explanations; removing it costs nothing (0.2825 vs 0.2816).", "FINDING-018"],
];

export default function AboutPage() {
  return (
    <div className={s.page}>
      <section className={s.intro}>
        <h1>What this is</h1>
        <p>
          GraphGuard scores bank transfers for money laundering as they arrive, puts the riskiest
          in front of an investigator, and shows <em>why</em> — including the ring of accounts
          around each alert. It was built to answer one question a compliance manager asks:{" "}
          <strong>with the people I have, how much laundering do we catch, and how much do we miss?</strong>
        </p>
        <p className={s.honest}>
          Said first, every time: the data is <strong>synthetic</strong> (IBM&apos;s AMLworld
          simulator); the stream is a <strong>replay</strong> of {fmt(N.transactions_in_window.value)} transactions,
          not live bank traffic; it runs on <strong>one server</strong>. Numbers are measured on the
          validation window; the test window is still sealed.
        </p>
      </section>

      <section className="card">
        <h2 className={s.h2}>How the data moves</h2>
        <Architecture />
      </section>

      <section className="card">
        <h2 className={s.h2}>The result, against honest baselines</h2>
        <table className={s.table}>
          <thead>
            <tr><th scope="col">Ranking</th><th scope="col">PR-AUC</th><th scope="col">Laundering in the top 5,000</th></tr>
          </thead>
          <tbody>
            {RESULTS.map((r) => (
              <tr key={r.name} className={r.strong ? s.strong : undefined}>
                <td>{r.name}{r.note && <span className="muted"> · {r.note}</span>}</td>
                <td className="num">{r.pr.toFixed(5)}</td>
                <td className="num">{r.caught === null ? "—" : `${fmt(r.caught)} of ${fmt(N.laundering_in_window.value)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="muted" style={{ fontSize: 13 }}>
          PR-AUC is the validators&apos; number (base rate 0.1%, so random ≈ 0.001). The model also
          catches {N.rings_caught_at_5000.value} of {N.rings_caught_at_5000.of} laundering rings in its top 5,000
          (at least half of each ring&apos;s payments). The live stream reproduces every one of
          these scores exactly.
        </p>
      </section>

      <section className="card">
        <h2 className={s.h2}>What we learned</h2>
        <ul className={s.findings}>
          {FINDINGS.map(([t, d, ref]) => (
            <li key={t}><strong>{t}.</strong> {d} <a href={doc("docs/findings.md")} className={s.ref}>{ref}</a></li>
          ))}
        </ul>
      </section>

      <div className={s.grid}>
        <section className="card">
          <h2 className={s.h2}>The leakage contract</h2>
          <ol className={s.list}>
            <li>Split by time, never randomly.</li>
            <li>The graph at time T holds only edges before T.</li>
            <li>No feature uses what did not exist at decision time.</li>
            <li>The test window is opened once.</li>
            <li>A feature that looks too good is investigated, not celebrated.</li>
          </ol>
          <p className="muted" style={{ fontSize: 13 }}>Enforced by three build guards; the ring drawings obey rule 2 too.</p>
        </section>
        <section className="card">
          <h2 className={s.h2}>Model risk, in SR 26-2&apos;s terms</h2>
          <dl className={s.dl}>
            <dt>Purpose</dt><dd>Rank transfers for review by a limited team; a person decides.</dd>
            <dt>Data</dt><dd>Synthetic; trained on the first window, measured on the next.</dd>
            <dt>Limits</dt><dd>Simulator patterns may not transfer; a weekday artifact is known.</dd>
            <dt>Monitoring</dt><dd>Alert on the scorer and the stream; drift and retraining in Phase 8.</dd>
            <dt>Scope</dt><dd>SR 26-2 (April 2026, guidance) covers the model, not the rules, and leaves generative AI out.</dd>
          </dl>
        </section>
      </div>

      <section className={s.links}>
        <a href={REPO}>Source code</a> · <a href={doc("docs/findings.md")}>All findings</a> ·{" "}
        <a href={doc("docs/adr")}>Decisions (ADRs)</a> · <a href={doc("PLAN.md")}>The plan</a>
      </section>
    </div>
  );
}
