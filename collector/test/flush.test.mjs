// Done-when 5: the daily flush writes one sorted bundle, updates the index and
// empties the pending store; with nothing pending it writes nothing. Plus the
// idempotence cases: a second fire, a failed write, a crash between the bundle
// write and the deletes, reports that arrive mid-flush, overlapping runs, and
// a listing that spans pages.

import { test } from "node:test";
import assert from "node:assert/strict";
import worker, { route, flush, flushDay, bundleKey, INDEX_KEY, CLAIM_KEY, PENDING_PREFIX, MAX_CLAIM } from "../src/worker.js";
import { makeEnv, post } from "./support/fakes.mjs";
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
const bundle = (env, day) => lines(env.BUNDLES.text(bundleKey(day)));

// A finished claim is never deleted, because R2's delete takes no
// precondition. It is overwritten with a retirement mark that names it and
// holds no pending key.
function assertDrained(env) {
  assert.deepEqual(env.BUNDLES.keys(PENDING_PREFIX), [], "pending is empty");
  const claim = JSON.parse(env.BUNDLES.text(CLAIM_KEY));
  assert.deepEqual(Object.keys(claim), ["done"], "the claim is retired, and the mark holds no pending key");
  assert.match(claim.done, /^[0-9a-f]{32}$|^other$/);
}

test("flushDay names the UTC day of the scheduled time", () => {
  assert.equal(flushDay(DAY1), "2026-10-03");
  assert.equal(flushDay(Date.UTC(2026, 9, 3, 23, 59, 59)), "2026-10-03");
});

test("a flush writes one bundle sorted by bytes, the index, and empties pending", async () => {
  const env = makeEnv();
  await send(env, C, A, B, A);
  await cron(env, DAY1);

  assert.deepEqual(bundle(env, "2026-10-03"), [A, A, B, C].sort());
  assert.ok(env.BUNDLES.text(bundleKey("2026-10-03")).endsWith("\n"));
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03"] });
  assert.deepEqual(env.BUNDLES.keys(), [bundleKey("2026-10-03"), CLAIM_KEY, INDEX_KEY].sort());
  assertDrained(env);
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
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B].sort());
});

test("a second fire the same day merges new reports into the day's bundle, re-sorted, duplicates kept", async () => {
  const env = makeEnv();
  // B sorts after A and C, so appending the second batch would leave the
  // bundle out of order.
  assert.ok(B > A && B > C);
  await send(env, B);
  await cron(env, DAY1);
  await send(env, C, A, C, B);
  await cron(env, DAY1);
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B, B, C, C].sort());
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03"] });
  assertDrained(env);
});

test("the next day gets its own bundle, and the index lists both days in order", async () => {
  const env = makeEnv();
  await send(env, A);
  await cron(env, DAY1);
  await send(env, B);
  await cron(env, DAY2);
  assert.deepEqual(bundle(env, "2026-10-03"), [A]);
  assert.deepEqual(bundle(env, "2026-10-04"), [B]);
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03", "2026-10-04"] });
});

test("pending objects are deleted only after the bundle write succeeds", async () => {
  const env = makeEnv();
  await send(env, A, B);
  const pending = env.BUNDLES.keys(PENDING_PREFIX);
  env.BUNDLES.fail = (key, op) => {
    if (op === "put" && key.startsWith("bundles/")) throw new Error("r2 unavailable");
  };
  await assert.rejects(cron(env, DAY1));
  assert.deepEqual(env.BUNDLES.keys(PENDING_PREFIX), pending, "every pending report survives");
  assert.deepEqual(env.BUNDLES.deletes, []);
  assert.equal(env.BUNDLES.text(bundleKey("2026-10-03")), undefined);
});

