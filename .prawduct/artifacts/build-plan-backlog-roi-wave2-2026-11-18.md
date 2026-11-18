---
artifact: build-plan
version: 2
scope: backlog-roi-wave2-2026-11-18
branch: integration/backlog-roi-wave2-2026-11-18
base: develop
working-branches: []
dropped:
  - "01: superseded by issue 1128 (commit 9e5087d3, 2026-11-10), which made a NOTE an observation at every stage; zero boundary NOTE findings since. Issue 830 closed as superseded"
partition: "four Opus-class builders in isolated worktrees, one per chunk, stacked on integration/backlog-roi-2026-11-18 (PR #1206). Seams have one owner each. plugin/lib/critic_consolidate.py: chunk 01 owns next_action_line's disposition wording; chunk 02 owns validate_partial, merge_findings, FINDING_SCOPE_DIRECTIVE, account_for_prior_blockers_directive and the resolution path. plugin/lib/dispositions.py: chunk 01 only. plugin/lib/ledger.py: chunk 03 only. plugin/lib/gates.py: chunk 04 owns the post-fix coverage remedy text; chunk 01 touches no gates.py. plugin/skills/critic/review-cycle.md: chunk 01 owns the 'Severity does not exempt' passage, chunk 04 owns the Verify-resolutions anchoring derivation and the exit-3 qualifier. plugin/methodology/building.md and plugin/skills/pr/SKILL.md: chunk 04 only. Reviewer payload and prose budgets are the coordinator's to reconcile at merge. Commit subjects use THIS plan's scope: `<type>(backlog-roi-wave2-2026-11-18): … (Chunk NN)`, which is what credits a chunk in `plan status`."
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
  - plugin/lib/dispositions.py
  - plugin/lib/critic_consolidate.py
  - plugin/lib/ledger.py
  - plugin/lib/gates.py
last_validated: 2026-11-18
---

## Goals

**Response taken:** Proceed, citing it. The owner asked on 2026-11-18 for every mid-to-high ROI
backlog item to be addressed with delegated builders. These four were deferred from wave 1
(`build-plan-backlog-roi-2026-11-18.md` § Goals) only because they share files with it. The
branch is stacked on wave 1's integration branch, so they build on its seams. Before dispatch,
`git log --grep` found no commit naming any of the four.

**Product:** each item's own acceptance list.

## Verification Strategy

Each fix is red first. Builders run only their own tests plus the CLASS of whole-tree guards that
read the files they touch: prose and payload budgets, packaging and citation lints, fragment
schema, goldens. The full suite runs once, on the integrated branch.

## Build Chunks

### Chunk 01: A boundary NOTE is noted, not owed (#830)

- **Description:** #830's design D1-D5, starting with step 0's measurement (the kill criterion).
- **Depends on:** none
- **Deliverables:** as #830 and `documentation/issues/830-requirements.md`.
- **Acceptance criteria:** #830's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: Class findings carry members as data (#847)

- **Description:** the measurement tool, then D1 and D3 regardless and D2 only if the measurement
  clears its bar, per `documentation/issues/847-design.md` and #847's forks.
- **Depends on:** none
- **Deliverables:** as #847.
- **Acceptance criteria:** #847's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: Resolution and disposition facts and the shared record (#606)

- **Description:** decide between mirroring resolution and disposition facts into the ledger and
  documenting the asymmetry, given that `evidence sync` now carries every fact to other clones
  through `refs/notes/prawduct`; implement the choice and fold in the `--fix` wording defect.
- **Depends on:** none
- **Deliverables:** as #606's Expected.
- **Acceptance criteria:** nobody reads the committed ledger as a complete audit trail when it
  is not one.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 04: The post-fix coverage rule has one home (#723)

- **Description:** a construction so correcting the rule edits one file.
- **Depends on:** none
- **Deliverables:** as #723's Acceptance.
- **Acceptance criteria:** #723's Acceptance list.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 05: Integration, suite and cumulative review

- **Description:** merge, resolve seams, run the suite once, run the cumulative Critic.
- **Depends on:** Chunk 01, Chunk 02, Chunk 03, Chunk 04
- **Type:** cumulative-final
- **Done when:**
  1. Suite green on the integrated tree
  2. Cumulative Critic: zero unresolved blocking
