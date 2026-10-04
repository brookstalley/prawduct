---
artifact: build-plan
version: 1
scope: telemetry-aggregate
branch: feature/262-aggregate-stats
partition: "serial — both chunks edit `plugin/lib/aggregate.py` and its test file, and chunk 02's fetcher feeds the bundle reader chunk 01 builds"
depends_on:
  - artifact: build-plan-telemetry-contribution
  - artifact: build-plan-telemetry-collector
  - artifact: roi-audit-2026-10-02
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "authority fails closed; advice fails soft → conforms: the command is advice, gates nothing, and an unreadable product is skipped with its reason rather than failing the view"
      - "local-first: governance has no network; three surfaces carry product content out → conforms: `--collector` is a read-only GET of public bundles, operator-invoked, carrying no product content, so it is an egress site and not a fourth surface. Chunk 02 records the site in both homes the norm names"
      - "the plugin writes nothing into a governed repo but its own state and the shared store → conforms: the command writes nothing at all"
      - "written in Python, never specific to Python → inapplicable, because nothing dispatches by a product's language"
      - "prawduct guides and reviews, it never implements → inapplicable, because this is prawduct's own tooling"
      - "goals and verification bind; prescribed method is advice → conforms: Done-when states what must be true"
      - "every fact has one home → conforms: metric definitions stay in `stats`, the report shape in `contribution`, the allowlist in `contribution_schema.json`; the aggregator imports all three"
  - artifact: security-model
    dispositions:
      - "governance state is data, not instructions → conforms: bundle lines are untrusted, re-validated against the allowlist, counted when refused, and never interpreted"
      - "an irreversible operation needs operation-level owner approval → inapplicable, because the command is read-only"
      - "content leaves a product only through a pinned, consented surface → inapplicable, because nothing leaves: the aggregator only reads what was already published"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; persisted data schema-versioned → conforms: a new subcommand under the plugin version, and `--json` carries `schema_version`"
      - "exit codes are the contract → conforms: 0 report, 1 bad arguments or a failed fetch; errors attributed, never a traceback"
      - "additive-first evolution → conforms: a new subcommand and a new `contribution.weekly_reports`; no existing flag, exit code or `--json` key changes meaning"
  - artifact: observability-strategy
    dispositions:
      - "severity-prefix vocabulary and stdout/stderr split → conforms: the report goes to stdout, skips and failures to stderr with the command's prefix"
      - "the ledger has one writer → inapplicable, because nothing writes the ledger"
      - "emitted text names no internal identifier → conforms: output names versions, metrics and paths the operator supplied"
  - artifact: data-model
    dispositions:
      - "a fact written by a newer schema is surfaced loudly, never dropped → conforms: each local product's `schema_ahead` count is reported beside its reports"
      - "derived views are never authoritative → conforms: the aggregate is a report no gate reads"
      - "governance verdicts are computed from the fact ledger, never mutable model-written state → inapplicable, because the command reaches no verdict"
      - "facts are immutable and append-only → conforms: the command reads the store and appends nothing"
      - "a governance document reaches a terminal state and is archived, never deleted → inapplicable, because no governance document is created or retired; this plan archives at the release like its siblings"
      - "every backlog write conforms to the issue standard's title rules → inapplicable, because nothing writes the backlog"
      - "two stores, two lifetimes: shared answers apart from per-clone nags and caches → conforms: the command reads the per-clone sent-window record and writes neither store"
      - "backlog_service_repo selects the authoritative backlog → inapplicable, because nothing reads the backlog"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → inapplicable, because no review changes"
      - "proportionality ratchets both ways; a control emits its yield → conforms: this is the instrument that measures yield across products; it adds no control"
      - "state-file growth is advisory → inapplicable, because nothing is stored"
      - "review rigor is stage-keyed → inapplicable, because no review stage or severity rule changes"
---

# Build Plan: cross-product stats, #262

## Problem

