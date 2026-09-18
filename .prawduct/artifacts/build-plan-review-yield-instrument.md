---
artifact: build-plan
version: 2
scope: review-yield-instrument
branch: feat/review-yield-instrument
partition: serial — one chunk
depends_on:
  - artifact: review-loop-nontermination-diagnosis
  - artifact: review-proportionality-assessment-2026-09-17
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint; cost = unit-cost × run-count, both levers → this plan does not itself move either lever. It ships the MEASUREMENT the levers will be graded by, which the next norm makes a precondition rather than a nicety"
      - "proportionality ratchets both ways; adding a control names the yield it expects AND EMITS THAT YIELD OBSERVABLY → ENGAGED, and it is the whole reason this chunk exists standalone. A control whose findings are printed and forgotten can never be retired on evidence, only defended on principle"
      - "review rigor is stage-keyed; the inner stage reports everything below the inner BLOCKING set as an observation → NOT ENGAGED by this plan, and that is the pivot recorded below: acting on this norm at the BOUNDARY is #830's work, and it departs from the norm's second half, so it needs its own decision and its own plan"
      - "state-file growth past its threshold is an advisory, never a hard block → inapplicable; no size gate changes"
  - artifact: architecture
    dispositions:
      - "every fact has one home; a fact is the whole predicate, not a token inside it → ENGAGED twice, and it changed the build both times. It is why this became an extension of `review-stats` rather than a new `tools/` script (a second home for severity, duration and observation aggregation over the same ledger), and why the tests landed in `tests/test_review_stats.py` rather than a parallel `tests/test_telemetry.py` (a second home for that module's tests)"
      - "goals and verification bind; prescribed method is advice → ENGAGED: the plan first prescribed a new tool and a new test file. Both were departed from, and both departures are recorded rather than taken silently"
      - "an independent reviewer never mutates the session it reviews → conforms; nothing gains a write path"
      - "authority fails closed; advice fails soft → ENGAGED: a bound this reader cannot interpret is REFUSED (exit 1) rather than filtered on as a bare string, because a window silently meaning something other than what was typed moves events between the halves of a before/after comparison and the delta is then attributed to whatever change was under test"
      - "local-first; no network, no third-party runtime dependency → conforms; stdlib only, one local file"
      - "prawduct is Python but never Python-specific → conforms; the ledger is read, never product code"
      - "prawduct guides and reviews; it never implements → conforms"
      - "the plugin writes nothing into a governed repo except its own state → conforms; read-only"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use a stable severity-prefix vocabulary → conforms: the window banner is a bare `WINDOW:` label on an operator-facing report, not a severity claim, and invents no prefix in the graded vocabulary"
      - "text emitted into a governed product names no prawduct-internal identifier → conforms; the output names severities and counts, no review id, chunk id or backlog number"
      - "the governance ledger has a single writer → conforms and is load-bearing: this chunk only ever READS it"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; `--json` keys are never repurposed → ENGAGED and satisfied: `window` and `remedies` are ADDED, `REPORT_SCHEMA_VERSION` moves 6 → 7 with them, and `TestJsonSchemaStability`'s pins are renegotiated in the open rather than worked around. No key removed, none repurposed"
      - "exit codes are the contract → ENGAGED: an uninterpretable bound exits 1, matching the command's existing bad-argument meaning; no exit code is repurposed"
      - "whole-surface semver; the internal CLI surface carries no per-subcommand version → conforms"
last_validated: 2026-09-18
---

## Requirements Confidence

**Level:** High. The question is fully stated, the inputs are one local append-only file whose
schema was read rather than recalled, and the acceptance is a reconciliation against figures already
written down on issue #829.

## Why this plan is one chunk, and what it is no longer

