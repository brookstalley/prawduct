// Done-when 5: the daily flush writes one sorted bundle, updates the index and
// empties the pending store; with nothing pending it writes nothing. Plus the
// idempotence cases: a second fire, a failed write, a crash between the bundle
// write and the cleanup, and reports that arrive mid-flush.

import { test } from "node:test";
import assert from "node:assert/strict";
import worker, { route, flushDay, bundleKey, INDEX_KEY } from "../src/worker.js";
import { makeEnv, post, storageOf } from "./support/fakes.mjs";
import { PYTHON_REPORTS } from "./support/reports.mjs";

const [A, B, C] = PYTHON_REPORTS.map((r) => r.bytes);
const DAY1 = Date.UTC(2026, 9, 3, 0, 0, 0);
const DAY2 = Date.UTC(2026, 9, 4, 0, 0, 0);

async function send(env, ...bodies) {
  for (const body of bodies) assert.equal((await route(post(body), env)).status, 204);
}

const cron = (env, scheduledTime) =>
  worker.scheduled({ cron: "0 0 * * *", type: "scheduled", scheduledTime }, env, { waitUntil() {} });

const lines = (text) => text.split("\n").filter((l) => l !== "");

test("flushDay names the UTC day of the scheduled time", () => {
  assert.equal(flushDay(DAY1), "2026-10-03");
  assert.equal(flushDay(Date.UTC(2026, 9, 3, 23, 59, 59)), "2026-10-03");
});

test("a flush writes one bundle sorted by bytes, the index, and empties pending", async () => {
  const env = makeEnv();
  await send(env, C, A, B, A);
  await cron(env, DAY1);

  const bundle = env.BUNDLES.text(bundleKey("2026-10-03"));
  assert.deepEqual(lines(bundle), [A, A, B, C].sort());
  assert.ok(bundle.endsWith("\n"));
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03"] });
  assert.deepEqual(env.BUNDLES.puts.sort(), [bundleKey("2026-10-03"), INDEX_KEY].sort());

  const storage = storageOf(env);
  assert.deepEqual(storage.rows("pending"), []);
  assert.deepEqual(storage.rows("claimed"), []);
  assert.deepEqual(storage.rows("claim"), []);
});

test("a flush with nothing pending writes nothing", async () => {
  const env = makeEnv();
  await cron(env, DAY1);
  assert.deepEqual(env.BUNDLES.puts, []);
  assert.equal(env.BUNDLES.objects.size, 0);
});

test("a second fire the same day, with nothing new, writes nothing", async () => {
  const env = makeEnv();
  await send(env, A, B);
  await cron(env, DAY1);
  const before = env.BUNDLES.puts.length;
  await cron(env, DAY1);
  assert.equal(env.BUNDLES.puts.length, before);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A, B].sort());
});

test("a second fire the same day merges new reports into the day's bundle, re-sorted", async () => {
  const env = makeEnv();
  // B sorts after A and C, so appending the second batch would leave the
  // bundle out of order.
  assert.ok(B > A && B > C);
  await send(env, B);
  await cron(env, DAY1);
  await send(env, C, A, C);
  await cron(env, DAY1);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A, B, C, C].sort());
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03"] });
});

test("the next day gets its own bundle, and the index lists both days in order", async () => {
  const env = makeEnv();
  await send(env, A);
  await cron(env, DAY1);
  await send(env, B);
  await cron(env, DAY2);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A]);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-04"))), [B]);
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03", "2026-10-04"] });
});

test("a failed bundle write fails the cron run and keeps every report for the next one", async () => {
  const env = makeEnv();
  await send(env, A, B);
  env.BUNDLES.failPut = () => {
    throw new Error("r2 unavailable");
  };
  await assert.rejects(cron(env, DAY1));
  assert.equal(env.BUNDLES.objects.size, 0);
  env.BUNDLES.failPut = null;
  await send(env, C);
  await cron(env, DAY2);
  // The claim taken on day 1 is finished into day 1's bundle; C, which
  // arrived after it, goes into day 2's.
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A, B].sort());
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-04"))), [C]);
  assert.deepEqual(storageOf(env).rows("pending"), []);
  assert.deepEqual(storageOf(env).rows("claimed"), []);
});

test("a crash after the bundle write but before cleanup never publishes a report twice", async () => {
  const env = makeEnv();
  await send(env, A, B);
  // The bundle lands, then the index write fails: the claim is not dropped.
  env.BUNDLES.failPut = (key) => {
    if (key === INDEX_KEY) throw new Error("crash");
  };
  await assert.rejects(cron(env, DAY1));
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A, B].sort());
  assert.equal(storageOf(env).rows("claimed").length, 2, "the claim survives the crash");
  // The object restarts (memory gone, storage kept) and the cron retries.
  env.BUNDLES.failPut = null;
  env.PENDING.evict("pending");
  await cron(env, DAY1);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A, B].sort(), "no duplicates");
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03"] });
  assert.deepEqual(storageOf(env).rows("claimed"), []);
  assert.deepEqual(storageOf(env).rows("claim"), []);
});

test("a report that arrives while a flush is publishing waits for the next flush", async () => {
  const env = makeEnv();
  await send(env, A);
  const realGet = env.BUNDLES.get.bind(env.BUNDLES);
  let injected = false;
  env.BUNDLES.get = async (key) => {
    if (!injected) {
      injected = true;
      await send(env, B); // lands between the claim and the bundle write
    }
    return realGet(key);
  };
  await cron(env, DAY1);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A]);
  assert.deepEqual(storageOf(env).rows("pending"), [{ report: B, n: 1 }]);
  env.BUNDLES.get = realGet;
  await cron(env, DAY2);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-04"))), [B]);
});

test("two overlapping flushes publish once", async () => {
  const env = makeEnv();
  await send(env, A, B);
  await Promise.all([cron(env, DAY1), cron(env, DAY1)]);
  assert.deepEqual(lines(env.BUNDLES.text(bundleKey("2026-10-03"))), [A, B].sort());
  assert.equal(env.BUNDLES.puts.filter((k) => k === bundleKey("2026-10-03")).length, 1);
});

test("bundles hold report bytes only; the one metadata value is a random claim id", async () => {
  const env = makeEnv();
  await send(env, A, B);
  await cron(env, DAY1);
  const entry = env.BUNDLES.objects.get(bundleKey("2026-10-03"));
  assert.deepEqual(Object.keys(entry.customMetadata), ["claim"]);
  assert.match(entry.customMetadata.claim, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  for (const line of lines(entry.text)) assert.ok(line === A || line === B);
});
