// Done-when 1: a report failing the allowlist gets a 400 naming only the
// failed rule, and nothing is stored. One case per refusal class.

import { test } from "node:test";
import assert from "node:assert/strict";
import { route, MAX_BODY_BYTES } from "../src/worker.js";
import { BASE, makeEnv, post } from "./support/fakes.mjs";
import { reportText, PYTHON_REPORTS } from "./support/reports.mjs";

const MARKER = "zz-marker-zz";

const VALID = reportText();
const swap = (from, to) => {
  assert.ok(VALID.includes(from), `fixture lacks ${from}`);
  return VALID.replace(from, to);
};

// [name, request factory, expected rule]
const CASES = [
  ["no content-type", () => post(VALID, {}), "content-type"],
  ["text/plain content-type", () => post(VALID, { "content-type": "text/plain" }), "content-type"],
  ["json-ish content-type", () => post(VALID, { "content-type": "application/jsonx" }), "content-type"],
  [
    "declared content-length over the cap",
    () => post(VALID, { "content-type": "application/json", "content-length": String(MAX_BODY_BYTES + 1) }),
    "too-large",
  ],
  [
    "streamed body over the cap with no content-length",
    () => {
      const big = reportText({}).replace("{", "{" + " ".repeat(MAX_BODY_BYTES));
      const stream = new Response(big).body;
      return new Request(`${BASE}/v1/report`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: stream,
        duplex: "half",
      });
    },
    "too-large",
  ],
  ["empty body", () => post(""), "json"],
  ["malformed JSON", () => post(VALID.slice(0, -1)), "json"],
  ["trailing garbage", () => post(VALID + "x"), "json"],
  ["NaN literal", () => post(swap('"iso_week":39', '"iso_week":NaN')), "json"],
  ["invalid UTF-8", () => post(new Uint8Array([0x7b, 0xff, 0x7d])), "json"],
  ["top-level array", () => post(`[${VALID}]`), "not-object"],
  ["top-level string", () => post(JSON.stringify(MARKER)), "not-object"],
  ["unknown key", () => post(reportText({ [MARKER]: 1 })), "unknown-key"],
  ["required key missing", () => post(reportText({}, ["iso_week"])), "missing-key"],
  ["enum: 0 is not false", () => post(swap('"dev":false', '"dev":0')), "enum"],
  ["enum: a string is not a boolean", () => post(swap('"dev":false', '"dev":"false"')), "enum"],
  ["enum: null", () => post(swap('"dev":false', '"dev":null')), "enum"],
  ["band not in the list", () => post(swap('"sessions":"10-49"', `"sessions":"${MARKER}"`)), "band"],
  ["band as a number", () => post(swap('"sessions":"10-49"', '"sessions":10')), "band"],
  ["integer field given a string", () => post(swap('"iso_week":39', '"iso_week":"39"')), "not-number"],
  ["integer field given true", () => post(swap('"schema":1', '"schema":true')), "not-number"],
  ["number field given false", () => post(reportText({ blocking_per_review: false })), "not-number"],
  ["number field given an object", () => post(reportText({ blocking_per_review: { v: 1 } })), "not-number"],
  ["non-finite number", () => post(swap('"iso_week":39', '"iso_week":1e400')), "not-number"],
  ["integer field given 1.0", () => post(swap('"schema":1', '"schema":1.0')), "not-integer"],
  ["integer field given 1e0", () => post(swap('"schema":1', '"schema":1e0')), "not-integer"],
  ["integer field given 39.5", () => post(swap('"iso_week":39', '"iso_week":39.5')), "not-integer"],
  ["below min", () => post(swap('"iso_week":39', '"iso_week":0')), "range"],
  ["above max", () => post(swap('"iso_year":2026', '"iso_year":2101')), "range"],
  ["schema version 2", () => post(swap('"schema":1', '"schema":2')), "range"],
  ["number above max", () => post(reportText({ red_test_run_share: 1.05 })), "range"],
  ["negative number", () => post(reportText({ blocking_per_review: -0.1 })), "range"],
  ["off step", () => post(reportText({ red_test_run_share: 0.33 })), "step"],
  ["off step by more than 1e-6", () => post(reportText({ rounds_per_scope_median: 2.50001 })), "step"],
];

for (const [name, make, rule] of CASES) {
  test(`refuses: ${name} -> ${rule}`, async () => {
    const env = makeEnv();
    const response = await route(make(), env);
    assert.equal(response.status, 400);
    const body = await response.text();
    assert.deepEqual(JSON.parse(body), { refused: rule });
    assert.ok(!body.includes(MARKER), "a refusal must not echo input");
    assert.deepEqual(env.BUNDLES.keys(), [], "a refused report must not be stored");
    assert.deepEqual(env.BUNDLES.puts, [], "a refused report must not reach storage at all");
  });
}

test("accepts every report the client produced, with 204 and an empty body", async () => {
  for (const { bytes } of PYTHON_REPORTS) {
    const env = makeEnv();
    const response = await route(post(bytes), env);
    assert.equal(response.status, 204);
    assert.equal(await response.text(), "");
  }
});

test("storage that is unavailable gives a bare 503, never the error", async () => {
  const env = makeEnv();
  env.BUNDLES.fail = () => {
    throw new Error(`storage down ${MARKER}`);
  };
  const response = await route(post(VALID), env);
  assert.equal(response.status, 503);
  assert.equal(await response.text(), "");
});

test("accepts content-type with parameters, any case", async () => {
  const response = await route(post(VALID, { "content-type": "Application/JSON; charset=utf-8" }), makeEnv());
  assert.equal(response.status, 204);
});

test("accepts a value within 1e-6 of its step", async () => {
  const response = await route(post(reportText({ rounds_per_scope_median: 2.5000000001 })), makeEnv());
  assert.equal(response.status, 204);
});

test("accepts a whole number written as a float in a number field", async () => {
  const response = await route(post(VALID.replace("}", ',"blocking_per_review":3.0}')), makeEnv());
  assert.equal(response.status, 204);
});

test("accepts a body exactly at the cap", async () => {
  const padded = VALID.replace("{", "{" + " ".repeat(MAX_BODY_BYTES - VALID.length));
  assert.equal(new TextEncoder().encode(padded).length, MAX_BODY_BYTES);
  const response = await route(post(padded), makeEnv());
  assert.equal(response.status, 204);
});

test("refuses a body one byte over the cap", async () => {
  const padded = VALID.replace("{", "{" + " ".repeat(MAX_BODY_BYTES - VALID.length + 1));
  const response = await route(post(padded), makeEnv());
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { refused: "too-large" });
});
