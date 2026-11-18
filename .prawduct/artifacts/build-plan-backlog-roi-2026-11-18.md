---
artifact: build-plan
version: 2
scope: backlog-roi-2026-11-18
branch: integration/backlog-roi-2026-11-18
base: develop
working-branches: []
partition: "ten builders in isolated worktrees, one per chunk, on disjoint files; Opus-class for chunks 01-05 and 07-09 (design judgment inside settled designs), Sonnet-class for 06 and 10 (fully specified). Shared seams have one owner each — plugin/lib/critic_consolidate.py: chunk 02 owns next_action_line, merge_findings, fact_to_cache_record and the consolidation call site that renders next_action; chunk 03 owns begin_review's exit-1 refusals and _widened_fallback_mode; chunk 04 owns carried_blocking, account_for_prior_blockers_directive and _round_budget_verdict. plugin/lib/coverage.py: chunk 02 owns the format_branch_rounds neighbourhood, chunk 04 owns any branch_review_ids extraction. plugin/lib/gates.py: chunk 04 owns the superseded-blocker remedy, chunk 07 owns _drop_other_sessions_commits. plugin/lib/briefing.py: chunk 04 owns _summarize_critic_findings, chunk 05 owns the backlog warming/stuck branch. plugin/bin/prawduct-hook: chunk 08 owns cmd_stop; any other chunk edits only its own subcommand handler. plugin/methodology/building.md: chunk 09 only. plugin/skills/critic/SKILL.md and review-cycle.md: chunk 03 only. Change-log fragments: one file per chunk, named by its scope. Cross-file prose budgets and the merge are the coordinator's; the coordinator integrates, runs the suite once, and governs"
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms; chunk 05 turns a silent cache miss into `unchecked`, chunk 06 makes decode loss visible as a warning, chunk 08's new signal is a dismissible advisory, never a refusal (owner ruling 2026-09-19 on tax)"
      - "local-first → conforms; chunk 08's gh lookup reuses the existing cmd_stop egress through one extracted helper, adding no new egress site"
      - "every fact has one home → conforms; chunk 04 makes the branch review set one owner for render, write and read; chunk 02 derives `check` in one registry"
      - "guides and reviews, never implements → conforms"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; chunk 02 derives `check` at consolidation, never reviewer-written"
      - "facts immutable and append-only → conforms; no fact is rewritten; chunk 02's field is additive and SCHEMA_VERSION does not move"
      - "derived views never authoritative → conforms; chunk 04 replaces newest-fact views with fact composition"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract → conforms; chunk 03 keeps exit 1 and exit 6, adding a `fallback_mode` key only"
      - "additive-first evolution → conforms; new keys and new queries only"
depends_on:
  - plugin/lib/plan_status.py
  - plugin/lib/critic_consolidate.py
  - plugin/lib/coverage.py
  - plugin/lib/dispositions.py
  - plugin/lib/gates.py
  - plugin/lib/briefing.py
  - plugin/lib/pr_gate.py
  - plugin/lib/backlog/sync.py
  - plugin/lib/backlog/snapshot.py
  - plugin/lib/backlog/encode.py
  - plugin/lib/stranded_work.py
  - plugin/lib/record_lint.py
  - plugin/methodology/building.md
last_validated: 2026-11-18
---

## Goals

