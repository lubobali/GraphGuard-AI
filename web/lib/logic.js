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

/** "1 person" / "about 5 people" for a daily workload. */
export function peopleFor(perDay) {
  const n = teamSize(perDay);
  return n === 1 ? "1 person" : `about ${fmt(n)} people`;
}

/**
 * The flow of counts (S7.12): of the `checked` payments at the top of the list, how many
 * are laundering (found) and how many are not (false alarms); how many laundering payments
 * sit lower and are never checked (missed). `system`/`rules` = the API's /capacity rankings.
 * Counts, never percentages or money (ADR 0008). The model ranks; people confirm.
 */
export function flowCounts(checked, system, rules) {
  return {
    checked,
    found: system.caught,
    falseAlarms: checked - system.caught,
    missed: system.missed,
    total: system.caught + system.missed,
    rulesFound: rules.caught,
    groupsFound: system.rings_caught,
    groupsTotal: system.rings_total,
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

/** Direct labels at line ends: keep them at least `gap` px apart, inside [lo, hi], in the
 *  same top-to-bottom order as their lines (screenshot 2026-11-22: two labels overlapped). */
export function spreadLabels(ys, gap, lo, hi) {
  const order = ys.map((y, i) => i).sort((a, b) => ys[a] - ys[b]);
  const out = [...ys];
  let prev = lo - gap;
  for (const i of order) { out[i] = Math.max(ys[i], prev + gap); prev = out[i]; }
  let next = hi + gap; // then pull back from the bottom, moving only the labels that must move
  for (const i of [...order].reverse()) { out[i] = Math.min(out[i], next - gap); next = out[i]; }
  return out;
}
