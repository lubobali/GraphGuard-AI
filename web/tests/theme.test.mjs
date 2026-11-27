// S8b.4b: dark by default, a remembered switch.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { KEY, label, nextTheme, readTheme, saveTheme } from "../lib/theme.js";

const store = (v) => ({ getItem: () => v, setItem(k, x) { this.saved = [k, x]; } });

test("dark unless the visitor chose light", () => {
  assert.equal(readTheme(store(null)), "dark");
  assert.equal(readTheme(store("light")), "light");
  assert.equal(readTheme(store("dark")), "dark");
  assert.equal(readTheme(store("purple")), "dark");
  assert.equal(readTheme(null), "dark");
});

test("blocked storage (private window) just means dark, never a crash", () => {
  const broken = { getItem() { throw new Error("denied"); }, setItem() { throw new Error("denied"); } };
  assert.equal(readTheme(broken), "dark");
  assert.doesNotThrow(() => saveTheme(broken, "light"));
});

test("the switch flips, saves, and says what it will do", () => {
  assert.equal(nextTheme("dark"), "light");
  assert.equal(nextTheme("light"), "dark");
  const s = store(null);
  saveTheme(s, "light");
  assert.deepEqual(s.saved, [KEY, "light"]);
  assert.equal(label("dark"), "Switch to light mode");
  assert.equal(label("light"), "Switch to dark mode");
});

test("the early script is a file of its own (the CSP allows no inline script)", () => {
  const src = readFileSync(new URL("../public/theme.js", import.meta.url), "utf8");
  assert.match(src, new RegExp(KEY));
  assert.match(src, /dataset\.theme/);
  const doc = readFileSync(new URL("../pages/_document.tsx", import.meta.url), "utf8");
  assert.match(doc, /<script src="\/theme\.js"/);
});

test("the styles are dark first; light only by choice, not by the device", () => {
  const css = readFileSync(new URL("../styles/globals.css", import.meta.url), "utf8");
  const root = css.slice(css.indexOf(":root {"), css.indexOf("}", css.indexOf(":root {")));
  assert.match(root, /color-scheme: dark/);
  assert.match(css, /:root\[data-theme="light"\]/);
  assert.doesNotMatch(css, /prefers-color-scheme/);
});

test("the built site carries theme.js when it has been exported", { skip: !existsSync(new URL("../out", import.meta.url)) }, () => {
  assert.ok(existsSync(new URL("../out/theme.js", import.meta.url)));
});
