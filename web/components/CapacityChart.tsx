import { useMemo, useRef, useState } from "react";
import type { Curve } from "../lib/api";
import { fmt, nearest, perDayFor, scale, ticks, spreadLabels } from "../lib/logic.js";
import s from "./CapacityChart.module.css";

// Laundering caught vs alerts a day, for the system, the rules and random (S7.7).
// One axis, thin 2px lines, a legend + direct labels (identity never by colour alone),
// a crosshair that snaps to the nearest point, the same readout on keyboard focus,
// and a table view of the same numbers.
const SERIES = [
  { key: "system", label: "Our model (GraphGuard)", color: "var(--series-system)", dash: "" },
  { key: "rules", label: "Fixed rules (old way)", color: "var(--series-rules)", dash: "" },
  { key: "random", label: "Random checks (no help)", color: "var(--series-random)", dash: "5 4" },
] as const;
const W = 720, H = 300, M = { l: 52, r: 128, t: 14, b: 40 };
const TABLE_PER_DAY = [25, 50, 100, 200, 500, 1000, 2000];

type Pt = { perDay: number; k: number; caught: number; rings: number };

export default function CapacityChart({ curve, perDay }: { curve: Curve; perDay: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const pts = useMemo(() => {
    const out: Record<string, Pt[]> = {};
    for (const { key } of SERIES)
      out[key] = (curve[key] || []).map(([k, caught, rings]) => ({ perDay: perDayFor(k), k, caught, rings }));
    return out;
  }, [curve]);
  const sys = pts.system;
  if (!sys?.length) return null;
  const maxX = sys[sys.length - 1].perDay;
  const maxY = Math.max(...SERIES.map(({ key }) => Math.max(...pts[key].map((p) => p.caught))));
  const yTicks = ticks(maxY, 5);
  const x = scale(0, maxX, M.l, W - M.r);
  const y = scale(0, yTicks[yTicks.length - 1], H - M.b, M.t);
  const path = (key: string) => pts[key].map((p, i) => `${i ? "L" : "M"}${x(p.perDay).toFixed(1)},${y(p.caught).toFixed(1)}`).join("");
  const at = hover ?? perDay;
  const endY: number[] = spreadLabels(
    SERIES.map(({ key }) => y(pts[key][pts[key].length - 1].caught)), 14, M.t, H - M.b);
  const readout = SERIES.map(({ key, label, color }) => ({ key, label, color, p: nearest(pts[key], at) }));

  function move(e: React.PointerEvent<SVGSVGElement>) {
    const r = svg.current!.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    setHover(Math.max(0, Math.min(maxX, x.invert(px))));
  }
  function key(e: React.KeyboardEvent) {
    const step = e.shiftKey ? 100 : 10;
    if (e.key === "ArrowRight") setHover(Math.min(maxX, at + step));
    if (e.key === "ArrowLeft") setHover(Math.max(0, at - step));
    if (e.key === "Escape") setHover(null);
  }
  const tipX = x(readout[0].p.perDay) / W;
  // near the right edge the readout flips to the left of the crosshair
  const tipStyle = { left: `${tipX * 100}%`, transform: tipX > 0.55 ? "translateX(calc(-100% - 10px))" : "translateX(10px)" };

  return (
    <figure className={s.fig}>
      <figcaption className={s.cap}>
        <strong>Laundering payments found</strong>
        <span className="muted"> · by how many the team checks a day. Higher line = better list.</span>
      </figcaption>
      <ul className={s.legend} aria-label="Legend">
        {SERIES.map(({ key, label, color, dash }) => (
          <li key={key}>
            <svg width="18" height="8" aria-hidden="true">
              <line x1="0" y1="4" x2="18" y2="4" stroke={color} strokeWidth="2" strokeDasharray={dash} />
            </svg>
            {label}
          </li>
        ))}
      </ul>
      <div className={s.plot}>
        <svg ref={svg} viewBox={`0 0 ${W} ${H}`} className={s.svg} role="img" tabIndex={0}
          aria-label={`Chart: at ${fmt(at)} checks a day, ${readout.map((r) => `${r.label} ${fmt(r.p.caught)}`).join(", ")}. Arrow keys move.`}
          onPointerMove={move} onPointerLeave={() => setHover(null)} onKeyDown={key}>
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} className={t ? s.grid : s.base} />
              <text x={M.l - 8} y={y(t)} className={s.tick} textAnchor="end" dominantBaseline="middle">{fmt(t)}</text>
            </g>
          ))}
          {ticks(maxX, 6).filter((t) => t <= maxX).map((t) => (
            <text key={t} x={x(t)} y={H - M.b + 18} className={s.tick} textAnchor="middle">{fmt(t)}</text>
          ))}
          <text x={(M.l + W - M.r) / 2} y={H - 4} className={s.axisLabel} textAnchor="middle">payments checked a day</text>
          {SERIES.map(({ key, color, dash }) => (
            <path key={key} d={path(key)} fill="none" stroke={color} strokeWidth="2"
              strokeDasharray={dash} strokeLinejoin="round" strokeLinecap="round" />
          ))}
          {SERIES.map(({ key, label }, i) => {
            const last = pts[key][pts[key].length - 1];
            return (
              <text key={key} x={W - M.r + 8} y={endY[i]} className={s.direct} dominantBaseline="middle">
                {fmt(last.caught)} · {label.split(" (")[0]}
              </text>
            );
          })}
          <line x1={x(perDay)} x2={x(perDay)} y1={M.t} y2={H - M.b} className={s.marker} />
          {hover !== null && (
            <line x1={x(readout[0].p.perDay)} x2={x(readout[0].p.perDay)} y1={M.t} y2={H - M.b} className={s.cross} />
          )}
          {readout.map(({ key, color, p }) => (
            <circle key={key} cx={x(p.perDay)} cy={y(p.caught)} r="4.5" fill={color} className={s.dot} />
          ))}
        </svg>
        <div className={s.tip} style={tipStyle} aria-hidden="true">
          <div className={s.tipHead}>{fmt(readout[0].p.perDay)} checks a day</div>
          {readout.map(({ key, label, color, p }) => (
            <div key={key} className={s.tipRow}>
              <span className={s.key} style={{ background: color }} />
              <strong className="num">{fmt(p.caught)}</strong>
              <span className="muted">{label.split(" (")[0]}</span>
            </div>
          ))}
        </div>
      </div>
      <details className={s.table}>
        <summary>Show these numbers as a table</summary>
        <table>
          <thead>
            <tr><th scope="col">Checks a day</th>{SERIES.map((r) => <th key={r.key} scope="col">{r.label}</th>)}<th scope="col">Groups found (our model)</th></tr>
          </thead>
          <tbody>
            {TABLE_PER_DAY.filter((d) => d <= maxX).map((d) => {
              const row = SERIES.map(({ key }) => nearest(pts[key], d));
              return (
                <tr key={d}>
                  <td className="num">≈ {fmt(row[0].perDay)}</td>
                  {row.map((p, i) => <td key={i} className="num">{fmt(p.caught)}</td>)}
                  <td className="num">{fmt(row[0].rings)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
