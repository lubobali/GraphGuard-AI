import { contributionBars } from "../lib/caseLogic.js";
import s from "./WhyBars.module.css";

// The biggest pushes on this score, up (raises risk) and down (lowers risk), on one
// symmetric scale. Direction is said in words and by side, never by colour alone.
type C = { feature: string; value: number | null; contribution: number };

export default function WhyBars({ contributions }: { contributions: C[] }) {
  const bars = contributionBars(contributions, 8);
  return (
    <figure className={s.fig}>
      <figcaption className={s.cap}>
        What moved this score <span className="muted">· the model&apos;s own SHAP values, biggest first</span>
      </figcaption>
      <div className={s.axis} aria-hidden="true"><span>← lowers risk</span><span>raises risk →</span></div>
      <ul className={s.list}>
        {bars.map((b: ReturnType<typeof contributionBars>[number]) => (
          <li key={b.feature} className={s.row}
            aria-label={`${b.label}: ${b.direction === "up" ? "raises" : "lowers"} risk by ${Math.abs(b.contribution).toFixed(2)}`}>
            <span className={s.label}>{b.label}</span>
            <span className={s.track}>
              <span className={s.mid} />
              <span className={b.direction === "up" ? s.up : s.down}
                style={{ width: `${b.share * 50}%`, [b.direction === "up" ? "left" : "right"]: "50%" }} />
            </span>
            <span className={`num ${s.val}`}>{b.contribution >= 0 ? "+" : "−"}{Math.abs(b.contribution).toFixed(2)}</span>
          </li>
        ))}
      </ul>
      <details className={s.raw}>
        <summary>The raw numbers</summary>
        <table>
          <thead><tr><th scope="col">Feature</th><th scope="col">Value the model saw</th><th scope="col">Push (log-odds)</th></tr></thead>
          <tbody>
            {contributions.map((c) => (
              <tr key={c.feature}><td>{c.feature}</td><td className="num">{c.value === null || Number.isNaN(c.value) ? "none (never sent)" : Number(c.value).toLocaleString("en-US", { maximumFractionDigits: 3 })}</td><td className="num">{c.contribution.toFixed(4)}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
