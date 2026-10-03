// Done-when 5, overlapping runs: two flushes that interleave never lose a
// report and never publish one twice. Each test replays one exact
// interleaving with pause points on per-run views of one shared bucket, so
// it is deterministic. Each is the failure a specific unconditional write
// would cause, named in the test.

import { test } from "node:test";
import assert from "node:assert/strict";
import { route, flush, bundleKey, INDEX_KEY, CLAIM_KEY, PENDING_PREFIX } from "../src/worker.js";
import { makeEnv, post, pauseAt, runView } from "./support/fakes.mjs";
import { PYTHON_REPORTS } from "./support/reports.mjs";

const [A, B, C] = PYTHON_REPORTS.map((r) => r.bytes);
// A fourth report, distinct from the other three.
const D = PYTHON_REPORTS[0].bytes.replace('"iso_week":39', '"iso_week":40');
const DAY1 = "2026-10-03";
const DAY2 = "2026-10-04";

async function send(env, ...bodies) {
  for (const body of bodies) assert.equal((await route(post(body), env)).status, 204);
}

// A regression can leave a run short of the pause point a test waits on, and
// node's runner has no default timeout, so each test fails rather than hangs.
const BOUNDED = { timeout: 10_000 };

const lines = (text) => (text === undefined ? [] : text.split("\n").filter((l) => l !== ""));
const published = (env) => env.BUNDLES.keys("bundles/").filter((k) => k.endsWith(".jsonl")).flatMap((k) => lines(env.BUNDLES.text(k)));

function claimOutstanding(env) {
  const text = env.BUNDLES.text(CLAIM_KEY);
  return text !== undefined && Array.isArray(JSON.parse(text).keys);
}

// Every report sent is published exactly once, and nothing is left pending
// or claimed.
function assertEachOnce(env, sent) {
  assert.deepEqual(published(env).sort(), [...sent].sort(), "each report is published exactly once");
  assert.deepEqual(env.BUNDLES.keys(PENDING_PREFIX), [], "pending is empty");
  assert.equal(claimOutstanding(env), false, "no claim is outstanding");
}

test("R-1: a run that adopts another's claim and reads the bundle before it is written loses nothing", BOUNDED, async () => {
  // The review's interleaving: run 2 adopts run 1's claim and reads the
  // bundle before run 1 writes it. Run 1 writes the bundle and deletes the
  // pending objects. Run 2's later reads come back empty. Run 2 must not then
  // write a bundle with fewer lines over run 1's.
  const env = makeEnv();
  await send(env, A, B, C);
  const keys = env.BUNDLES.keys(PENDING_PREFIX);

  const oneAtBundle = pauseAt("get", bundleKey(DAY1));
  const run1 = flush(runView(env.BUNDLES, { pauses: [oneAtBundle] }), DAY1);
  await oneAtBundle.reached; // run 1 holds the claim, and has read nothing yet

  const twoAtSecondReport = pauseAt("get", keys[1]);
  const run2 = flush(runView(env.BUNDLES, { pauses: [twoAtSecondReport] }), DAY1);
  await twoAtSecondReport.reached; // run 2 adopted, read no bundle, read keys[0]

  oneAtBundle.release();
  await run1; // run 1 published all three and deleted them
  twoAtSecondReport.release();
  await run2;

  assertEachOnce(env, [A, B, C]);
  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: [DAY1] });
});

test("a stale bundle write never lands over a newer bundle (kills an unconditional bundle put)", BOUNDED, async () => {
  // Run 2 reads the bundle and every claimed report, then stalls before its
  // write. Run 1 finishes the claim, and run 3 merges a new report D into the
  // same bundle. Run 2's write, made on what it read, would drop D.
  const env = makeEnv();
  await send(env, A, B, C);

  const oneAtBundle = pauseAt("get", bundleKey(DAY1));
  const run1 = flush(runView(env.BUNDLES, { pauses: [oneAtBundle] }), DAY1);
  await oneAtBundle.reached;

  const twoAtWrite = pauseAt("put", bundleKey(DAY1));
  const run2 = flush(runView(env.BUNDLES, { pauses: [twoAtWrite] }), DAY1);
  await twoAtWrite.reached;

  oneAtBundle.release();
  await run1;
  await send(env, D);
  await flush(env.BUNDLES, DAY1); // run 3
  twoAtWrite.release();
  await run2;

  assertEachOnce(env, [A, B, C, D]);
});