test("a failed run's claim is finished by the next run, into its own day, before anything new", async () => {
  const env = makeEnv();
  await send(env, A, B);
  env.BUNDLES.fail = (key, op) => {
    if (op === "put" && key.startsWith("bundles/")) throw new Error("r2 unavailable");
  };
  await assert.rejects(cron(env, DAY1));
  env.BUNDLES.fail = null;
  await send(env, C); // arrives after the claim, so it is not in it
  await cron(env, DAY2);
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B].sort());
  assert.equal(env.BUNDLES.text(bundleKey("2026-10-04")), undefined);
  assert.equal(env.BUNDLES.keys(PENDING_PREFIX).length, 1, "C waits for the next run");
  await cron(env, DAY2);
  assert.deepEqual(bundle(env, "2026-10-04"), [C]);
  assertDrained(env);
});

test("a run that dies after the bundle write, before the deletes, never publishes a report twice", async () => {
  const env = makeEnv();
  await send(env, A, B);
  env.BUNDLES.fail = (key, op) => {
    if (op === "delete") throw new Error("crash");
  };
  await assert.rejects(cron(env, DAY1));
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B].sort());
  assert.equal(env.BUNDLES.keys(PENDING_PREFIX).length, 2, "the pending objects survive the crash");
  assert.ok(JSON.parse(env.BUNDLES.text(CLAIM_KEY)).keys, "so does the claim, outstanding");
  env.BUNDLES.fail = null;
  await cron(env, DAY1);
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B].sort(), "no duplicates");
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03"] });
  assertDrained(env);
});

test("a run that dies after deleting some pending objects finishes the rest without republishing", async () => {
  const env = makeEnv();
  await send(env, A, B, C);
  let deleted = 0;
  env.BUNDLES.fail = (key, op) => {
    if (op === "delete" && key.startsWith(PENDING_PREFIX) && ++deleted > 1) throw new Error("crash");
  };
  await assert.rejects(cron(env, DAY1));
  env.BUNDLES.fail = null;
  await cron(env, DAY1);
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B, C].sort());
  assertDrained(env);
});

test("a report that arrives while a flush is publishing waits for the next flush", async () => {
  const env = makeEnv();
  await send(env, A);
  const realGet = env.BUNDLES.get.bind(env.BUNDLES);
  let injected = false;
  env.BUNDLES.get = async (key) => {
    if (key === bundleKey("2026-10-03") && !injected) {
      injected = true;
      await send(env, B); // lands after the claim was written
    }
    return realGet(key);
  };
  await cron(env, DAY1);
  assert.deepEqual(bundle(env, "2026-10-03"), [A]);
  assert.equal(env.BUNDLES.keys(PENDING_PREFIX).length, 1);
  env.BUNDLES.get = realGet;
  await cron(env, DAY2);
  assert.deepEqual(bundle(env, "2026-10-04"), [B]);
});

test("two overlapping runs publish each report once", async () => {
  const env = makeEnv();
  await send(env, A, B, C);
  await Promise.all([cron(env, DAY1), cron(env, DAY1)]);
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B, C].sort());
  assertDrained(env);
});

test("a run that finds another run's claim after looking finishes that claim instead of taking its own", async () => {
  const env = makeEnv();
  await send(env, A);
  const [k1] = env.BUNDLES.keys(PENDING_PREFIX);
  await send(env, B);
  // Another run claimed k1 and wrote its bundle, but has not deleted yet. It
  // got there just after this run read "no claim".
  const realGet = env.BUNDLES.get.bind(env.BUNDLES);
  let raced = false;
  env.BUNDLES.get = async (key) => {
    const result = await realGet(key);
    if (key === CLAIM_KEY && !raced) {
      raced = true;
      await env.BUNDLES.put(CLAIM_KEY, JSON.stringify({ id: "other", day: "2026-10-03", keys: [k1] }));
      await env.BUNDLES.put(bundleKey("2026-10-03"), A + "\n", { customMetadata: { claim: "other" } });
    }
    return result;
  };
  await cron(env, DAY1);
  env.BUNDLES.get = realGet;
  assert.deepEqual(bundle(env, "2026-10-03"), [A], "the other run's report is not merged twice");
  assert.equal(env.BUNDLES.keys(PENDING_PREFIX).length, 1, "B waits for the next run");
  await cron(env, DAY1);
  assert.deepEqual(bundle(env, "2026-10-03"), [A, B].sort());
  assertDrained(env);
});