**This branch began as wave 1 of the review-economics program (#832 — "stop writing remedies for
NOTE-severity findings"), with this instrument as its first chunk. The owner stopped the second
chunk mid-build, and was right to.**

#832's lever is indirect: strip the remedy text so the NOTE label is not overridden by its payload.
Three things argued against it, and the third is the one that settled it.

1. It removes information rather than changing an incentive. A builder who still wants to fix the
   thing now has to re-derive the fix, which is more expensive, not less.
2. It is satisfiable by rating WARNING instead — which displaces work up a severity while every
   metric #832 names reads as success. That risk was written into this plan's own advisory section
   before the build started, which should have been the tell that the lever was a proxy.
3. **The direct lever is what a note COSTS, not what it says — and this repo has already proved it
   works.** At *inner* stage a note is not a finding at all: it is demoted to an observation,
   acceptable on the record for free, buying no round. That single change took `verify-resolutions`
   from **2.04** non-blocking findings per round to **0.09** (measured 2026-09-18, split at
   `cdcac17d`). The 87% of notes that still generate round-buying work — **992 of 1,141**
   post-2026-08-04 — come from `cumulative`, the boundary stage, where the full severity table still
   runs.

Extending that demotion to the boundary is **#830** ("severity should select the CHANNEL, not just
the label"), not #832. It is a bigger change than #832 because it departs from a ratified norm —
`nonfunctional-requirements.md`: *the boundary stage runs the full severity table and is never
skipped* — so it needs a recorded decision or an amendment, and a plan of its own.

**What survives into that work is this chunk**, unchanged and independently useful: #830's third
acceptance criterion is *"some record makes 'did a note ever prevent a blocker' answerable from the
ledger"*, and a date window plus a remedy dimension on `review-stats` is where that answer starts.
It is also the before-measurement any of #829–#834 will be graded against, and a before-measurement
taken after the change is no measurement at all.

`[DECISION: ship the instrument alone under its own scope and re-plan #830 separately | the
instrument is complete, green and useful under every option on the table, while the contract change
it was built to grade is now the wrong change; holding it hostage to a re-plan buys nothing and
loses a measurement that only gets less useful as the corpus moves | user can veto]`

## Routes departed from, recorded rather than taken silently

Both are departures from this plan as first written, under `architecture.md` *goals and verification
bind; prescribed method is advice*. **Neither abandoned path is written in backticks anywhere in a
chunk body**: record-lint reads a backticked path there as a declared deliverable, and declaring a
file that was deliberately never built is a BLOCKING ref-drift finding — which is exactly what the
first draft of this plan earned.

1. **A new era-split script under `tools/` became an extension of `review-stats`.** Reading the
   surface first showed the new tool would be a second home for severity, duration and observation
   aggregation over the same ledger — the exact norm this plan disposes of under `architecture.md`.
2. **A new telemetry test module became an extension of the existing test home.** The plan asserted
   the module had *no test file today*. False — 685 lines of one, including the
   `TestJsonSchemaStability` pins this change had to renegotiate. The claim came from a
   `grep -rln … | head` whose output was cut below the fold; the slice is invisible in what you read
   back.

## Status

- [x] Chunk 01: A window and a remedy dimension on `review-stats`

---

## Chunk 01: A window and a remedy dimension on `review-stats`

**Type:** cumulative-final
**Description:** `review-stats` already aggregates severity, actionable share, observations and
durations over the governance ledger. It could not slice by date, and it had no notion of whether a
finding ships a fix plan. Both gaps are filled here.

**Deliverables:**
- `plugin/lib/telemetry.py` — `--since` / `--until` window bounds, the remedy dimension, the human
  rendering of both, `REPORT_SCHEMA_VERSION` 6 → 7.
- `plugin/bin/prawduct-hook` — the `review-stats` usage string.
- `tests/test_review_stats.py` — the module's existing test home, extended.
- new `plugin/lib/timewindow.py` — the window predicate's one home, shared with
  `tools/pr-review-yield.py`; and new `tests/test_window_bounds_one_home.py`, its agreement pin.

**Done when — all met:**
1. Window bounds accept the forms `tools/pr-review-yield.py` accepts, and its period cases are
   ported rather than re-derived. **Met, and then superseded by the cumulative review** — the two
   instruments no longer hold two copies at all. `plugin/lib/timewindow.py` is the one home and both
   import it, because three reviewers found the copies had *already* diverged on the lower bound.
   Porting was the plan's goal; sharing is strictly stronger, and the plan's own deliverable list is
   updated rather than left describing the weaker outcome.
2. The remedy dimension counts three outcomes: present, blank, and **absent**. **Met, and it was a
   real defect in the first cut** — the PR reviewer's findings carry `{goal, severity, file, line,
   summary}` with no remedy key, so folding absence into "wrote no remedy" reported that role at 0%,
   a claim its schema cannot support. `rate` is null for such a population.
3. A control that must fail: two corpora identical but for remedy presence report different rates.
   **Met.**
4. Additive only; existing `--json` keys survive and the version moves with the shape. **Met.**
5. Mutation-verified. **Met, on the second attempt** — the first sweep returned pytest's usage-error
   code for all eight subprocesses, so six "kills" were false and only the deliberate survivor
   control made that visible. The re-run found a genuine survivor: `--since` never parsed a full
   timestamp, so a zoned bound was string-compared against `...Z` stamps. `_precedes_lower` now
   mirrors `_exceeds_upper`.
6. Real-corpus reconciliation. **Met** — `--since 2026-08-04` reproduces #829's recorded figures
   exactly (pre 25/187/257, post 74/14/12; totals 99 blocking / 470 non-blocking), and the halves
   partition 1020 events as 469 + 551.

**Deliberately not a test:** the real ledger is gitignored, so a test reading it would be red where
it can see and green in CI — the environment-shaped hole that pattern always leaves. The
reconciliation is a verification step, recorded above and in the commit.

**Known coverage bound, stated rather than inherited:** `tests/test_review_stats.py` now covers the
two surfaces added here. The rest of `telemetry.py` — `top_files`, the learning tally, `round_price`
— is covered as it was before, which is partially. This chunk did not widen that and does not claim to.
