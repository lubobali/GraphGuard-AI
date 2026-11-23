// Click-then-screenshot for UI checks (S7.14+). Runs INSIDE the throwaway Playwright image
// (scripts/ui/clickshot.sh); talks to Chromium over its DevTools port with Node's own
// WebSocket -- no packages. Steps: "click:<css>", "wait:<ms>", "shot:<name>", "eval:<js>".
//   node clickshot.mjs <url> <WxH> [dark] step...
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const [url, size, ...rest] = process.argv.slice(2);
const dark = rest[0] === "dark";
const steps = dark ? rest.slice(1) : rest;
const [w, h] = size.split("x").map(Number);
const chrome = spawn(process.env.CH, ["--headless=new", "--no-sandbox", "--disable-gpu",
  "--hide-scrollbars", "--remote-debugging-port=9333", `--window-size=${w},${h}`,
  ...(dark ? ["--blink-settings=preferredColorScheme=0"] : []), "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch("http://127.0.0.1:9333/json")).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0; const pending = new Map();
ws.addEventListener("message", (m) => { const d = JSON.parse(m.data); pending.get(d.id)?.(d); pending.delete(d.id); });
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
await send("Page.enable");
await send("Page.navigate", { url });
await sleep(4000);
for (const s of steps) {
  const [kind, ...arg] = s.split(":"); const a = arg.join(":");
  if (kind === "wait") await sleep(Number(a));
  if (kind === "click" || kind === "eval") {
    const expr = kind === "click"
      ? `(() => { const el = [...document.querySelectorAll(${JSON.stringify(a.split("|")[0])})].find((e) => ${JSON.stringify(a.split("|")[1] ?? "")} === "" || e.textContent.includes(${JSON.stringify(a.split("|")[1] ?? "")})); if (!el) return "missing"; el.scrollIntoView({block: "center"}); el.click(); return "ok"; })()`
      : a;
    const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
    console.log(s, "->", r.result?.result?.value);
    await sleep(600);
  }
  if (kind === "shot") {
    const r = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(`/out/${a}.png`, Buffer.from(r.result.data, "base64"));
    console.log("saved", a);
  }
}
ws.close(); chrome.kill();
