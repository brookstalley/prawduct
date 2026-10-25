---
artifact: build-plan
version: 2
scope: review-stats-dispositions
branch: feature/941-review-stats-dispositions
partition: serial — one chunk; the join, the shared rate helper and the reader share one shape
last_validated: 2026-10-25
---

## Goals

**Response taken:** Proceed, citing #941 (`stage:ready`; the owner chose Option A in the issue
body, which supersedes `documentation/issues/941-design.md` where they differ).

**Product:** `review-stats` groups reviews by role × model × mode, scope and stage, but its only
yield figure is `actionable_rate`: what a reviewer *labelled*. This adds what the builder *did*
with each blocking/warning finding, from the evidence store's disposition and resolution facts,
by the rule `stats` and `render-dispositions` already use. It also says how many reviews it could
join, so a rate over a subset is never read as a rate over the whole.

**Architecture:** `review_stats()` reads the store once and turns it into a pure-data outcome map
`{fact_id: {fid: outcome}}` through `stats.finding_outcome`. `aggregate_review_stats` stays pure
and takes that map as an argument. The acted/answered arithmetic moves out of `stats._finish` into
one exported `stats.acted_on`, which both reports call.

**Inferences (not settled by the issue; mine):**
- The status lives in two places. A top-level `dispositions` header carries
  `{status, as_of}` or `{status, reason}`, and every stat block carries a `dispositions` block
  with the same `status`. `as_of` is the moment of the store read.
- A store that is `empty` (no file yet) counts as unavailable, the same as no git or an
  unreadable file. The issue lists "absent" among the unavailable cases.
- A finding in a joined review that has no `fid` counts as `other`, which matches `stats`.
- The human line puts the outcome first in the yield part of the fragment. The old
  `actionable N%` text becomes `severity-actionable N%`, and the reason it is unavailable is
  printed once in the header, not on every line.
- The human line also names the undispositioned count. On this repo's real store (2026-10-25)
  the rate is 93% of 1,884 answered, and 360 findings are unanswered. A rate printed without
  them reads as a verdict on findings nobody has answered yet. The issue keeps them visible in
  `by_outcome`; this keeps them visible on the line people read.

## Status

- [x] Chunk 01: review-stats joins the evidence store; one acted-on rule shared with `stats`

Context: Single chunk. Done when: `tests/test_review_stats.py` and `tests/test_stats.py` pass,
`plugin/docs/governance-telemetry.md` § review-stats documents the block and schema 9, a change
fragment exists, the develop `-dev.2` bump rides this branch, and `/prawduct:critic` passes.

## Chunk 01: review-stats joins the evidence store

**Delivers:**
1. `stats.acted_on(counts) -> (acted, answered, rate)`; `stats._finish` calls it.
2. `telemetry._extract_row` returns `fact_id` (str or None); findings keep their `fid`.
3. `telemetry.aggregate_review_stats(..., dispositions=None)`: per-group `dispositions` block
   (`status`, `joined_reviews`, `unjoined_reviews`, `by_outcome` over `stats._OUTCOMES`,
   `answered`, `acted_on_rate`) over blocking+warning findings of joined reviews, or
   `{status: unavailable, reason}`. A top-level `dispositions` header.
4. `telemetry.review_stats`: one `evidence.read_facts`, lazy imports, builds the outcome map.
5. Human line: `acted on N% of M answered blocking/warning findings, U undispositioned (J of R
   reviews joined) | severity-actionable P%`; the header line states `as_of` or the reason it is
   unavailable.
6. `REPORT_SCHEMA_VERSION` 8 → 9; the doc's § review-stats and `--json` contract updated.
7. Version bump to 3.7.3-dev.2 (four files); change fragment.

**Acceptance:** the issue's list, verbatim:
- Red first: a `fixed` twin and an `accept` twin both give `actionable_rate` 1.0, but
  `acted_on_rate` 1.0 vs 0.0 (fails on develop).
- For one fixture, `review-stats` and `stats` give the same outcome tally per finding.
- An event with no `fact_id`, or one whose `fact_id` is missing from the store, is counted in
  `unjoined_reviews`, and rates are computed over the rest only.
- A missing or unreadable store gives `status: unavailable` with a reason, and the severity
  fields are byte-identical to a run with the join disabled.
- An event outside `--since/--until` is in neither the numerator nor the denominator.
- `stats` output is unchanged after the helper extraction (existing tests pass unedited).
- Schema 9 and the doc agree.
