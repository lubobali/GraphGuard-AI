// S8b.1: the simulator's business types in plain words ("Sole Proprietorship #29351" ->
// "Small business #29351") and neutral bank names. Applied to whole API answers and the tour file, so names in
// headers, the money picture, reasons and AI facts all match. Types we cannot explain
// ("Country", "Direct") stay as the data has them.
import BANKS from "./bankNames.js";

const PLAIN = { "Sole Proprietorship": "Small business", Corporation: "Company", Individual: "Person" };
const RE = new RegExp(`\\b(${Object.keys(PLAIN).join("|")}) #(\\d+)`, "g");
// The simulator's US-style bank names, some of them real banks' names: never shown (S8b.1).
// Longest first, so "National Bank of Laramie" wins over "Bank of Laramie".
const esc = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const BANK_RE = new RegExp(`\\b(${Object.keys(BANKS).sort((a, b) => b.length - a.length).map(esc).join("|")})\\b`, "g");

export function plainNames(v) {
  if (typeof v === "string") return v.replace(RE, (_, t, n) => `${PLAIN[t]} #${n}`).replace(BANK_RE, (b) => BANKS[b]);
  if (Array.isArray(v)) return v.map(plainNames);
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plainNames(x)]));
  return v;
}
