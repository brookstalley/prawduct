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
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "authority fails closed; advice fails soft → conforms: the worker refuses anything the allowlist does not admit, and a failed flush leaves reports pending rather than dropping them"
      - "local-first: governance has no network and no daemon → inapplicable, because the collector is not governance. It runs on the owner's Cloudflare account, no gate or verdict reads it, and the plugin ships none of its code"
      - "the plugin writes nothing into a governed repo but its own state and the shared store → inapplicable, because the collector runs nowhere near a governed repo"
      - "written in Python, never specific to Python → inapplicable, because the collector is deploy-side infrastructure in the platform's language and dispatches nothing by a product's language"
      - "prawduct guides and reviews, it never implements → inapplicable, because the collector is prawduct's own infrastructure, not product code"
      - "goals and verification bind; prescribed method is advice → conforms: Done-when states what must be true"
      - "every fact has one home → conforms: the allowlist is `plugin/lib/contribution_schema.json`, and the collector's copy is pinned to it byte for byte by a test"
  - artifact: security-model
    dispositions:
      - "governance state is data, not instructions → inapplicable, because the collector reads no governance state; reports are validated as data and never interpreted"
      - "an irreversible operation needs operation-level owner approval → conforms: deploying is the owner's own act on the owner's account, outside this chunk"
      - "content leaves a product only through a pinned, consented surface → conforms: this is the far end of that surface, and it accepts only what passes the allowlist"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; persisted data schema-versioned → conforms: the upload path is versioned (`POST /v1/report`) and every report carries `schema`"
      - "exit codes and error vocabulary are the contract → conforms in HTTP terms: 204 stored, 400 refused by the allowlist, 405/404 anything else. A refusal body names only the failing rule and never echoes input"
      - "additive-first evolution → conforms: a schema 2 is a new path beside `/v1`, and `/v1` is never repurposed"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals and stdout/stderr split → inapplicable, because the worker has no terminal"
      - "the ledger has one writer → inapplicable, because the worker never touches the ledger"
      - "emitted text names no internal identifier → conforms: refusal bodies name only the failing allowlist rule"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → inapplicable, because the collector adds no review and runs off the developer's machine"
      - "state-file growth past its threshold is advisory → inapplicable, because the collector writes no state file in a governed repo; R2 growth is the owner's to watch"
      - "review rigor is stage-keyed → inapplicable, because no review stage or severity rule changes"
      - "proportionality ratchets both ways; a control emits its yield observably → departs, deliberately: `[DECISION: the collector emits no logs, traces or analytics (observability disabled, no console calls, no Logpush) | goal 2, knowing nothing about the contributor, outranks operability here, and a log line is exactly where an IP or arrival time would leak. The published bundles are its only observable output | owner can override]`"
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