test("the listing follows the cursor across pages", async () => {
  const env = makeEnv({ pageSize: 2 });
  await send(env, A, B, C, A, B);
  await cron(env, DAY1);
  assert.ok(env.BUNDLES.lists >= 3, "the fake must have paginated");
  assert.deepEqual(bundle(env, "2026-10-03"), [A, A, B, B, C].sort());
  assertDrained(env);
});

test("one run claims at most MAX_CLAIM reports; the rest wait for the next run", async () => {
  const env = makeEnv({ pageSize: 400 });
  // Written straight into pending/, as route() would, to keep the test fast.
  for (let k = 0; k < MAX_CLAIM + 5; k++) {
    await env.BUNDLES.put(`${PENDING_PREFIX}${String(k).padStart(64, "0")}-${"0".repeat(32)}`, A);
  }
  await flush(env.BUNDLES, "2026-10-03");
  assert.equal(bundle(env, "2026-10-03").length, MAX_CLAIM);
  assert.equal(env.BUNDLES.keys(PENDING_PREFIX).length, 5);
  await flush(env.BUNDLES, "2026-10-04");
  assert.equal(bundle(env, "2026-10-04").length, 5);
  assertDrained(env);
});

test("only canonical, allowlisted bytes are published, whatever sits under pending/", async () => {
  const env = makeEnv();
  await send(env, A);
  await env.BUNDLES.put(`${PENDING_PREFIX}stray`, '{"sender":"203.0.113.77"}');
  await env.BUNDLES.put(`${PENDING_PREFIX}spaced`, JSON.stringify(PYTHON_REPORTS[1].report, null, 1));
  await cron(env, DAY1);
  assert.deepEqual(bundle(env, "2026-10-03"), [A]);
  assertDrained(env);
});

test("bundles hold report bytes only; the one metadata value is a random claim id", async () => {
  const env = makeEnv();
  await send(env, A, B);
  await cron(env, DAY1);
  const entry = env.BUNDLES.objects.get(bundleKey("2026-10-03"));
  assert.deepEqual(Object.keys(entry.customMetadata), ["claim"]);
  assert.match(entry.customMetadata.claim, /^[0-9a-f]{32}$/);
  for (const line of lines(entry.text)) assert.ok(line === A || line === B);
  assert.deepEqual(Object.keys(env.BUNDLES.objects.get(INDEX_KEY).customMetadata), []);
});

test("an unparseable index does not fail the flush; the flush rebuilds it from the bundles", async () => {
  // If an index that won't parse made the flush throw, it would throw every
  // night, and the claim and its pending objects would never clear.
  for (const corrupt of ["{not json", '{"days":"2026-10-03"}', "", '{"days":["../claims"]}']) {
    const env = makeEnv();
    await send(env, A);
    await cron(env, DAY1);
    await env.BUNDLES.put(INDEX_KEY, corrupt);
    await send(env, B);
    await cron(env, DAY2);
    assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-10-03", "2026-10-04"] }, corrupt);
    assert.deepEqual(bundle(env, "2026-10-04"), [B]);
    assertDrained(env);
  }
});

test("the index lists exactly the days that have a bundle", async () => {
  const env = makeEnv();
  await send(env, A);
  await cron(env, DAY1);
  // A stale index: it names a day with no bundle, and misses a bundle's day.
  await env.BUNDLES.put(INDEX_KEY, JSON.stringify({ days: ["2020-01-01"] }));
  await env.BUNDLES.put(bundleKey("2026-09-30"), A + "\n");
  await send(env, B);
  await cron(env, DAY2);
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: ["2026-09-30", "2026-10-03", "2026-10-04"] });
});

test("a claim that publishes nothing writes no bundle and no index", async () => {
  const env = makeEnv();
  await env.BUNDLES.put(`${PENDING_PREFIX}stray`, '{"sender":"203.0.113.77"}');
  await cron(env, DAY1);
  assert.equal(env.BUNDLES.text(INDEX_KEY), undefined);
  assert.equal(env.BUNDLES.text(bundleKey("2026-10-03")), undefined);
  assertDrained(env);
});
