// The demo has no logins (S7.15): each browser gets a random visitor id, so "your cases"
// are yours and one visitor never locks an alert for another. Kept in localStorage when
// it works; a blocked storage gives an id for this page view only.

let cached = null;
const KEY = "gg-visitor";

export function newVisitorId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  const b = Array.from({ length: 16 }, () => Math.floor(Math.random() * 256));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = b.map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

export function visitorId() {
  if (cached) return cached;
  try {
    cached = localStorage.getItem(KEY);
    if (!cached) { cached = newVisitorId(); localStorage.setItem(KEY, cached); }
  } catch {
    cached = cached || newVisitorId();
  }
  return cached;
}
