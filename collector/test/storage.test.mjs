// Done-when 2: a stored report persists as its canonical bytes only, in one R2
// object with no metadata, under a key that encodes neither sender nor time. Also the canonical-bytes parity
// with Python's json.dumps(report, sort_keys=True, separators=(",", ":")).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { admit, route, SCHEMA, JsonNumber, canonicalize, PENDING_PREFIX } from "../src/worker.js";
import { BASE, makeEnv, post } from "./support/fakes.mjs";
import { PYTHON_REPORTS } from "./support/reports.mjs";

const SENDER = {
  "content-type": "application/json",
  "cf-connecting-ip": "203.0.113.77",
  "x-forwarded-for": "198.51.100.23",
  "x-real-ip": "192.0.2.99",
  "user-agent": "identifying-agent/9.9",
  "cookie": "session=identifying-cookie",
  "x-contributor": "identifying-header-value",
};
const LEAKS = ["203.0.113.77", "198.51.100.23", "192.0.2.99", "identifying"];

function senderRequest(body) {
  const request = new Request(`${BASE}/v1/report`, { method: "POST", headers: SENDER, body });
  // What the Workers runtime attaches about the connection.
  Object.defineProperty(request, "cf", { value: { asn: 64496, country: "ZZ", city: "identifying-city" } });
  return request;
}

test("parity: the canonical bytes equal Python's for reports the client built", () => {
  for (const { report, bytes } of PYTHON_REPORTS) {
    // From Python's own bytes, and from the same report spelled differently
    // (insertion order, whitespace).
    assert.deepEqual(admit(bytes), { ok: true, canonical: bytes });
    const respelled = JSON.stringify(report, null, 2);
    assert.notEqual(respelled, bytes);
    assert.deepEqual(admit(respelled), { ok: true, canonical: bytes });
  }
});

test("parity: every value to_step can emit formats as Python writes it", () => {
  const fixture = JSON.parse(readFileSync(new URL("./fixtures/python-step-values.json", import.meta.url), "utf8"));
  let checked = 0;
  for (const [field, texts] of Object.entries(fixture.values)) {
    const spec = SCHEMA.fields[field];
    assert.ok(spec, `fixture names unknown field ${field}`);
    for (const text of texts) {
      const isInt = !/[.eE]/.test(text);
      const report = new Map([[field, new JsonNumber(Number(text), isInt)]]);
      assert.equal(canonicalize(report), `{"${field}":${text}}`);
      checked++;
    }
  }
  assert.ok(checked > 7000, "the fixture should cover every step value");
});

test("parity: the collector accepts exactly what Python's validate accepts, stored in client form", () => {
  const fixture = JSON.parse(readFileSync(new URL("./fixtures/python-verdicts.json", import.meta.url), "utf8"));
  assert.ok(fixture.cases.some((c) => c.accepted) && fixture.cases.some((c) => !c.accepted));
  for (const { body, accepted, stored } of fixture.cases) {
    const verdict = admit(body);
    assert.equal(verdict.ok, accepted, body);
    if (accepted) assert.equal(verdict.canonical, stored, body);
  }
});

test("canonical form snaps a within-tolerance value to its grid spelling", () => {
  const base = PYTHON_REPORTS[0].bytes.slice(0, -1);
  assert.match(admit(base + ',"red_test_run_share":0.35000000001}').canonical, /"red_test_run_share":0\.35[,}]/);
  assert.match(admit(base + ',"blocking_per_review":3.0}').canonical, /"blocking_per_review":3[,}]/);
  assert.match(admit(base + ',"blocking_per_review":1e-8}').canonical, /"blocking_per_review":0[,}]/);
  assert.match(admit(base + ',"blocking_per_review":-0}').canonical, /"blocking_per_review":0[,}]/);
});

test("a repeated key keeps its last value, as Python's json.loads does", () => {
  const text = PYTHON_REPORTS[0].bytes.replace('"iso_week":39', '"iso_week":12,"iso_week":39');
  assert.deepEqual(admit(text), { ok: true, canonical: PYTHON_REPORTS[0].bytes });
});

const KEY_RE = /^pending\/([0-9a-f]{64})-([0-9a-f]{32})$/;

async function sha256(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

test("a stored report is one pending object: canonical bytes, no metadata, a hash-and-random key", async () => {
  const env = makeEnv();
  const { report, bytes } = PYTHON_REPORTS[1];
  const response = await route(senderRequest(JSON.stringify(report, null, 1)), env);
  assert.equal(response.status, 204);

  const [entry, ...rest] = env.BUNDLES.entries();
  assert.equal(rest.length, 0, "one report, one object, nothing else written");
  assert.equal(entry.text, bytes);
  assert.deepEqual(entry.customMetadata, {});
  assert.deepEqual(entry.httpMetadata, {});
  assert.deepEqual(entry.options, [], "put was called with no options at all");
  const m = KEY_RE.exec(entry.key);
  assert.ok(m, entry.key);
  assert.equal(m[1], await sha256(bytes));
});

test("nothing about the sender or the time reaches the object's key, body or metadata", async () => {
  const env = makeEnv();
  const before = Date.now();
  await route(senderRequest(PYTHON_REPORTS[0].bytes), env);
  const [entry] = env.BUNDLES.entries();
  const visible = [entry.key, entry.text, JSON.stringify(entry.customMetadata), JSON.stringify(entry.httpMetadata)].join("\n");
  for (const leak of LEAKS) assert.ok(!visible.includes(leak), `storage holds ${leak}`);
  // No clock reading: neither epoch milliseconds or seconds nor an ISO time.
  const outsideReport = visible.split(PYTHON_REPORTS[0].bytes).join("");
  for (const t of [before, Date.now()]) {
    assert.ok(!outsideReport.includes(String(t).slice(0, 8)), "epoch milliseconds in storage");
    assert.ok(!outsideReport.includes(String(Math.floor(t / 1000)).slice(0, 7)), "epoch seconds in storage");
  }
  assert.doesNotMatch(outsideReport, /20[0-9]{2}-[01][0-9]-[0-3][0-9]|T[0-2][0-9]:[0-5][0-9]/);
});

test("identical reports from two contributors are two objects, so both are counted", async () => {
  const env = makeEnv();
  await route(post(PYTHON_REPORTS[0].bytes), env);
  await route(post(PYTHON_REPORTS[0].bytes), env);
  await route(post(PYTHON_REPORTS[2].bytes), env);
  const keys = env.BUNDLES.keys(PENDING_PREFIX);
  assert.equal(keys.length, 3);
  const hashes = keys.map((k) => KEY_RE.exec(k)[1]);
  const same = await sha256(PYTHON_REPORTS[0].bytes);
  assert.equal(hashes.filter((h) => h === same).length, 2);
  assert.equal(new Set(keys).size, 3);
});

test("the random suffix varies, so key order is not arrival order", async () => {
  const env = makeEnv();
  for (let k = 0; k < 40; k++) await route(post(PYTHON_REPORTS[0].bytes), env);
  const arrival = env.BUNDLES.puts;
  const lexical = [...arrival].sort();
  assert.notDeepEqual(arrival, lexical);
  assert.equal(new Set(arrival.map((k) => KEY_RE.exec(k)[2])).size, 40);
});
