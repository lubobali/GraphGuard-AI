// Pure helpers for the investigator screens (S7.7). Plain JS so Node's test runner reads
// them directly; the API (graphguard.demo.queries) uses the same window and conversion.

/** The validation window: 2022-09-06 13:34 -> 2022-09-08 16:08 = 50.5667 h. */
export const WINDOW_DAYS = 50.5667 / 24;
export const MAX_K = 5000;
/** Industry illustration: an analyst works ~20 alerts a day (research notes, S7 research). */
export const ALERTS_PER_ANALYST = 20;

/** Alerts a day -> alerts over the window (k), the API's k_for(). */
export function kFor(perDay) {
  return Math.max(1, Math.min(MAX_K, Math.round(perDay * WINDOW_DAYS)));
}

/** k -> alerts a day. */
export function perDayFor(k) {
  return k / WINDOW_DAYS;
}

export function fmt(n) {
  return Math.round(n).toLocaleString("en-US");
}

export function plural(n, one, many) {
  return `${fmt(n)} ${Math.round(n) === 1 ? one : many}`;
}

export function teamSize(perDay) {
  return Math.max(1, Math.round(perDay / ALERTS_PER_ANALYST));
}

/**
 * The slider's plain sentence. `r` = the API's /capacity rankings.
 * Counts, never percentages or money (ADR 0008).
 */
export function capacitySentence(perDay, r) {
  const s = r.system;
  const total = s.caught + s.missed;
  const team = teamSize(perDay);
  const people = team === 1 ? "one investigator" : `about ${team} investigators`;
  return {
    lead: `A team of ${people} working ${fmt(perDay)} alerts a day catches ` +
      `${fmt(s.caught)} of ${fmt(total)} laundering transactions and ` +
      `${fmt(s.rings_caught)} of ${plural(s.rings_total, "ring", "rings")}.`,
    missed: `It misses ${fmt(s.missed)}.`,
    rules: `Simple rules alone, same workload: ${plural(r.rules.caught, "transaction", "transactions")}` +
      ` and ${plural(r.rules.rings_caught, "ring", "rings")}.`,
  };
}

/** "Top 0.01%" from a percentile (share ranked below). */
export function topShare(percentile) {
  const top = 100 - percentile;
  if (top < 0.01) return "Top 0.01%";
  if (top < 1) return `Top ${top.toFixed(2)}%`;
  return `Top ${top.toFixed(1)}%`;
}

/** Linear scale factory for the hand-drawn chart. */
export function scale(d0, d1, r0, r1) {
  const m = (r1 - r0) / (d1 - d0 || 1);
  const f = (v) => r0 + (v - d0) * m;
  f.invert = (p) => d0 + (p - r0) / m;
  return f;
}

/** "Nice" axis ticks: ~count steps of 1/2/5 x 10^n. */
export function ticks(max, count = 5) {
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((s) => s * mag).find((s) => s >= raw);
  const end = Math.ceil(max / step - 1e-9) * step; // the axis covers the top of the data
  const out = [];
  for (let v = 0; v <= end + 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

/** Nearest curve point to an x (alerts a day) - the crosshair's snap. */
export function nearest(points, perDay) {
  let best = points[0];
  for (const p of points) if (Math.abs(p.perDay - perDay) < Math.abs(best.perDay - perDay)) best = p;
  return best;
}
