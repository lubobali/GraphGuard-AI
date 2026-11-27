// S8b.1: business types in plain words, everywhere a name or a sentence about one is shown.
import { test } from "node:test";
import assert from "node:assert/strict";
import { plainNames } from "../lib/names.js";

test("each business type the data holds reads plainly; the number stays", () => {
  assert.equal(plainNames("Sole Proprietorship #29351"), "Small business #29351");
  assert.equal(plainNames("Corporation #12611"), "Company #12611");
  assert.equal(plainNames("Individual #7"), "Person #7");
  assert.equal(plainNames("Partnership #39337"), "Partnership #39337"); // already plain
  // the simulator's own types we cannot explain stay as they are, never guessed
  assert.equal(plainNames("Country #12"), "Country #12");
  assert.equal(plainNames("Direct #3"), "Direct #3");
});

test("inside a sentence (a reason, an AI fact), and only before an account number", () => {
  assert.equal(plainNames("Sole Proprietorship #1 paid Corporation #2 9,500.00 Euro."),
    "Small business #1 paid Company #2 9,500.00 Euro.");
  assert.equal(plainNames("a Corporation is a company"), "a Corporation is a company");
});

test("whole API answers and the tour file: every string, nothing else changed", () => {
  const data = { n: 3, ok: true, none: null, name: "Corporation #5",
    list: [{ text: "Individual #9 sent it", cites: [10] }] };
  assert.deepEqual(plainNames(data), { n: 3, ok: true, none: null, name: "Company #5",
    list: [{ text: "Person #9 sent it", cites: [10] }] });
  assert.equal(data.name, "Corporation #5"); // the input is not changed
});

import BANKS from "../lib/bankNames.js";

test("no named bank is ever shown: each becomes its neutral name, longest name first", () => {
  assert.equal(plainNames("Bank of the West"), BANKS["Bank of the West"]);
  assert.match(plainNames("Paid at National Bank of Laramie today"), /^Paid at USA Bank #\d+ today$/);
  assert.equal(plainNames("National Bank of Laramie"), BANKS["National Bank of Laramie"]);
  assert.notEqual(BANKS["National Bank of Laramie"], BANKS["Bank of Laramie"]);
  assert.equal(plainNames("Russia Bank #21"), "Russia Bank #21");
  for (const name of Object.keys(BANKS)) assert.equal(plainNames(name), BANKS[name], name);
});