**Response taken:** Proceed, citing it. The owner asked (2026-11-18) for every mid-to-high ROI
backlog item to be addressed with delegated builders on an integration branch, without waiting
on them short of an irreversible decision. Selection rule: `stage:ready` items with a settled
design or a fully specified proposed change, impact M with effort S/M or impact L with effort M,
excluding date-gated re-runs (#981, #987, #1035, #1036), owner-run measurements with private
inputs, live experiments (#1130, #984), heavy-suite work (#1015, #757), and items that would add
blocking tax against the 2026-09-19 ruling (#855). Items deferred for file collision with this
wave, not for ROI: #830 and #847 (dispositions/critic_consolidate seams owned by chunks 02 and 04),
#606 (ledger.py, chunk 02), #723 (gates remedy prose, chunk 04).

**Product:** each item's own acceptance list, as the issue states it.

**Out of scope:** the chunk-credit family's requirements-stage halves (#1141, #1198).

## Verification Strategy

Each fix is red first: a test that fails on develop at cda8c2f9 and passes after. Builders run
only the tests for their files plus any prose budget test their edits touch, through
`testament run --json -- <files>`. The full suite runs once, on the integrated branch.
#1144 (watch the first live reviewer-less `/prawduct:pr`) is discharged by this plan's own PR.

## Build Chunks

### Chunk 01: A merged or verified chunk is credited (#1191, #1199)

- **Description:** per-chunk credit in `plan status` composes a verify-resolutions fact that
  extends a chunk review's head tree to the chunk commit's tree (#1191), and chunk proposal reads
  chunk-naming subjects when the interval falls back to the merge-base (#1199).
- **Depends on:** none
- **Deliverables:** fixes in `plugin/lib/plan_status.py` (and the span/proposal code it calls)
  with fixture-repo tests reproducing each report red.
- **Acceptance criteria:** both issues' Expected sections hold.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: Consolidation carries the round tally and a derived control check (#815, #548)

- **Description:** #815's `branch_rounds_clause` on `next_action`; #548's `control_checks.py`
  registry, `check` field on facts, cache, ledger `review.pr` rows and `pr-review-yield.py`.
- **Depends on:** none
- **Deliverables:** as each issue's Proposed change.
- **Acceptance criteria:** each issue's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: Every verify-resolutions demotion names a covering mode (#662)

- **Description:** the exit-1 anchor refusals return `fallback_mode` from the one recommender
  (renamed `covering_fallback_mode`), with the `BASE_AT_HEAD_COVERED` arm; the skill prose stops
  telling the reader to apply the property by hand.
- **Depends on:** none
- **Deliverables:** as #662's Proposed change.
- **Acceptance criteria:** #662's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 04: The branch's review set replaces the newest-fact view (#334)

- **Description:** one `branch_review_ids` owner feeds `render-dispositions`, the verify
  roll-call (`carried_blocking`), the gate's superseded remedy and the handoff summary.
- **Depends on:** none
- **Deliverables:** as #334's Proposed change.
- **Acceptance criteria:** #334's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 05: Backlog cache misses and failed refreshes are visible (#1195, #755)

- **Description:** `closes-unresolved` only for an id the backlog cannot resolve, a cache miss
  reads `unchecked` naming `sync --rebuild` or falls back to lookup, and incremental sync does not
  leave the cache silently partial (#1195); every detached refresh leaves a durable attempt
  record and the briefing says stuck, not warming (#755, design `documentation/issues/755-design.md`).
- **Depends on:** none
- **Deliverables:** fixes with tests.
- **Acceptance criteria:** both issues' Expected / Acceptance lists.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 06: Backlog decode degradations warn (#745)

- **Description:** the three degradations each emit a decode-envelope warning; returned values
  do not change.
- **Depends on:** none
- **Deliverables:** fixes in `plugin/lib/backlog/encode.py` with tests.
- **Acceptance criteria:** #745's Expected.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 07: The Stop span keeps commits of Bash-written files (#1184)

- **Description:** authorship in `_drop_other_sessions_commits` widens beyond Edit-family tools;
  each drop is recorded as a stop observation; the narrowed docs are widened to match.
- **Depends on:** none
- **Deliverables:** fix with a test committing a Bash-written file from a terminal.
- **Acceptance criteria:** #1184's Proposed.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 08: A pushed, finished branch with no PR is surfaced (#843)

- **Description:** the pushed-branch arm per `documentation/issues/843-design.md`, through an
  extracted `gitstate.pr_exists_for_branch` shared with `cmd_stop`; advisory, never blocking.
- **Depends on:** none
- **Deliverables:** as the design's remaining arm.
- **Acceptance criteria:** #843's Remaining section.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 09: Late requirements have a home; gate and review may run together (#1034, #678)

- **Description:** #1034's record shape, `late_requirements.py` reader, `late-requirement-record`
  lint and `building.md` step; #678's concurrency statement for the test gate and the Critic,
  after verifying from code whether a `test-evidence record` write voids a live review.
- **Depends on:** none
- **Deliverables:** as each issue's Proposed change.
- **Acceptance criteria:** each issue's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 10: Research tooling for the native-review stop and record findings (#1197, #771)

- **Description:** the blind-verification join beside `compare.py` (#1197);
  `tools/measure-record-findings.py` and its fleet run (#771).
- **Depends on:** none
- **Deliverables:** both tools with their tests and README entries; the fleet output returned to
  the coordinator, who posts it.
- **Acceptance criteria:** each issue's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

## Status

- [ ] Chunk 01
- [ ] Chunk 02
- [ ] Chunk 03
- [ ] Chunk 04
- [ ] Chunk 05
- [ ] Chunk 06
- [ ] Chunk 07
- [ ] Chunk 08
- [ ] Chunk 09
- [ ] Chunk 10
