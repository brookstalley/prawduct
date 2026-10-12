// Done-when 3: the worker never logs and reads no request header beyond
// content-type and content-length. Greps the source, so a new log line or
// header read fails here before it can ship. Also pins the worker's embedded
// allowlist to its one home, the plugin's plugin/lib/contribution_schema.json:
// the worker imports nothing, so it carries the allowlist as an object, and
// this test is what keeps that object equal to the file.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { SCHEMA } from "../src/worker.js";

const here = (p) => new URL(p, import.meta.url);
const SOURCE = readFileSync(here("../src/worker.js"), "utf8");

test("no console call anywhere in the worker", () => {
  assert.equal(SOURCE.match(/\bconsole\s*[.[]/g), null);
});

test("the only headers read are content-type and content-length", () => {
  const reads = [...SOURCE.matchAll(/\.headers\b(.{0,40})/g)].map((m) => m[1]);
  assert.ok(reads.length > 0, "the grep must see the header reads it is policing");
  for (const tail of reads) {
    assert.match(tail, /^\.get\("content-(type|length)"\)/, `unexpected header access: .headers${tail}`);
  }
});

test("no other way to reach the sender: no cf object, no address headers, no header iteration", () => {
  const forbidden = [
    /\.cf\b/,
    /\[\s*["']cf["']\s*\]/,
    /connecting-ip/i,
    /forwarded/i,
    /x-real-ip/i,
    /true-client-ip/i,
    /user-agent/i,
    /\bheaders\s*\.\s*(entries|keys|values|forEach|has)\b/,
    /\.\.\.\s*request\.headers/,
    /Object\.fromEntries\(\s*request/,
  ];
  for (const re of forbidden) assert.doesNotMatch(SOURCE, re);
});

test("the worker imports nothing", () => {
  assert.doesNotMatch(SOURCE, /^\s*import\b/m);
  assert.doesNotMatch(SOURCE, /\bimport\s*\(/);
  assert.doesNotMatch(SOURCE, /\brequire\s*\(/);
});

test("nothing in the worker reads the clock", () => {
  // The only clock-shaped call is flushDay's, on the cron's scheduled time.
  const clocks = [...SOURCE.matchAll(/Date\.now\(|new Date\(([^)]*)\)|performance\.now/g)].map((m) => m[0]);
  assert.deepEqual(clocks, ["new Date(scheduledTime)"]);
});

test("the embedded allowlist equals the plugin's allowlist", () => {
  const file = JSON.parse(readFileSync(here("../../plugin/lib/contribution_schema.json"), "utf8"));
  assert.deepEqual(SCHEMA, file);
});
