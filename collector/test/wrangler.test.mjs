// Done-when 4: wrangler.toml turns observability off and ships nothing that
// would export a trace. Parses the file and pins each key, so loosening one
// fails the suite. Also pins the bindings the worker reads.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import * as workerModule from "../src/worker.js";
import { parseToml } from "./support/fakes.mjs";

const here = (p) => new URL(p, import.meta.url);
const TEXT = readFileSync(here("../wrangler.toml"), "utf8");
const CONFIG = parseToml(TEXT);

test("observability is off at every level Cloudflare documents", () => {
  const o = CONFIG.observability;
  assert.equal(o.enabled, false);
  assert.equal(o.head_sampling_rate, 0);
  assert.equal(o.logs.enabled, false);
  assert.equal(o.logs.invocation_logs, false);
  assert.equal(o.logs.head_sampling_rate, 0);
  assert.equal(o.traces.enabled, false);
  assert.equal(o.traces.head_sampling_rate, 0);
  assert.equal(o.issues.enabled, false);
});

test("no Logpush, no tail consumers, no other telemetry export", () => {
  assert.equal(CONFIG.logpush, false);
  for (const key of ["tail_consumers", "streaming_tail_consumers", "analytics_engine_datasets", "upload_source_maps"]) {
    assert.equal(CONFIG[key], undefined, key);
  }
  assert.doesNotMatch(TEXT, /^\s*(tail_consumers|streaming_tail_consumers|analytics_engine_datasets)\b/m);
});

test("the cron is one daily trigger", () => {
  assert.deepEqual(CONFIG.triggers.crons, ["0 0 * * *"]);
});

test("the one binding is the R2 bucket the worker reads", () => {
  assert.equal(CONFIG.main, "src/worker.js");
  assert.ok(existsSync(here("../" + CONFIG.main)));
  assert.deepEqual(
    CONFIG.r2_buckets.map((b) => b.binding),
    ["BUNDLES"],
  );
  assert.equal(typeof workerModule.default.fetch, "function");
  assert.equal(typeof workerModule.default.scheduled, "function");
});

test("no Durable Object: no binding, no class lifecycle, no other storage binding", () => {
  for (const key of ["durable_objects", "exports", "migrations", "kv_namespaces", "d1_databases", "queues", "analytics_engine_datasets"]) {
    assert.equal(CONFIG[key], undefined, key);
  }
  const classes = Object.entries(workerModule).filter(([, v]) => typeof v === "function" && /^class\b/.test(String(v)));
  assert.deepEqual(classes.map(([k]) => k), ["JsonNumber"], "the only exported class is the parser's number type");
});

test("owner values are placeholders, and no route is chosen for the owner", () => {
  assert.match(CONFIG.r2_buckets[0].bucket_name, /^<[A-Z0-9_]+>$/);
  assert.equal(CONFIG.account_id, undefined);
  assert.equal(CONFIG.route, undefined);
  assert.equal(CONFIG.routes, undefined);
});
