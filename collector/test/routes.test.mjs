// Done-when 6: GET serves the index and the bundles; every other method or
// path is 405 or 404.

import { test } from "node:test";
import assert from "node:assert/strict";
import worker, { route, bundleKey, INDEX_KEY } from "../src/worker.js";
import { BASE, makeEnv, post } from "./support/fakes.mjs";
import { PYTHON_REPORTS } from "./support/reports.mjs";

async function flushedEnv() {
  const env = makeEnv();
  for (const { bytes } of PYTHON_REPORTS) await route(post(bytes), env);
  await worker.scheduled({ scheduledTime: Date.UTC(2026, 9, 3) }, env, {});
  return env;
}

const req = (method, path) => new Request(BASE + path, { method });

test("GET /bundles/index.json serves the index as JSON", async () => {
  const env = await flushedEnv();
  const response = await worker.fetch(req("GET", "/bundles/index.json"), env);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "application/json");
  assert.deepEqual(await response.json(), { days: ["2026-10-03"] });
});

test("GET /bundles/<day>.jsonl serves that day's bundle", async () => {
  const env = await flushedEnv();
  const response = await worker.fetch(req("GET", "/bundles/2026-10-03.jsonl"), env);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "application/x-ndjson");
  assert.equal(await response.text(), env.BUNDLES.text(bundleKey("2026-10-03")));
});

test("GET of a day with no bundle, or before any flush, is 404", async () => {
  const env = await flushedEnv();
  assert.equal((await worker.fetch(req("GET", "/bundles/2026-10-04.jsonl"), env)).status, 404);
  assert.equal((await worker.fetch(req("GET", "/bundles/index.json"), makeEnv())).status, 404);
});

test("other methods on the known paths are 405 with Allow", async () => {
  const env = await flushedEnv();
  const cases = [
    ["GET", "/v1/report", "POST"],
    ["PUT", "/v1/report", "POST"],
    ["DELETE", "/v1/report", "POST"],
    ["POST", "/bundles/index.json", "GET"],
    ["PUT", "/bundles/2026-10-03.jsonl", "GET"],
    ["DELETE", "/bundles/2026-10-03.jsonl", "GET"],
    ["HEAD", "/bundles/index.json", "GET"],
  ];
  for (const [method, path, allow] of cases) {
    const response = await worker.fetch(req(method, path), env);
    assert.equal(response.status, 405, `${method} ${path}`);
    assert.equal(response.headers.get("allow"), allow);
  }
  assert.ok(env.BUNDLES.text(bundleKey("2026-10-03")), "a refused DELETE deletes nothing");
});

test("every other path is 404, including ones that would reach other bucket keys", async () => {
  const env = await flushedEnv();
  const paths = [
    "/",
    "/v1",
    "/v1/report/",
    "/v2/report",
    "/bundles",
    "/bundles/",
    "/bundles/2026-10-03.json",
    "/bundles/2026-10-03",
    "/bundles/../bundles/index.json.jsonl",
    "/bundles/2026-1-3.jsonl",
    "/bundles/x2026-10-03.jsonl",
    "/bundles/2026-10-03.jsonl/x",
    "/" + bundleKey("2026-10-03") + "x",
    "/" + INDEX_KEY + "/",
  ];
  for (const path of paths) {
    for (const method of ["GET", "POST"]) {
      const response = await worker.fetch(req(method, path), env);
      assert.equal(response.status, 404, `${method} ${path}`);
    }
  }
});
