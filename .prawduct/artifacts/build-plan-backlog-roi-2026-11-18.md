---
artifact: build-plan
version: 2
scope: backlog-roi-2026-11-18
branch: integration/backlog-roi-2026-11-18
base: develop
working-branches: []
dropped:
  - "06: legs 2 and 3 of issue 745 already shipped on develop in 1e40d9d4 (2026-11-15); leg 1 needs a design choice of evidence source, so the issue is restaged to design"
partition: "ten builders in isolated worktrees, one per chunk, on disjoint files; Opus-class for chunks 01-05 and 07-09 (design judgment inside settled designs), Sonnet-class for 06 and 10 (fully specified); chunk 06 returned no work (descoped, see its section). Shared seams have one owner each — plugin/lib/critic_consolidate.py: chunk 02 owns next_action_line, merge_findings, fact_to_cache_record and the consolidation call site that renders next_action; chunk 03 owns begin_review's exit-1 refusals and _widened_fallback_mode; chunk 04 owns carried_blocking, account_for_prior_blockers_directive and _round_budget_verdict. plugin/lib/coverage.py: chunk 02 owns the format_branch_rounds neighbourhood, chunk 04 owns any branch_review_ids extraction. plugin/lib/gates.py: chunk 04 owns the superseded-blocker remedy, chunk 07 owns _drop_other_sessions_commits. plugin/lib/briefing.py: chunk 04 owns _summarize_critic_findings, chunk 05 owns the backlog warming/stuck branch. plugin/bin/prawduct-hook: chunk 08 owns cmd_stop; any other chunk edits only its own subcommand handler. plugin/methodology/building.md: chunk 09 only. plugin/skills/critic/SKILL.md and review-cycle.md: chunk 03 only. Change-log fragments: one file per chunk, named by its scope. Cross-file prose budgets and the merge are the coordinator's; the coordinator integrates, runs the suite once, and governs"
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer-side write path changes; chunk 03's refusals and chunk 02's derived field are written by consolidation, not by a reviewer"
      - "authority fails closed; advice fails soft → conforms; chunk 05 turns a silent cache miss into `unchecked`, chunk 08's new signal is an info advisory, never a refusal (owner ruling 2026-09-19 on tax), chunk 07's drop record is advice that never changes a gate verdict"
      - "local-first → conforms; chunk 08's PR lookup is `git_hygiene.any_pr_for` on the existing `_gh_json` egress site, reached only behind `worktrees --prs`; the session-start probe stays offline (egress_boundary updated)"
      - "the plugin writes nothing into a governed repo except its own state → conforms; chunk 09's late-requirement records are written by the builder by hand, the lint only reads"
      - "written in Python, never specific to Python → conforms; chunk 07 reads file timestamps and chunk 09's lint reads markdown, neither dispatches by language"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms; builders departed from issue methods where code had moved (chunks 02, 03, 08) and recorded why in their fragments"
      - "every fact has one home → conforms; chunk 04 makes the branch review set one owner for render, write and read; chunk 02 derives `check` in one registry; chunk 08 keeps one gh seam"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; chunk 02 derives `check` at consolidation, never reviewer-written"
      - "facts immutable and append-only → conforms; no fact is rewritten; chunk 02's field is additive and SCHEMA_VERSION does not move"
      - "derived views never authoritative → conforms; chunk 04 replaces newest-fact views with fact composition"
      - "a governance document reaches a terminal state → conforms; chunk 01 changes how chunk state is derived, not how a plan ends; the #1199 merged-side span credit is a recorded departure under D1 awaiting the owner's confirmation"
      - "backlog issues conform to the title rules → inapplicable because no backlog write path changes (chunk 05 touches the cache and the counts snapshot only)"
      - "a newer-schema fact is surfaced, never dropped → conforms; no fact schema changes, and the census report schema bump (2→3) adds keys"
      - "two stores, two lifetimes → conforms; chunk 05's refresh attempt record is per-clone state beside the counts snapshot it describes"
      - "backlog_service_repo selects the authoritative store → conforms; chunk 05's cache repair keys watermarks by scope and reads no markdown backlog"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; persisted data schema-versioned → conforms; the dispositions report schema moves 2→3 with additive keys, the review fact schema is unchanged"
      - "exit codes are the contract → conforms; chunk 03 keeps exit 1 and exit 6, adding a `fallback_mode` key only; chunk 05's cache-miss result exits 0 as a warning"
      - "additive-first evolution → conforms; new keys, a new `--prs` flag and a new query only"
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

**Descoped 2026-11-18, nothing to build.** The delegate found legs 2 and 3 already on develop
(1e40d9d4, 2026-11-15, with `tests/test_backlog_decode_degradations.py`), and leg 1 (deleted soft
facet) undetectable from the data decode holds: telling deleted from never-set needs a prior value
(a facet echo in the block, or a cache/timeline comparison at `get`), which is a design choice.
#745 is restaged to `design` for leg 1. No commit; worktree reaped.

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

### Chunk 11: Integration, suite and cumulative review

- **Description:** merge the delegate branches into the integration branch, resolve seams, run
  the declared suite once, and run the cumulative Critic.
- **Depends on:** Chunk 01, Chunk 02, Chunk 03, Chunk 04, Chunk 05, Chunk 07, Chunk 08, Chunk 09, Chunk 10
- **Type:** cumulative-final
- **Done when:**
  1. Suite green on the integrated tree
  2. Cumulative Critic: zero unresolved blocking
