# prawduct stats collector

A Cloudflare Worker that receives anonymous prawduct stats reports and publishes them once a day
as a public bundle. It exists to serve two goals, and when they conflict the second wins:

1. collect telemetry that improves prawduct;
2. know nothing about the contributor.

Sending is the client's business (`prawduct-hook contribute`, in `plugin/lib/contribution.py`).
Contribution is off by default, and a repository sends nothing until its owner opts in. The
collector only ever sees reports that a contributor has previewed byte for byte and approved.

The Worker has one binding, a private R2 bucket. It has no Durable Object, database, queue or KV.

## The privacy promise

**Stored:** each accepted report, as one R2 object under `pending/` whose body is the report's
canonical bytes and nothing else. The object has no custom metadata and no HTTP metadata. Its key
is `pending/<sha256 of the bytes>-<128 random bits>`, so the key is built from the content and a
random number, never from the sender or the time. The random part keeps identical reports from two
contributors apart, so both are counted.

A report gets in only if it passes the allowlist (`schema.json`, a byte-for-byte copy of
`plugin/lib/contribution_schema.json`). Under that allowlist every value is an integer, a number on
its field's step, a band label, or a boolean, so a report has no room for free text.

**Not stored, anywhere, by this code:**

- the sender's IP address, or any header. The worker reads `content-type` and `content-length`
  and nothing else, and never touches the request's `cf` object.
- arrival time, in any key, body or metadata the worker writes.
- arrival order. R2 lists keys in lexical order, and a key's order is set by its hash and random
  part. A bundle is sorted by its lines' bytes.
- logs. The worker has no `console` call, and `wrangler.toml` turns off Workers Logs, invocation
  logs, traces, Issues and Logpush, and declares no tail consumers.

Each claim above is pinned by a test under `test/`, as § Tests shows.

## What Cloudflare still sees

The guarantees below hold **by policy, not by construction**. They depend on how the account owner
runs the account, and on Cloudflare.

- **The IP address, at the TLS edge.** Cloudflare terminates the connection, so it sees the
  sender's address while the request is open. The worker never reads it. A contributor who wants to
  hide it can send through a VPN or Tor, because the client honours `HTTPS_PROXY`.
- **A pending object's upload time, for under a day.** R2 stamps every object with an `uploaded`
  time, and the worker can't prevent that. Until the nightly flush deletes a pending object, its
  upload time is visible to anyone with access to the account, in a listing or the dashboard. The
  flush runs every night at 00:00 UTC, so no pending object outlives a day unless a flush fails or
  more than `MAX_CLAIM` reports arrive in a day (§ Flush).
