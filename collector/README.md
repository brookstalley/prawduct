# prawduct stats collector

A Cloudflare Worker that receives anonymous prawduct stats reports and publishes them once a day
as a public bundle. It exists to serve two goals, and when they conflict the second wins:

1. collect telemetry that improves prawduct;
2. know nothing about the contributor.

Sending is the client's business (`prawduct-hook contribute`, in `plugin/lib/contribution.py`).
Contribution is off by default, and a repository sends nothing until its owner opts in. The
collector only ever sees reports that a contributor has previewed byte for byte and approved.

## The privacy promise

**Stored:** the report's canonical bytes, plus a count of identical copies, and nothing else. A
report gets in only if it passes the allowlist (`schema.json`, a byte-for-byte copy of
`plugin/lib/contribution_schema.json`). Under that allowlist every value is an integer, a number on
its field's step, a band label, or a boolean, so a report has no room for free text.

**Not stored, anywhere, by this code:**

- the sender's IP address, or any header. The worker reads `content-type` and `content-length`
  and nothing else, and never touches the request's `cf` object. A fresh internal request carries
  only the canonical bytes to storage, so no header of the original request gets there.
- arrival time. No row has a timestamp. The pending tables are `WITHOUT ROWID`, because a rowid
  table numbers rows in insert order, and that order would be the arrival order.
- arrival order. A bundle is sorted by its lines' bytes.
- logs. The worker has no `console` call, and `wrangler.toml` turns off Workers Logs, invocation
  logs, traces, Issues and Logpush, and declares no tail consumers.

Each claim above is pinned by a test under `test/`, as § Tests shows.

## What Cloudflare still sees

The guarantees below hold **by policy, not by construction**. They depend on how the account owner
runs the account, and on Cloudflare.

- **The IP address, at the TLS edge.** Cloudflare terminates the connection, so it sees the
  sender's address while the request is open. The worker never reads it. A contributor who wants to
  hide it can send through a VPN or Tor, because the client honours `HTTPS_PROXY`.
- **Real-time logs.** Anyone with access to the account can open a live tail (`wrangler tail`, or
  **Logs → Live** in the dashboard). A live tail shows each request's headers and `cf` object while
  it streams, whatever `observability` says. Nothing is persisted unless the tail is running. The
  policy is never to tail this Worker.
- **Aggregate metrics.** Workers metrics record request counts, error counts and CPU and wall time
  per Worker, with no per-request detail.
- **Durable Object history (30 days).** Cloudflare backs SQLite Durable Objects with a durable change
  log that supports point-in-time recovery to any moment in the past 30 days
  (`getBookmarkForTime`). So for 30 days, code deployed on the account could reconstruct roughly
  when a pending row appeared, and reports deleted by a flush stay recoverable for that long. The
  docs offer no way to switch this off. On the Free plan SQLite is the only backend, and the
  key-value backend is closed to new namespaces. The rows themselves carry no time.
- **R2 object times.** R2 records an upload time for each object, so it knows when each *bundle*
  was written. That is when the flush ran, not when any report arrived.

The upgrade path to "by construction" is Oblivious HTTP (RFC 9458): a relay sees the IP but not the
content, and the collector sees the content but not the IP. It is deferred (see
`.prawduct/artifacts/roi-audit-2026-10-02.md` § Contribution design).

## Endpoints

| Method and path | Response |
|---|---|
| `POST /v1/report` | `204`, empty body: stored. `400`, `{"refused":"<rule>"}`: refused, nothing stored. |
| `GET /bundles/index.json` | `200` `application/json`: `{"days":["YYYY-MM-DD", …]}`, ascending. `404` before the first flush. |
| `GET /bundles/<YYYY-MM-DD>.jsonl` | `200` `application/x-ndjson`: that day's bundle. `404` if there is none. |
| the same paths, another method | `405`, with `Allow`. |
| anything else | `404`. |

`POST /v1/report` requirements:

- `content-type: application/json` (parameters such as `charset` are allowed);
- a body of at most **4 KiB**. The largest report schema 1 allows is about 720 bytes in canonical
  form, or about 1 KiB pretty-printed. So 4 KiB admits every valid report however it is spaced, and
  refuses padding before parsing it;
- UTF-8 JSON that passes the allowlist under the same rules as `contribution.validate`:
  - no key outside the schema, and every required key present;
  - enums matched type-strictly, so `0` is not `false`;
  - bands drawn from the band list;
  - integer fields given JSON integers, so `1.0` and `1e0` are refused;
  - numbers finite, within `[min, max]`, and within 1e-6 of a step;
  - booleans never accepted as numbers.

