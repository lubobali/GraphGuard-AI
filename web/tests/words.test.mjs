// S7.12: phrases that misled a first-time reader (Lubo, 2026-11-23) never come back.
// Scans the page sources, not the built HTML: most text renders in the browser.
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const BANNED = [
  "Random picks",          // means nothing to a newcomer; the line moved to the table
  "Rules only",            // say "fixed rules (old way)"
  "alerts worked",         // the team checks; the model ranks
  "A team of",             // the old sentence that said the team "catches"
  "How many alerts can your team work",
];
const WEB = join(dirname(fileURLToPath(import.meta.url)), "..");
const ROOTS = ["pages", "components", "lib"].map((d) => join(WEB, d));

function files(dir) {
  return readdirSync(dir).flatMap((f) => {
    const p = join(dir, f);
    return statSync(p).isDirectory() ? files(p) : /\.(tsx?|jsx?|json)$/.test(f) ? [p] : [];
  });
}

test("no page says the words that misled a first-time reader", () => {
  const hits = [];
  for (const f of ROOTS.flatMap(files)) {
    const text = readFileSync(f, "utf8");
    for (const w of BANNED) if (text.includes(w)) hits.push(`${f}: "${w}"`);
  }
  assert.deepEqual(hits, []);
});
