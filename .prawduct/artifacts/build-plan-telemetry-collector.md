---
artifact: build-plan
version: 1
scope: telemetry-collector
branch: feature/telemetry-contribution
partition: "one isolated-worktree delegate builds chunk 01. Its tree is the new `collector/` directory, and nothing in `plugin/` or `.prawduct/` is touched. The integrator owns the schema-parity test under `tests/`, the Critic and the merge. Deploying needs the owner's Cloudflare account and is not delegated."
depends_on:
  - artifact: build-plan-telemetry-contribution
  - artifact: roi-audit-2026-10-02
governed_by:
  - artifact: architecture
    dispositions:
      - "local-first: governance has no network and no daemon → inapplicable, because the collector is not governance. It runs on the owner's Cloudflare account, no gate or verdict reads it, and the plugin ships none of its code"
      - "the governance runtime carries no third-party dependencies → conforms: the worker imports nothing, and its tests run on node's built-in runner. `wrangler` is deploy tooling, used only by the owner"
      - "every fact has one home → conforms: the allowlist is `plugin/lib/contribution_schema.json`, and the collector's copy is pinned to it byte for byte by a test"
  - artifact: security-model
    dispositions:
      - "content leaves a product only through a pinned, consented surface → conforms: this is the far end of that surface, and it accepts only what passes the allowlist"
  - artifact: api-contract
    dispositions:
      - "exit codes and error vocabulary are the contract → conforms in HTTP terms: 204 stored, 400 refused by the allowlist, 405/404 anything else. A refusal body names only the failing rule, never echoing input"
      - "versioned paths → conforms: the upload is `POST /v1/report`, so a schema 2 can live beside it"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals and stdout/stderr split → inapplicable, because the worker has no terminal"
      - "logging → departs, deliberately: `[DECISION: the collector emits no logs, traces or analytics (observability disabled, no console calls, no Logpush) | goal 2, knowing nothing about the contributor, outranks operability here, and a log line is exactly where an IP or arrival time would leak | owner can override]`"
---

# Build Plan: telemetry collector, wave 3 (#950)

## Problem

Wave 2's client (`build-plan-telemetry-contribution.md`) builds reports, but there is nowhere to
send them. The owner chose the host on 2026-10-03: Cloudflare, a Worker plus R2 on an account the
owner owns (audit § Owner decisions; #950).

## Success

- `POST /v1/report` stores a report that passes the allowlist and refuses anything else.
- Nothing about the sender or the request is persisted: no IP, no headers, no arrival time, no
  logs. The public code shows it.
- Stored reports are published as one bundle per UTC day. A bundle holds content only, sorted, so
  its order says nothing about arrival. Anyone can read the bundles.

## Out of scope

- Ingestion into `aggregate-review-stats`. That tool is #262's, and it does not exist yet. The
  public bundle format is its input contract, and #950's ingestion criterion moves to #262.
- Deploying. That is the owner's action on the owner's account (§ Deploy).
- Oblivious HTTP, rate limiting by IP (impossible without keeping IPs), and auth.

## Requirements Confidence: Medium

- [ASSUMPTION: reports wait in one SQLite-backed Durable Object until a daily cron writes them to
  R2 as one bundle and deletes them. Neither the DO rows nor the bundle carry a per-report time.
  Writing each report straight to R2 would give every object an upload timestamp | MED impact |
  owner can override]
- [ASSUMPTION: a bundle is JSON Lines, one canonical report per line, sorted by the line's bytes,
  at `bundles/<YYYY-MM-DD>.jsonl`, with `bundles/index.json` listing the days. Both are served by
  the worker's `GET` routes, so the bucket stays private | MED impact | owner can override]
- [ASSUMPTION: abuse control is a body-size cap and the allowlist. Poisoning cannot be detected by
  design, so the aggregator must use robust statistics | LOW impact | owner can override]
- [ASSUMPTION: Workers, Durable Objects, R2 and cron behave as their current docs say. Those facts
  are post-cutoff and fast-moving, so the delegate verifies each against the docs before relying on
  it | MED impact | resolved in chunk 01 step 0]

## Chunks

### Chunk 01: the worker, its config and its tests

new `collector/` holds the worker (`src/worker.js`, no imports), `wrangler.toml` (observability
off, no Logpush, the R2 binding, the DO binding and migration, a daily cron), a copy of the schema
(`schema.json`), tests runnable with `node --test`, and a README covering the privacy promise, the
endpoints and the owner's deploy steps.

**Foreign API:** Cloudflare Workers, Durable Objects, R2, cron triggers, wrangler config

Done when:
0. verify-api: each binding, handler signature and config key used is checked against Cloudflare's
   current docs, and the README cites what was read.
1. A report failing the allowlist gets a 400 and is not stored. Each refusal class has a test.
2. A stored report persists as its canonical bytes only. A test asserts that the stored value
   equals the canonical bytes, with no IP, header or time field anywhere in storage.
3. The worker never calls `console.*` and reads no request header beyond what it needs, the
   content length and type. A test greps the source.
4. `wrangler.toml` disables observability. A test parses the file and pins it.
5. The daily flush writes one sorted bundle, updates the index and empties the pending store.
   A flush with nothing pending writes nothing.
6. `GET` serves the index and bundles; every other method or path is 404 or 405.
7. `tests/test_collector_schema_parity.py` pins `collector/schema.json` to the plugin's schema byte
   for byte. The integrator writes this test.

## Deploy (owner)

Deploying is not a chunk, because nothing is built: the owner runs `wrangler deploy` from their
account and gives the endpoint URL. Wave 2 then pins that URL as the client's endpoint constant, and
a live round trip is recorded in `.prawduct/operator-verification.md`.

## Status

- [ ] Chunk 01: the worker, its config and its tests