A refusal names the first failing rule, and never echoes input. The rules are `content-type`,
`too-large`, `json`, `not-object`, `unknown-key`, `missing-key`, `enum`, `band`, `not-number`,
`not-integer`, `range` and `step`. A `503` means storage was unavailable, and the client should
retry later.

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
- **The day names the flush, not the week the report covers.** The cron runs at 00:00 UTC, and a
  bundle holds whatever was pending then, roughly the previous day's arrivals. Each report carries
  its own window (`iso_year`, `iso_week`) and version (`plugin_major`, `plugin_minor`, `dev`).
  Aggregate on those, never on the bundle's day.
- **Poisoning cannot be detected.** A report carries no identity, so the aggregator must use
  robust statistics, such as medians and trimmed means, rather than trusting any single line.
- A later schema can be added under `POST /v2/report`. Every line carries `schema`.

## How the flush stays idempotent

The daily cron calls the Durable Object, which does the following:

1. **Claim.** In one transaction, it moves every pending row into a `claimed` table and records a
   random claim id with the flush's day. Reports that arrive during the rest of the flush land in
   `pending`, untouched, and wait for the next one.
2. **Publish.** It reads the day's bundle, if one exists. Unless that bundle's `customMetadata.claim`
   is already this claim's id, it merges in the claimed reports, re-sorts, and writes the bundle
   with the claim id. It then adds the day to the index, a set union.
3. **Drop.** It deletes the claimed rows and the claim.

The failure cases:

| Failure | Outcome |
|---|---|
| The cron fires twice | Nothing is pending the second time, so nothing is written. Overlapping runs inside one object share a single flush. |
| A second flush on the same day | It merges into that day's bundle and re-sorts it. |
| The bundle write fails | The cron run fails. The claim survives, and the next run finishes it into its original day's bundle before it claims anything new. |
| The bundle write succeeds, then the run dies before the drop | The retry finds the claim id already on the bundle, skips the merge, and finishes. No report is published twice. |
| Nothing is pending | Nothing is written: no bundle, no index update. |

The claim is the only time-shaped value ever stored. It is the flush's day, which is public as the
bundle's name, and it exists only while a flush is in progress.

## Deploy (owner)