test("a run that finds its claim's reports gone does not re-stamp the bundle (kills merging past a missing report)", BOUNDED, async () => {
  // As above, but run 3 dies after writing its bundle, before its deletes,
  // so its claim is outstanding. Run 2 must not write the bundle again with
  // its own claim id: run 4 would then not recognise run 3's claim as merged
  // and would publish D a second time.
  const env = makeEnv();
  await send(env, A, B, C);

  const oneAtBundle = pauseAt("get", bundleKey(DAY1));
  const run1 = flush(runView(env.BUNDLES, { pauses: [oneAtBundle] }), DAY1);
  await oneAtBundle.reached;

  const twoAtWrite = pauseAt("put", bundleKey(DAY1));
  const run2 = flush(runView(env.BUNDLES, { pauses: [twoAtWrite] }), DAY1);
  await twoAtWrite.reached;

  oneAtBundle.release();
  await run1;
  await send(env, D);
  const crashOnDelete = (op) => {
    if (op === "delete") throw new Error("run 3 dies");
  };
  await assert.rejects(flush(runView(env.BUNDLES, { fail: crashOnDelete }), DAY1));
  assert.equal(claimOutstanding(env), true, "run 3's claim is left outstanding");
  twoAtWrite.release();
  await run2;
  await flush(env.BUNDLES, DAY1); // run 4 finishes run 3's claim

  assertEachOnce(env, [A, B, C, D]);
});

for (const prior of [false, true]) {
  const where = prior ? "over a retired claim (kills a retirement mark that doesn't name its claim)" : "on a fresh bucket";
  test(`a stalled claim never overwrites the claim another run took, ${where} (kills an unconditional claim write)`, BOUNDED, async () => {
    // Run 1 lists A and B, run 2 lists A, B and C, and both stall before
    // writing the claim. Run 1 claims and finishes. Run 2's claim, if it
    // landed, would hold A and B, already deleted, so it would be skipped as
    // published, and C would be deleted unpublished. Over a retired claim
    // both runs read the same mark. Run 1's own mark must not share that
    // mark's etag, or run 2's write would pass its precondition.
    const env = makeEnv();
    if (prior) {
      await send(env, D);
      await flush(env.BUNDLES, DAY1);
    }
    await send(env, A, B);

    const oneAtClaim = pauseAt("put", CLAIM_KEY);
    const run1 = flush(runView(env.BUNDLES, { pauses: [oneAtClaim] }), DAY1);
    await oneAtClaim.reached;
    await send(env, C);
    const twoAtClaim = pauseAt("put", CLAIM_KEY);
    const run2 = flush(runView(env.BUNDLES, { pauses: [twoAtClaim] }), DAY1);
    await twoAtClaim.reached;

    oneAtClaim.release();
    await run1;
    twoAtClaim.release();
    await run2;
    assert.equal(env.BUNDLES.keys(PENDING_PREFIX).length, 1, "C waits for the next run");
    await flush(env.BUNDLES, DAY2);

    assertEachOnce(env, prior ? [A, B, C, D] : [A, B, C]);
  });
}

