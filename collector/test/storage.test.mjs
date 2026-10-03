// Done-when 2: a stored report persists as its canonical bytes only, with no
// address, header or time anywhere in storage. Also the canonical-bytes parity
// with Python's json.dumps(report, sort_keys=True, separators=(",", ":")).

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { admit, route, SCHEMA, JsonNumber, canonicalize } from "../src/worker.js";
import { BASE, makeEnv, post, storageOf } from "./support/fakes.mjs";
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

test("a stored report is its canonical bytes and a count, and nothing about the sender", async () => {
  const env = makeEnv();
  const { report, bytes } = PYTHON_REPORTS[1];
  const response = await route(senderRequest(JSON.stringify(report, null, 1)), env);
  assert.equal(response.status, 204);

  const storage = storageOf(env);
  assert.deepEqual(storage.rows("pending"), [{ report: bytes, n: 1 }]);
  assert.deepEqual(storage.rows("claimed"), []);
  assert.deepEqual(storage.rows("claim"), []);

  const everything = storage.dump();
  for (const leak of LEAKS) assert.ok(!everything.includes(leak), `storage holds ${leak}`);
  // No time: no column for one, no current year or epoch-like number anywhere
  // except inside the report's own bytes.
  const outsideReport = everything.split(bytes).join("");
  assert.ok(!/\b(time|date|ts|ip|addr|header|agent|seen|arriv)/i.test(outsideReport), outsideReport);
  assert.ok(!/\b20[0-9]{2}\b|\b1[0-9]{9,12}\b/.test(outsideReport), outsideReport);
});

test("only the canonical bytes cross to the Durable Object: no sender header, no cf object", async () => {
  const env = makeEnv();
  await route(senderRequest(PYTHON_REPORTS[0].bytes), env);
  assert.equal(env.PENDING.received.length, 1);
  const forwarded = env.PENDING.received[0];
  for (const [name] of forwarded.headers) {
    assert.ok(!(name in SENDER) || name === "content-type", `header ${name} crossed`);
    for (const leak of LEAKS) assert.ok(!forwarded.headers.get(name).includes(leak));
  }
  assert.equal(forwarded.cf, undefined);
  assert.equal(await forwarded.text(), PYTHON_REPORTS[0].bytes);
});

test("identical reports are one row with a count, so none is lost", async () => {
  const env = makeEnv();
  for (let k = 0; k < 3; k++) await route(post(PYTHON_REPORTS[0].bytes), env);
  await route(post(PYTHON_REPORTS[2].bytes), env);
  const rows = storageOf(env).rows("pending");
  assert.deepEqual(
    rows.sort((a, b) => (a.report < b.report ? -1 : 1)),
    [
      { report: PYTHON_REPORTS[2].bytes, n: 1 },
      { report: PYTHON_REPORTS[0].bytes, n: 3 },
    ].sort((a, b) => (a.report < b.report ? -1 : 1)),
  );
});

test("pending tables keep no insertion order: they are WITHOUT ROWID", () => {
  const env = makeEnv();
  const ddl = storageOf(env).dump();
  for (const table of ["pending", "claimed", "claim"]) {
    assert.match(ddl, new RegExp(`CREATE TABLE ${table} \\([^)]*\\) WITHOUT ROWID`));
  }
});

test("the Durable Object refuses bytes that are not already canonical", async () => {
  const env = makeEnv();
  const stub = env.PENDING.getByName("pending");
  const spaced = JSON.stringify(PYTHON_REPORTS[0].report, null, 1);
  const response = await stub.fetch(new Request("https://pending.internal/store", { method: "POST", body: spaced }));
  assert.equal(response.status, 400);
  assert.deepEqual(storageOf(env).rows("pending"), []);
});