These steps need the owner's Cloudflare account. The Workers Free plan covers SQLite Durable
Objects and one cron trigger. R2 usage at this volume sits inside R2's free tier, but the account
needs an R2 subscription: a checkout flow in the dashboard, under **R2**
(https://developers.cloudflare.com/r2/get-started/).

1. Install a current Wrangler. The `exports` field used here dates from June 2026, and
   `observability.issues` is documented from Wrangler 4.134.0. Check with
   `npx wrangler --version`, then run `npx wrangler login`.
2. Create the bucket: `npx wrangler r2 bucket create <name>`. Put `<name>` in `wrangler.toml` in
   place of `<R2_BUCKET_NAME>`. Leave the bucket private, with no `r2.dev` URL and no custom
   domain. The Worker serves the bundles itself.
3. Optional: set `account_id`, or `CLOUDFLARE_ACCOUNT_ID`, and add a `route` or custom domain if
   the collector should answer on your own hostname. Otherwise it answers on `workers.dev`.
4. From `collector/`, run `npx wrangler deploy`.
5. Confirm in the dashboard (**Workers & Pages → prawduct-collector**):
   - **Settings → Observability**: Workers Logs and Traces are disabled.
   - **Settings**: there is no Logpush and no Tail Worker.
   - **Logs**: nothing is persisted after a test request.
   - **R2 → the bucket → Settings**: public access is disabled.
6. Smoke test. Send `prawduct-hook contribute --json` output, or a hand-built valid report, with
   `curl -X POST -H 'content-type: application/json' --data-binary @report.json
   https://<host>/v1/report`, and expect `204`. `GET https://<host>/bundles/index.json` returns
   `404` until the first 00:00 UTC flush, then lists the day.
7. Give the endpoint URL to wave 2 (`build-plan-telemetry-contribution.md`), which pins it as the
   client's endpoint constant. A live round trip is then recorded in
   `.prawduct/operator-verification.md`.

**If your Wrangler predates `exports`:** replace the `[exports.PendingReports]` table with the
legacy form below. The two forms are mutually exclusive, and the `wrangler.toml` test pins
`exports`.

```toml
[[migrations]]
tag = "v1"
new_sqlite_classes = ["PendingReports"]
```

## Tests

```sh
node --test collector/test/
```

The tests need node 25 and nothing else: no npm install and no dependencies. The fakes in
`test/support/fakes.mjs` mirror the documented binding APIs:

- R2 `get` and `put`, with custom metadata;
- Durable Object `storage.sql.exec`, `toArray`, `one` and `transactionSync`, run on node's
  built-in SQLite, so the worker's SQL runs against a real engine;
- the Durable Object namespace's `getByName(...).fetch`.

Node 25 does not search a directory argument for test files. So `test/package.json` points the
directory at `test/all.mjs`, which loads every `*.test.mjs` beside it.

| Done-when | Test file |
|---|---|
| 1. Each refusal class is a 400, and nothing is stored | `refusals.test.mjs` |
| 2. Storage holds canonical bytes only: no address, header or time; parity with Python | `storage.test.mjs` |
| 3. No `console`, and no header read beyond content-type and content-length (source grep) | `source.test.mjs` |
| 4. `wrangler.toml` turns observability off | `wrangler.test.mjs` |
| 5. The flush sorts, updates the index, writes nothing when empty, and empties pending; idempotence | `flush.test.mjs` |
| 6. The GET routes, and 404/405 | `routes.test.mjs` |

The Python parity fixtures under `test/fixtures/` come from the real client, and are regenerated
with `python3 collector/test/fixtures/generate.py`. The hand-picked reports in
`test/support/reports.mjs` were produced by applying `contribution.to_step` to raw values, then
printing `json.dumps(report, sort_keys=True, separators=(",", ":"))`.

## Docs consulted (verify-api, 2026-10-03)

- Wrangler configuration: `name`, `main`, `compatibility_date`, `logpush`, `observability`,
  `triggers.crons`, `r2_buckets`, `durable_objects.bindings`, `exports` vs `migrations`,
  `tail_consumers`.
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
- Limits and pricing: Free plan CPU 10 ms per invocation, request body limits, and 5 cron triggers.
  https://developers.cloudflare.com/workers/platform/limits/ and
  https://developers.cloudflare.com/workers/platform/pricing/
- Durable Object class `exports`, the SQLite storage declaration that replaced `migrations`:
  https://developers.cloudflare.com/durable-objects/reference/durable-objects-migrations/ and the
  changelog,
  https://developers.cloudflare.com/changelog/post/2026-06-30-declarative-do-class-exports/
- Legacy `migrations` with `new_sqlite_classes`:
  https://developers.cloudflare.com/durable-objects/reference/durable-object-class-migrations-legacy/
- SQLite storage API: `sql.exec`, the cursor's `toArray`, `one` and `raw`, `transactionSync`,
  no `BEGIN` in `exec`, and PITR.
  https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/
- Durable Object base class, and the `fetch` handler on an object:
  https://developers.cloudflare.com/durable-objects/api/base/ and
  https://developers.cloudflare.com/durable-objects/best-practices/create-durable-object-stubs-and-send-requests/
- Namespace `getByName`: https://developers.cloudflare.com/durable-objects/api/namespace/
- Durable Objects pricing (Free plan: SQLite backend only) and limits (100 bound parameters, 2 MB
  rows): https://developers.cloudflare.com/durable-objects/platform/pricing/ and
  https://developers.cloudflare.com/durable-objects/platform/limits/
- R2 Workers API: `get`, `put` with `httpMetadata` and `customMetadata`, and `R2ObjectBody`.
  https://developers.cloudflare.com/r2/api/workers/workers-api-reference/
- R2 pricing and free tier: https://developers.cloudflare.com/r2/pricing/

**One fact the docs leave open.** Every current Durable Objects example extends `DurableObject`
from `cloudflare:workers`, and the base-class page calls it the class "which all Durable Objects
inherit from". The docs no longer show a plain class. They do say that RPC needs the base class,
and that the `fetch()` handler path remains supported. `PendingReports` is a plain class with a
`fetch()` handler, because the worker must import nothing so that node can load it. No page
states that plain classes are refused. The first `wrangler deploy` settles it, and it fails loudly
if they are, not silently. If it fails, change the class line to
`export class PendingReports extends DurableObject` with
`import { DurableObject } from "cloudflare:workers"`, and load the tests through a stub for that
import. The logic is unchanged, and so are the tests.
