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

1. **Claim.** It lists `pending/`, following R2's `truncated`/`cursor` pagination, and takes up to
   `MAX_CLAIM` (900) keys. It writes them, with a random claim id and the day, to
   `claims/current.json`. The write is create-only (`onlyIf` with `If-None-Match: *`), so when
   another run claimed first, this run finishes that claim instead of taking its own.
2. **Publish.** It reads the day's bundle, if one exists. Unless that bundle's
   `customMetadata.claim` is already this claim's id, it reads every claimed object and keeps only
   canonical, allowlisted bytes. It merges them into the bundle, keeping duplicates, sorts, and
   writes the bundle with `customMetadata: {claim: <id>}`. It then adds the day to
   `bundles/index.json`, a set union.
3. **Clean up.** Only after the bundle write succeeds, it deletes the claimed pending objects, in
   batches of up to 1,000 keys, the most R2 takes per call. It then deletes the claim, after
   checking that the claim is still its own.

**Where the record lives.** A claim manifest under `claims/` holds which pending keys a bundle
contains. The bundle's own custom metadata holds only the id of the last claim merged into it. A
key list can't go in the bundle's metadata, because R2 caps custom metadata at 8,192 bytes, about
90 keys. A run that finds a manifest finishes it, and the id on the bundle stops a claim from being
merged twice.

The failure cases:

| Failure | Outcome |
|---|---|
| Nothing is pending | Nothing is written: no claim, no bundle, no index update. |
| The cron fires twice | The second run finds nothing pending and writes nothing. |
| A second flush on the same day | It merges into that day's bundle and re-sorts it. |
| The bundle write fails | The run fails, and no pending object is deleted. The next run finishes the claim into its original day's bundle. That run claims nothing new; reports that arrived since wait one more run. |
| The run dies after the bundle write, before or during the deletes | The next run finds the claim, sees the claim id on the bundle, skips the merge, and finishes the deletes. No report is published twice. |
| Two runs overlap | Only one creates the claim. The other finishes that same claim, and the merge is deterministic, so both write the same bundle. |
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
2. Create the bucket: `npx wrangler r2 bucket create <name>`. Put `<name>` in `wrangler.toml` in
   place of `<R2_BUCKET_NAME>`. Leave public access, event notifications and bucket locks off
   (§ What Cloudflare still sees).
3. Optional: set `account_id`, or `CLOUDFLARE_ACCOUNT_ID`, and add a `route` or custom domain if
   the collector should answer on your own hostname. Otherwise it answers on `workers.dev`.
4. From `collector/`, run `npx wrangler deploy`.
5. Confirm in the dashboard (**Workers & Pages → prawduct-collector**):
   - **Settings → Observability**: Workers Logs and Traces are disabled.
   - **Settings**: there is no Logpush and no Tail Worker.
   - **Logs**: nothing is persisted after a test request.
   - **R2 → the bucket → Settings**: public access is disabled, and there are no event
     notifications and no bucket lock rules.
6. Smoke test. Send `prawduct-hook contribute --json` output, or a hand-built valid report, with
   `curl -X POST -H 'content-type: application/json' --data-binary @report.json
   https://<host>/v1/report`, and expect `204`. One object appears under `pending/` with no custom
   metadata. `GET https://<host>/bundles/index.json` returns `404` until the first 00:00 UTC flush,
   then lists the day, and `pending/` is empty again.
7. Give the endpoint URL to wave 2 (`build-plan-telemetry-contribution.md`), which pins it as the
   client's endpoint constant. A live round trip is then recorded in
   `.prawduct/operator-verification.md`.

**Check on the first live flush:** the binding docs say R2's `onlyIf` accepts every conditional
header but `If-Range`. The wildcard form, `If-None-Match: *`, is stated only for the S3 API, in R2's
changelog entry of 2022-07-30. The fake models it, but only a live run proves the binding honours
it. If R2 ignored the precondition, the claim would lose its exclusivity, and
only overlapping runs would be exposed, which a daily cron makes unlikely.

## Tests

```sh
node --test collector/test/
```

The tests need node 25 and nothing else: no npm install and no dependencies. `test/support/fakes.mjs`
is an in-memory R2 bucket shaped to the documented binding:

- `get` returns a body, `text()`, `json()`, `customMetadata`, `httpMetadata` and `uploaded`;
- `put` takes `httpMetadata`, `customMetadata` and `onlyIf` with `If-None-Match: *`;
- `delete` takes a key or up to 1,000 keys;
- `list` takes `prefix`, `cursor` and `limit`, returns pages in lexical order with `truncated` and
  `cursor`, and can be made to page small.

Node 25 does not search a directory argument for test files. So `test/package.json` points the
directory at `test/all.mjs`, which loads every `*.test.mjs` beside it.

| Done-when | Test file |
|---|---|
| 1. Each refusal class is a 400, and nothing is stored | `refusals.test.mjs` |
| 2. Storage is canonical bytes in one object: no metadata, no address, header or time in key, body or metadata; parity with Python | `storage.test.mjs` |
| 3. No `console`, and no header read beyond content-type and content-length (source grep) | `source.test.mjs` |
| 4. `wrangler.toml` turns observability off and binds only R2 | `wrangler.test.mjs` |
| 5. The flush sorts, keeps duplicates, updates the index, writes nothing when empty, and empties pending; idempotence, pagination and the cap | `flush.test.mjs` |
| 6. The GET routes, and 404/405 | `routes.test.mjs` |

The Python parity fixtures under `test/fixtures/` come from the real client. Regenerate them with
`python3 collector/test/fixtures/generate.py [PLUGIN_DIR]`, where `PLUGIN_DIR` defaults to this
repository's `plugin/`. The script refuses to run unless that plugin's
`lib/contribution_schema.json` is byte-identical to `collector/schema.json`. The hand-picked
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
  - `R2Object.uploaded`;
  - `onlyIf` takes an `R2Conditional` or `Headers` with every conditional header but `If-Range`.

  https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
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
