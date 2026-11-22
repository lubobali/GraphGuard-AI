import s from "./Architecture.module.css";

// How data moves, left to right in two rows: offline (top), live (bottom). Plain boxes,
// one arrow style; the text says what each box is, not which brand it is.
const TOP = [
  ["Raw CSV", "5.08M transfers, simulator"],
  ["Lakehouse", "bronze → silver → gold · test window sealed"],
  ["Features", "as of each payment · graph + amounts"],
  ["XGBoost", "trained on the first window · MLflow"],
  ["Model store", "S3, pinned by SHA-256"],
];
const BOTTOM = [
  ["Kafka replay", "validation window, in order, with faults"],
  ["Consumer (k3s)", "live features in Redis · model + rules"],
  ["Postgres", "each decision once · late labels"],
  ["Demo copy", "read-only login · explanations · rings"],
  ["This site", "static pages · small read API"],
];
const W = 980, BW = 168, BH = 64, GAP = (W - 5 * BW) / 4, Y1 = 30, Y2 = 160;

function Row({ items, y }: { items: string[][]; y: number }) {
  return (
    <>
      {items.map(([title, sub], i) => {
        const x = i * (BW + GAP);
        return (
          <g key={title}>
            <rect x={x} y={y} width={BW} height={BH} rx={8} className={s.box} />
            <text x={x + 10} y={y + 24} className={s.title}>{title}</text>
            <foreignObject x={x + 10} y={y + 30} width={BW - 20} height={BH - 32}>
              <div className={s.sub}>{sub}</div>
            </foreignObject>
            {i < items.length - 1 && (
              <line x1={x + BW + 4} y1={y + BH / 2} x2={x + BW + GAP - 6} y2={y + BH / 2} className={s.arrow} markerEnd="url(#arr)" />
            )}
          </g>
        );
      })}
    </>
  );
}

export default function Architecture() {
  const modelX = 4 * (BW + GAP) + BW / 2;
  const consumerX = 1 * (BW + GAP) + BW / 2;
  return (
    <figure className={s.fig}>
      <svg viewBox={`-4 0 ${W + 8} 250`} className={s.svg} role="img"
        aria-label="Offline: raw CSV to lakehouse to features to XGBoost to the model store. Live: Kafka replay to the consumer on k3s, which loads the model, to Postgres, to the demo copy, to this site.">
        <defs>
          <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" className={s.head} />
          </marker>
        </defs>
        <text x={0} y={18} className={s.lane}>Offline — train and measure</text>
        <text x={0} y={Y2 - 12} className={s.lane}>Live — the replayed stream</text>
        <Row items={TOP} y={Y1} />
        <Row items={BOTTOM} y={Y2} />
        <path d={`M${modelX},${Y1 + BH + 4} C${modelX},${Y1 + BH + 40} ${consumerX},${Y2 - 50} ${consumerX},${Y2 - 22}`}
          className={s.load} markerEnd="url(#arr)" />
        <text x={(modelX + consumerX) / 2} y={Y1 + BH + 34} className={s.loadText} textAnchor="middle">model loaded at start, hash checked</text>
      </svg>
    </figure>
  );
}