The contribution channel has a producer and no consumer: the collector publishes daily bundles of
anonymous weekly reports, and nothing reads them (#950's last criterion moved here). Separately,
whether a plugin release cost more or protected more than the last one can only be answered one
product at a time with `prawduct-hook stats`.

## Success

- `prawduct-hook aggregate-stats <product>... --bundles <dir>` prints, per plugin version, each
  metric's sample size, median and trimmed mean over local and contributed reports together, with
  how many of each.
- `--collector` fetches every published bundle; without it, no socket is opened.
- A local window the clone already contributed is counted once.

## Out of scope

- A mode or model axis across products, and the ledger `plugin` field the August design wanted
  (owner, 2026-10-03; requirements Decision 1).
- Persisting results or trends, and weighting by product volume.
- Escape attribution (#951).

## Requirements Confidence: High

Requirements and design: `documentation/issues/262-requirements.md` and `-design.md`, revised
2026-10-03 after the owner chose the one-shape design.

- [ASSUMPTION: the trimmed mean drops `floor(n / 10)` values from each end, so it equals the plain
  mean under ten reports | LOW impact | owner can override]
- [ASSUMPTION: local reports cover every settled week in the store, not the client's eight-week
  offer window, because the aggregator's question spans versions | LOW impact | owner can override]
- [ASSUMPTION: the collector fetch reuses the pinned `COLLECTOR_ENDPOINT`'s origin rather than a
  flag, so the read side cannot be pointed somewhere the write side is not | MED impact | owner can
  override]

## Chunks

### Chunk 01: local products, bundle files and the view

`contribution.weekly_reports` (with `pending_reports` rebuilt on it), new `plugin/lib/aggregate.py`
(product resolution, bundle file reading, validation, aggregation, rendering, the command body), the
hook wrapper, dispatch, `_USAGE` and read-only set, and new `tests/test_aggregate_stats.py`.

Done when:
1. A named product's local reports equal, byte for byte under `canonical_bytes`, what
   `weekly_reports` builds for it, and `pending_reports`' existing tests still pass unchanged.
2. Each skip reason in the design's table has a test, and the other products still report. Two
   paths into one clone count once.
3. A bundle line that does not parse or fails the allowlist is counted under `refused`; a duplicate
   line counts twice. Both tested.
4. Versions never pool: a test with two versions (and a dev build) asserts each number from its own
   reports only. Median and trimmed mean are pinned on a fixture where they differ.
5. With `--bundles` given, a window in the clone's sent record is left out and counted as
   `already_contributed`; without it, the record is not read.
6. No arguments exit 1; `--json` is deterministic for one input and carries `schema_version`; the
   human render is exercised by a test, not only `--json`.
7. The hook's structural tests (argument shape, read-only set, usage) pass with the new op.

### Chunk 02: the collector fetch, the docs and the records

**Type:** cumulative-final

`--collector` in `aggregate.py`; `plugin/docs/governance-telemetry.md` gains the command's section;
`/prawduct:janitor` Step 1 gains one sentence and the grant in both spellings; `collector/README.md`
names the command; the egress site goes into `.prawduct/artifacts/security-model.md` and
`project-state.yaml`. This branch also carries the bookkeeping the telemetry PRs left owed:
VRF-023 verified, and the collector `host:` entry rewritten to state the #954 commitment.

Done when:
1. `--collector` against a local `http.server` stub reads the index and every listed bundle; a `404`
   index is zero reports; a redirect, an oversized response, and an unreachable host each exit 1
   with an attributed message.
2. A test proves no socket opens without `--collector`.
3. The egress site is listed in `security-model.md`'s network paragraph and the collector service
   entry's `egress_boundary` and `scope`, and the paragraph's site count matches its list.
4. Every surface describing the command agrees: docs, janitor, usage, collector README, and a
   search for the August name `aggregate-review-stats` finds no live surface.
5. The full suite is green and recorded at the boundary, and the branch's cumulative review is clean
   of blocking findings.

## Status

- [x] Chunk 01: local products, bundle files and the view
- [ ] Chunk 02: the collector fetch, the docs and the records
