// Post-build check of the static export (S7.7). Fails the build if:
//  - any HTML carries an executable inline <script> (the API's CSP is script-src 'self');
//  - any HTML/CSS loads something from another host (the page must be self-contained);
//  - any file holds a secret-looking string.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const SECRET = [/AKIA[0-9A-Z]{16}/, /-----BEGIN [A-Z ]*PRIVATE KEY-----/, /_PASSWORD\s*=/,
  /\bsk-[A-Za-z0-9]{20,}/, /postgres(ql)?:\/\/[^\s"']+:[^\s"']+@/];

export function inlineScripts(html) {
  const out = [];
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)) {
    const attrs = m[1];
    const isData = /type=["']application\/(ld\+)?json["']/i.test(attrs);
    if (!/\bsrc=/i.test(attrs) && !isData && m[2].trim()) out.push(m[2].slice(0, 80));
  }
  return out;
}

export function externalLoads(text) {
  const re = /(?:src|href)=["'](?:https?:)?\/\/[^"']+|url\(\s*["']?(?:https?:)?\/\/[^)]+/gi;
  return [...text.matchAll(re)].map((m) => m[0]);
}

export function secrets(text) {
  return SECRET.filter((re) => re.test(text)).map(String);
}

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* files(p);
    else yield p;
  }
}

export function check(dir) {
  const problems = [];
  for (const f of files(dir)) {
    if (!/\.(html|css|js|json|txt)$/.test(f)) continue;
    const text = readFileSync(f, "utf8");
    if (f.endsWith(".html")) {
      for (const s of inlineScripts(text)) problems.push(`${f}: inline script: ${s}`);
    }
    if (/\.(html|css)$/.test(f)) {
      for (const e of externalLoads(text)) problems.push(`${f}: loads from another host: ${e}`);
    }
    for (const s of secrets(text)) problems.push(`${f}: secret-looking string ${s}`);
  }
  return problems;
}

if (process.argv[1] && process.argv[1].endsWith("check-export.mjs")) {
  const problems = check(process.argv[2] || "out");
  if (problems.length) {
    console.error(problems.join("\n"));
    process.exit(1);
  }
  console.log("export check: no inline scripts, no external loads, no secrets");
}
