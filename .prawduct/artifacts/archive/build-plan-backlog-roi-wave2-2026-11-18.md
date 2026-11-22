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
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer-side write path changes; chunk 02's member fields are written by the reviewer into its own partial and graded by consolidation"
      - "authority fails closed; advice fails soft → conforms; chunk 02 withholds a `fixed` resolution of a blocking finding whose members are unanswered (closed: the finding keeps blocking under every plugin version), and drops a malformed member with a warning (soft)"
      - "local-first → inapplicable because no network surface changes; chunk 03 documents the existing notes transport and adds none"
      - "the plugin writes nothing into a governed repo except its own state → inapplicable because no repo-write path changes"
      - "written in Python, never specific to Python → inapplicable because no language dispatch changes"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms; chunk 03 chose documentation over mirroring once the evidence showed the ledger was never a shared record, and recorded why"
      - "every fact has one home → conforms; chunk 04 gives the post-fix coverage rule one home (`gates.POST_FIX_COVERAGE`) with prose pointing at `review-cycle.md`'s derivation"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; chunk 02's member grading reads the review fact's recorded members, and the model writes only into its partial"
      - "facts immutable and append-only → conforms; a withheld resolution is never appended, and nothing is rewritten"
      - "derived views never authoritative → conforms; chunk 03 states that the ledger is a per-worktree view of reviews, never their outcomes"
      - "a governance document reaches a terminal state → conforms; chunk 01 is recorded in `dropped:`"
      - "backlog issues conform to the title rules → inapplicable because no backlog write path changes"
      - "a newer-schema fact is surfaced, never dropped → conforms; the review fact's new optional fields are additive and older readers ignore them"
      - "two stores, two lifetimes → conforms; chunk 03 names which facts travel (`TRANSPORTED_KINDS`) and files the disposition question as #1207"
      - "backlog_service_repo selects the authoritative store → inapplicable because no backlog reader changes"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; persisted data schema-versioned → conforms; `scope`/`closure`/`members` are optional additive keys, and SCHEMA_VERSION does not move"
      - "exit codes are the contract → conforms; no exit code changes, and `validate-partial` still exits 0 when it drops a malformed member, printing a warning"
      - "additive-first evolution → conforms; new optional fields and a new tool only"
depends_on:
  - plugin/lib/dispositions.py
  - plugin/lib/critic_consolidate.py
  - plugin/lib/ledger.py
  - plugin/lib/gates.py
last_validated: 2026-11-18
lifecycle: completed
archived: 2026-11-22
released_in: v3.9.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

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