- **Nothing after the delete.** R2 has no object versioning: the S3 compatibility table marks
  `GetBucketVersioning` and `PutBucketVersioning` unimplemented. Cloudflare's docs call deleting an
  object irreversible
  ([Delete objects](https://developers.cloudflare.com/r2/objects/delete-objects/)). Once the flush
  deletes a pending object, its upload time is gone with it. A bundle keeps only its own upload
  time, which is when the flush ran.
- **Real-time logs.** Anyone with access to the account can open a live tail (`wrangler tail`, or
  **Logs → Live** in the dashboard). A live tail shows each request's headers and `cf` object while
  it streams, whatever `observability` says. Nothing is persisted unless the tail is running. The
  policy is never to tail this Worker.
- **Aggregate metrics.** Workers metrics and R2 metrics record request and operation counts, with
  no per-request detail.
- **Bucket features that would undo this.** Leave these off on the bucket:
  - **event notifications**, which would announce each upload, with a time, to a queue;
  - **bucket locks**, which would stop the flush from deleting;
  - **public access**: no `r2.dev` URL and no custom domain on the bucket. The Worker serves only
    `bundles/`.

### Why not a Durable Object

An earlier design held pending reports in one SQLite-backed Durable Object. SQLite Durable Objects
keep a change log for 30 days to support point-in-time recovery (`getBookmarkForTime`). With that
log, code deployed on the account could recover roughly when each pending row was written, and the
rows deleted by a flush, for 30 days. The docs offer no way to switch this off, and the key-value
backend is closed to new namespaces. Writing each report straight to R2 trades that for an upload
time that lasts under a day and then is deleted irreversibly.

The upgrade path to "by construction" is Oblivious HTTP (RFC 9458): a relay sees the IP but not the
content, and the collector sees the content but not the IP. It is deferred (see
`.prawduct/artifacts/roi-audit-2026-10-02.md` § Contribution design).

## Endpoints

| Method and path | Response |
|---|---|
| `POST /v1/report` | `204`, empty body: stored. `400`, `{"refused":"<rule>"}`: refused, nothing stored. `503`, empty body: storage unavailable, retry later. |
| `GET /bundles/index.json` | `200` `application/json`: `{"days":["YYYY-MM-DD", …]}`, ascending. `404` before the first flush. |
| `GET /bundles/<YYYY-MM-DD>.jsonl` | `200` `application/x-ndjson`: that day's bundle. `404` if there is none. |
| `GET /health` | `200` `application/json`: `{"claim_outstanding":false}` or `true`, and nothing else (§ Is it working?). |
| the same paths, another method | `405`, with `Allow`. |
| anything else, including `pending/` and `claims/` keys | `404`. |

`POST /v1/report` requirements:

- `content-type: application/json` (parameters such as `charset` are allowed);
- a body of at most **4 KiB**. The largest report the schema allows is under 800 bytes in canonical
  form, and under 1 KiB pretty-printed. So 4 KiB admits every valid report however it is spaced,
  and refuses padding before parsing it;
- UTF-8 JSON that passes the allowlist under the same rules as `contribution.validate`:
  - no key outside the schema, and every required key present;
  - enums matched type-strictly, so `0` is not `false`;
  - bands drawn from the band list;
  - integer fields given JSON integers, so `1.0` and `1e0` are refused;
  - numbers finite, within `[min, max]`, and within 1e-6 of a step;
  - booleans never accepted as numbers.

A refusal names the first failing rule, and never echoes input. The rules are `content-type`,
`too-large`, `json`, `not-object`, `unknown-key`, `missing-key`, `enum`, `band`, `not-number`,
`not-integer`, `range` and `step`.

## Bundle format: the aggregator's input contract

This is the input contract for #262's `aggregate-review-stats`.

- `bundles/index.json` is `{"days":[…]}`: every day that has a bundle, ascending, as `YYYY-MM-DD`.
- `bundles/<day>.jsonl` holds one report per line, each a JSON object in canonical form: keys
  sorted, no whitespace, ASCII. Lines are sorted by their bytes, and every line, the last
  included, ends in `\n`.
- **Duplicates are real.** Two contributors can send byte-identical reports, for example a small
  week with only the required fields. Each copy is its own line, so the aggregator must not
  dedupe lines.
- **Canonical form is the client's.** For every report the client can produce, the line is exactly
  the bytes `contribution.canonical_bytes` gave and the contributor approved. A stepped number the
  allowlist admits within its 1e-6 tolerance is written as the grid value it stands for, for
  example `0.35000000001` as `0.35`, and a whole number as an integer.
- **The day names the flush, not the week the report covers.** A bundle holds whatever a flush
  claimed, which is roughly the previous day's arrivals. Each report carries its own window
  (`iso_year`, `iso_week`) and version (`plugin_major`, `plugin_minor`, `dev`). Aggregate on those,
  never on the bundle's day.
- **Poisoning cannot be detected.** A report carries no identity, so the aggregator must use
  robust statistics, such as medians and trimmed means, rather than trusting any single line.
- A later schema can be added under `POST /v2/report`. Every line carries `schema`.

## Flush

The cron runs at 00:00 UTC and names the bundle for the UTC day it runs. Each run works through
three steps.

1. **Claim.** It reads `claims/current.json`. If a claim is outstanding there, it finishes that
   claim and takes none of its own. Otherwise it lists `pending/`, following R2's
   `truncated`/`cursor` pagination, and takes up to `MAX_CLAIM` (900) keys. It writes them, with a
   random claim id and the day, to `claims/current.json`, only if that object is still as it was
   read: absent, or the same retirement mark. If another run claimed first, this run finishes that
   claim instead.
2. **Publish.** It reads the day's bundle, if one exists. Unless that bundle's
   `customMetadata.claim` is already this claim's id, it reads every claimed object and keeps only
   canonical, allowlisted bytes. It merges them into the bundle, keeping duplicates, sorts, and
   writes the bundle with `customMetadata: {claim: <id>}`. That write lands only if the bundle is
   still as it was read. It then rebuilds `bundles/index.json` from a listing of the bundles that
   exist, again only over the index it read, and writes nothing if the index is already right.
3. **Clean up.** Only after the bundle write succeeds, it deletes the claimed pending objects, in
   batches of up to 1,000 keys, the most R2 takes per call. It then retires the claim: it
   overwrites it with `{"done":"<claim id>"}`, only if the claim is still the one it holds.

**Overlapping runs.** Every write a run makes on the strength of something it read carries a
precondition that the thing is unchanged. That is R2's `put` with `onlyIf`: `{etagMatches: <etag
read>}`, or `If-None-Match: *` for a key that was absent. A write that loses a race stores nothing,
and the run reads again, up to four times; then it throws and leaves the claim for the next run. A
claim is never deleted, because R2's `delete` takes no precondition, and a stalled run could
otherwise delete a claim taken after the one it held. The retirement mark names its claim, so no two
marks share an etag. Last, a claimed pending object is deleted only after its claim is published.
So a run that finds one gone knows another run published the claim, and writes no bundle for it.
Writing what was left would put a bundle without that report over one that has it.

**Where the record lives.** A claim manifest under `claims/` holds which pending keys a bundle
contains. The bundle's own custom metadata holds only the id of the last claim merged into it. A
key list can't go in the bundle's metadata, because R2 caps custom metadata at 8,192 bytes, about
90 keys. A run that finds a manifest finishes it, and the id on the bundle stops a claim from being
merged twice. A retired claim keeps only its random id. Its upload time is when the flush finished.

The failure cases:

| Failure | Outcome |
|---|---|
| Nothing is pending | Nothing is written: no claim, no bundle, no index update. |
| A claim's reports all fail re-admission | Nothing is published, and no bundle or index is created. The pending objects are deleted, and the claim is retired. |
| The cron fires twice | If the first run has finished, the second finds nothing pending and writes nothing. If the two overlap, see "Two runs overlap". |
| A second flush on the same day | It merges into that day's bundle and re-sorts it. |
| The bundle write fails | The run fails, and no pending object is deleted. The next run finishes the claim into its original day's bundle. That run claims nothing new; reports that arrived since wait one more run. |
| The run dies after the bundle write, before or during the deletes | The next run finds the claim, sees the claim id on the bundle, skips the merge, and finishes the deletes. No report is published twice. |
| Two runs overlap | Only one claim is outstanding at a time, so the later run finishes the earlier one's claim. Whichever run writes the bundle first wins. The other's write fails its precondition, and on reading again the run finds the claim id on the bundle, or a claimed report gone, and writes nothing. A stale index write fails the same way and is rebuilt. Neither run can retire a claim but its own. No report is lost or published twice. `test/overlap.test.mjs` replays, for each guard, the interleaving that loses or duplicates a report without it. |
| A run loses the same race four times | It throws without deleting anything, and the next run finishes the claim. |
| `bundles/index.json` is missing, stale or unparseable | The flush never parses it. It rebuilds the index from the bundles that exist, so the next flush that has a claim puts it right. |
| A report arrives during a flush | It isn't in the claim, so it stays pending for the next run. |

**The cap.** A flush makes about one R2 call per claimed report, plus a dozen more. The Free plan
allows 1,000 calls to Cloudflare services per invocation, so one run claims at most 900 reports,
and the rest wait for the next run. The cap bounds the cost of a run, not the throughput. If more
than 900 reports arrive every day, raise `MAX_CLAIM` on the Paid plan (10,000 by default) or add
cron times. Otherwise the backlog grows, and pending objects outlive a day.

## Deploy (owner)

These steps need the owner's Cloudflare account. The Workers Free plan covers the Worker and one
cron trigger. R2 usage at this volume sits inside R2's free tier, but the account needs an R2
subscription: a checkout flow in the dashboard, under **R2**
(https://developers.cloudflare.com/r2/get-started/).

1. Install a current Wrangler (`observability.issues` is documented from 4.134.0). Check with
   `npx wrangler --version`, then run `npx wrangler login`.
2. Create the bucket: `npx wrangler r2 bucket create <name>`, and set `bucket_name` in
   `wrangler.toml` to `<name>`. The deployed collector's bucket is `prawduct-telemetry`, so a
   redeploy to the same account needs no change. Leave public access, event notifications and
   bucket locks off (§ What Cloudflare still sees).
3. Optional: set `account_id`, or `CLOUDFLARE_ACCOUNT_ID`, and add a `route` or custom domain if
   the collector should answer on your own hostname. Otherwise it answers on `workers.dev`.
4. From `collector/`, run `npx wrangler deploy`.
5. Confirm in the dashboard (**Workers & Pages → prawduct-collector**):
   - **Settings → Observability**: Workers Logs and Traces are disabled.
   - **Settings**: there is no Logpush and no Tail Worker.
   - **Logs**: nothing is persisted after a test request.
   - **R2 → the bucket → Settings**: public access is disabled, and there are no event
     notifications and no bucket lock rules.
6. Smoke test. Write one report to `report.json`. Use this fixture, which is marked `"dev":true`
   because it is published in the next bundle like any other report:

   ```sh
   printf '%s' '{"dev":true,"iso_week":39,"iso_year":2026,"plugin_major":3,"plugin_minor":7,"reviews":"10-49","schema":1,"scopes":"1-9","sessions":"10-49"}' > report.json
   ```

   Don't post `prawduct-hook contribute --json` output as it stands. It is a preview,
   `{"schema_version":1,"pending":[{"window":…,"report":{…}}],"digest":…}`, which the worker refuses
   with `400 {"refused":"unknown-key"}`. To send a real pending report instead, take one out of it:

   ```sh
   prawduct-hook contribute --json | python3 -c 'import json,sys; r=json.load(sys.stdin)["pending"][0]["report"]; print(json.dumps(r,sort_keys=True,separators=(",",":")))' > report.json
   ```

   That fails with `IndexError` when nothing is pending. A report sent this way is not recorded as
   sent, so `contribute --send` would send its window again.

   Then run `curl -X POST -H 'content-type: application/json' --data-binary @report.json
   https://<host>/v1/report` and expect `204`. One object appears under `pending/` with no custom
   metadata. `GET https://<host>/bundles/index.json` returns `404` until the first 00:00 UTC flush,
   then lists the day, and `pending/` is empty again.
7. Give the endpoint URL to wave 2 (`build-plan-telemetry-contribution.md`), which pins it as the
   client's endpoint constant. A live round trip is then recorded in
   `.prawduct/operator-verification.md`.

**Check on the first live flush.** The flush is safe against overlapping runs only if R2 honours
two preconditions on the binding's `put`: `{etagMatches: <etag>}`, an `R2Conditional` field the
binding reference documents, and a `Headers` object carrying `If-None-Match: *`. The reference says
`onlyIf` takes either form and every conditional header but `If-Range`. R2's release notes of
2023-06-16 say the binding parses a wildcard (`*`) in conditional headers. The worker puts the
wildcard in `Headers` because the `R2Conditional` fields once parsed `*` as a literal etag
(workerd#2572, since closed). It passes `etagMatches` the unquoted `etag`, not the quoted
`httpEtag`. The docs don't say which form the field takes, but a third-party report says workerd
throws on a quoted one, and the fake does the same. The fake models both forms, but only a live run proves the binding honours them. If R2
ignored them, overlapping runs could lose or double-publish reports again. With one daily cron,
runs rarely overlap.

## Is it working?

The worker keeps no logs, so check the state it leaves behind. None of these checks needs a log,
and none reveals anything about a contributor.

1. **`GET https://<host>/health`.** `{"claim_outstanding":false}` is healthy. `true` outside the
   first few minutes after 00:00 UTC means the last flush failed partway, and its claim waits for
   the next run, which retries it. `true` on two mornings running means every flush is failing.
2. **`GET https://<host>/bundles/index.json`.** The last entry in `days` is the last day a flush
   published something. If reports are being sent and that day is more than a day old, flushes are
   not publishing.
3. **The pending count, in the dashboard.** Go to **R2 → the bucket → Objects** and filter on
   `pending/`. Wrangler can't list objects: its `r2 object` commands are `get`, `put` and `delete`.
   After a healthy flush the count is zero, or whatever exceeded the 900 cap. A count that only grows
   means flushes are failing, and pending upload times are outliving a day.

To see a stuck claim, run `npx wrangler r2 object get <bucket>/claims/current.json --remote --pipe`.
Its `day` is the day the stuck flush began. Don't delete or edit it by hand. A run that found no
claim would claim the same reports again and publish twice any already in the bundle. Fix the
cause, such as R2 errors or a hand-edited object, and let the next run finish the claim. A broken
`bundles/index.json` can't be the cause: the flush rebuilds it rather than reading it.

`/health` does not report the pending count. Anyone can call the route, and a count anyone can poll
would time each report's arrival. The claim flag changes only when the cron runs, so it reveals
nothing about any report.

## Tests

```sh
node --test 'collector/test/*.test.mjs'
```

Quote the glob: node expands it itself, and runs each test file in its own process. A bare
directory (`node --test collector/test/`) is not searched for test files. The tests need node 22 or
later and nothing else: no npm install and no dependencies. They were run on node 22.23.3, 24.21.0
and 25.6.1. `test/support/fakes.mjs` is an in-memory R2 bucket shaped to the documented binding:

- `get` returns a body, `text()`, `json()`, `etag` (unquoted), `httpEtag` (quoted),
  `customMetadata`, `httpMetadata` and `uploaded`;
- `put` takes `httpMetadata`, `customMetadata` and `onlyIf`. Two preconditions are modelled, the
  two the worker uses: `Headers` with `If-None-Match: *`, and `{etagMatches}`. Any other
  precondition throws, and so does a quoted etag, as in workerd. The etag is the MD5 of the body, so
  writing the same bytes again keeps it, as R2 does for a single-part upload;
- `delete` takes a key or up to 1,000 keys;
- `list` takes `prefix`, `cursor` and `limit`, returns pages in lexical order with `truncated` and
  `cursor`, and can be made to page small;
- `runView` and `pauseAt` give each of several runs its own view of one bucket, and stop a run just
  before a chosen call until the test releases it. So an overlap test replays one exact
  interleaving, the same way every time.

| Done-when | Test file |
|---|---|
| 1. Each refusal class is a 400, and nothing is stored | `refusals.test.mjs` |
| 2. Storage is canonical bytes in one object: no metadata, no address, header or time in key, body or metadata; parity with Python | `storage.test.mjs` |
| 3. No `console`, and no header read beyond content-type and content-length (source grep) | `source.test.mjs` |
| 4. `wrangler.toml` turns observability off and binds only R2 | `wrangler.test.mjs` |
| 5. The flush sorts, keeps duplicates, rebuilds the index, writes nothing when empty, and empties pending; idempotence, pagination, the cap and a corrupt index | `flush.test.mjs` |
| 5. Overlapping runs never lose a report or publish one twice: one test per conditional write, each replaying the interleaving that write guards against | `overlap.test.mjs` |
| 6. The GET routes, `/health`, and 404/405 | `routes.test.mjs` |

The Python parity fixtures under `test/fixtures/` come from the real client. Regenerate them with
`python3 collector/test/fixtures/generate.py [PLUGIN_DIR]`, where `PLUGIN_DIR` defaults to this
repository's `plugin/`. The script refuses to run unless that plugin's
`lib/contribution_schema.json` is byte-identical to `collector/schema.json`. Importing
`generate.py` has no side effects, so a Python test can compare its `step_values()`,
`verdict(body)` and `BODIES` with the committed files. The hand-picked
reports in `test/support/reports.mjs` were produced by applying `contribution.to_step` to raw
values, then printing `json.dumps(report, sort_keys=True, separators=(",", ":"))`.

## Docs consulted (verify-api, 2026-10-03)

- R2 Workers binding API:
  - `get(key) -> R2ObjectBody | null`;
  - `put(key, value, {httpMetadata, customMetadata, onlyIf}) -> R2Object | null`, where `null`
    means a failed precondition;
  - `delete(key | keys[])`, up to 1,000 keys;
  - `list({prefix, cursor, limit, include})`, which returns `{objects, truncated, cursor}` in
    lexical order, and may return fewer than `limit`, so callers loop on `truncated`;
  - `R2Object.uploaded`, `R2Object.etag` (unquoted) and `R2Object.httpEtag` (quoted);
  - `onlyIf` takes an `R2Conditional` (`etagMatches`, `etagDoesNotMatch`, `uploadedBefore`,
    `uploadedAfter`) or `Headers` with every conditional header but `If-Range`. On a failed
    precondition `put` returns `null` and stores nothing. `delete` takes no options, so it has no
    precondition.

  https://developers.cloudflare.com/r2/api/workers/workers-api-reference/ (re-read 2026-10-03)
- R2 release notes. 2022-09-19: `put()` takes `onlyIf`. 2023-06-16: the binding parses conditional
  headers with several etags, which can be strong, weak or a wildcard (`*`).
  https://developers.cloudflare.com/r2/platform/release-notes/
- workerd#2572 (closed): the `R2Conditional` fields parsed `*` as a strong etag, so a wildcard
  there did not mean "any object". The worker puts its wildcard in `Headers` for that reason.
  https://github.com/cloudflare/workerd/issues/2572
- Wrangler's `r2 object` commands are `get`, `put` and `delete`, with no listing.
  https://developers.cloudflare.com/workers/wrangler/commands/r2/
- R2 delete: "Deleting objects from a bucket is irreversible."
  https://developers.cloudflare.com/r2/objects/delete-objects/
- R2 S3 compatibility: `GetBucketVersioning` and `PutBucketVersioning` are not implemented, and
  `If-None-Match` is supported on `PutObject`. https://developers.cloudflare.com/r2/api/s3/api/
- R2 limits: 8,192 bytes of custom metadata, and 1,024-byte keys.
  https://developers.cloudflare.com/r2/platform/limits/
- R2 pricing and free tier, and the R2 subscription: https://developers.cloudflare.com/r2/pricing/
  and https://developers.cloudflare.com/r2/get-started/
- R2 bucket features to leave off: https://developers.cloudflare.com/r2/buckets/event-notifications/
  and https://developers.cloudflare.com/r2/buckets/bucket-locks/
- Wrangler configuration: `name`, `main`, `compatibility_date`, `logpush`, `observability`,
  `triggers.crons`, `r2_buckets`, `tail_consumers`.
  https://developers.cloudflare.com/workers/wrangler/configuration/
- Workers Logs: on by default for new Workers; `observability.enabled`, `head_sampling_rate`,
  `observability.logs.invocation_logs`.
  https://developers.cloudflare.com/workers/observability/logs/workers-logs/
- Traces: `observability.traces.enabled` and `observability.logs.enabled`.
  https://developers.cloudflare.com/workers/observability/traces/
- Workers Issues: `observability.issues.enabled`.
  https://developers.cloudflare.com/workers/observability/issues/
- Logpush (the `logpush` key) and Tail Workers (`tail_consumers`):
  https://developers.cloudflare.com/workers/observability/logs/logpush/ and
  https://developers.cloudflare.com/workers/observability/logs/tail-workers/
- Real-time logs: a live tail carries request headers and `cf`.
  https://developers.cloudflare.com/workers/observability/logs/real-time-logs/
- Metrics and analytics: https://developers.cloudflare.com/workers/observability/metrics-and-analytics/
- Handlers: `fetch(request, env, ctx)` and `scheduled(controller, env, ctx)`, with
  `controller.scheduledTime`.
  https://developers.cloudflare.com/workers/runtime-apis/handlers/fetch/ and
  https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/
- Cron triggers: UTC, and the `crons` syntax.
  https://developers.cloudflare.com/workers/configuration/cron-triggers/
- Workers limits and pricing: Free plan CPU 10 ms per invocation, 1,000 subrequests to Cloudflare
  services per invocation, request body limits, and 5 cron triggers.
  https://developers.cloudflare.com/workers/platform/limits/ and
  https://developers.cloudflare.com/workers/platform/pricing/
- Durable Objects point-in-time recovery, the reason no Durable Object is used:
  https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