test("a stalled run never retires another run's claim (kills an unconditional claim retirement)", BOUNDED, async () => {
  // Run 2 adopts run 1's claim after run 1 published it, and stalls just
  // before retiring it. Run 1 finishes; run 3 claims D and dies after its
  // bundle write. If run 2 then retired the claim it finds, which is now run
  // 3's, the next day's run would claim D afresh and publish it into a second
  // bundle.
  const env = makeEnv();
  await send(env, A, B);
  const batchDelete = (key) => Array.isArray(key);

  const oneAtDeletes = pauseAt("delete", batchDelete);
  const run1 = flush(runView(env.BUNDLES, { pauses: [oneAtDeletes] }), DAY1);
  await oneAtDeletes.reached; // run 1 has published, and deleted nothing

  // Run 2 adopted, so its only claim write is the retirement.
  const twoAtRetire = pauseAt("put", CLAIM_KEY);
  const twoAtDelete = pauseAt("delete", CLAIM_KEY);
  const run2 = flush(runView(env.BUNDLES, { pauses: [twoAtRetire, twoAtDelete] }), DAY1);
  await Promise.race([twoAtRetire.reached, twoAtDelete.reached]);

  oneAtDeletes.release();
  await run1;
  await send(env, D);
  const crashOnDelete = (op, key) => {
    if (op === "delete" && batchDelete(key)) throw new Error("run 3 dies");
  };
  await assert.rejects(flush(runView(env.BUNDLES, { fail: crashOnDelete }), DAY1));
  assert.equal(claimOutstanding(env), true, "run 3's claim is left outstanding");
  twoAtRetire.release();
  twoAtDelete.release();
  await run2;
  await flush(env.BUNDLES, DAY2);
  await flush(env.BUNDLES, DAY2);

  assertEachOnce(env, [A, B, D]);
});

test("a stale index write never drops a day another run added (kills an unconditional index put)", BOUNDED, async () => {
  // Run 2 adopts run 1's claim, sees run 1's bundle and skips the merge, but
  // reads the index before run 1 writes it, and stalls before its own index
  // write. Run 1 finishes, and run 3 publishes the next day. Run 2's index,
  // built on what it read, would leave the next day out.
  const env = makeEnv();
  await send(env, A);

  const oneAtIndex = pauseAt("get", INDEX_KEY);
  const run1 = flush(runView(env.BUNDLES, { pauses: [oneAtIndex] }), DAY1);
  await oneAtIndex.reached; // run 1 has written its bundle

  const twoAtIndexWrite = pauseAt("put", INDEX_KEY);
  const run2 = flush(runView(env.BUNDLES, { pauses: [twoAtIndexWrite] }), DAY1);
  await twoAtIndexWrite.reached;

  oneAtIndex.release();
  await run1;
  await send(env, B);
  await flush(env.BUNDLES, DAY2);
  twoAtIndexWrite.release();
  await run2;

  assert.deepEqual(JSON.parse(env.BUNDLES.text(INDEX_KEY)), { days: [DAY1, DAY2] });
  assertEachOnce(env, [A, B]);
});

test("a run that loses the bundle race on every attempt throws and deletes nothing (kills giving up quietly)", BOUNDED, async () => {
  // Every bundle write fails its precondition, as if another run wrote the
  // bundle between each read and write. The run must not go on to delete
  // reports it never published.
  const env = makeEnv();
  await send(env, A, B);
  const pending = env.BUNDLES.keys(PENDING_PREFIX);
  const view = runView(env.BUNDLES);
  let attempts = 0;
  const put = view.put;
  view.put = async (key, value, options) => {
    if (key === bundleKey(DAY1)) {
      attempts++;
      return null;
    }
    return put(key, value, options);
  };
  await assert.rejects(flush(view, DAY1), /bundle kept changing/);
  assert.ok(attempts > 1, "the run read again before giving up");
  assert.deepEqual(env.BUNDLES.keys(PENDING_PREFIX), pending, "every pending report survives");
  assert.equal(claimOutstanding(env), true, "the claim waits for the next run");
  await flush(env.BUNDLES, DAY1);
  assertEachOnce(env, [A, B]);
});

test("the pause points are real: a run held at one has made no later call", BOUNDED, async () => {
  // The interleaving tests mean something only if a paused run is truly
  // stopped. Feed the instrument a case it must catch.
  const env = makeEnv();
  await send(env, A);
  const atBundle = pauseAt("get", bundleKey(DAY1));
  const run = flush(runView(env.BUNDLES, { pauses: [atBundle] }), DAY1);
  await atBundle.reached;
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(env.BUNDLES.text(bundleKey(DAY1)), undefined, "nothing past the pause has run");
  assert.equal(env.BUNDLES.keys(PENDING_PREFIX).length, 1);
  atBundle.release();
  await run;
  assertEachOnce(env, [A]);
});
