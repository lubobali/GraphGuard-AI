import assert from "node:assert/strict";
import test from "node:test";
import { externalLoads, inlineScripts, secrets } from "../scripts/check-export.mjs";

test("inline executable scripts are found; data scripts and src scripts are not", () => {
  assert.equal(inlineScripts('<script>alert(1)</script>').length, 1);
  assert.equal(inlineScripts('<script src="/_next/a.js"></script>').length, 0);
  assert.equal(inlineScripts('<script id="__NEXT_DATA__" type="application/json">{}</script>').length, 0);
});

test("loads from another host are found", () => {
  assert.equal(externalLoads('<link href="https://fonts.example/x.css">').length, 1);
  assert.equal(externalLoads('a{background:url(//cdn.example/x.png)}').length, 1);
  assert.equal(externalLoads('<link href="/_next/static/x.css">').length, 0);
  assert.equal(externalLoads('<script src="https://cdn.example/x.js"></script>').length, 1);
  assert.equal(externalLoads('<a href="https://github.com/x/y">repo</a>').length, 0); // a link
});

test("secret-looking strings are found", () => {
  assert.equal(secrets("DEMO_READER_PASSWORD=abc").length, 1);
  assert.equal(secrets("postgresql://u:p@h/db").length, 1);
  assert.equal(secrets("nothing here").length, 0);
});
