---
artifact: build-plan
version: 2
scope: coherence-pass
branch: fix/coherence-pass-2026-11-16
base: develop
working-branches: []
partition: "three Opus builders in isolated worktrees, one per chunk, on disjoint files; shared seams have one owner each — plugin/bin/prawduct-hook: chunk 01 owns the exit-7 and check-operator-verification handlers, chunk 03 owns the critic-consolidate, SubagentStop and Stop-backstop call sites; plugin/skills/pr/SKILL.md: chunk 01 owns the test-status and operator-verification rows, chunk 02 owns the change-log/gitignore rows. The coordinator merges, runs the suite once, and governs"
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms; the operator-verification ImportError arm stops failing open, and advice text loses blocking voice where nothing blocks"
      - "every fact has one home → conforms; each chunk removes a second owner (suite remedy text, the .prawduct/ narrowing advice, the head-detach check) rather than adding one"
      - "guides and reviews, never implements → conforms"
  - artifact: data-model
    dispositions:
      - "facts immutable and append-only → conforms; no fact is rewritten, the manifest loses a key nothing reads"
      - "derived views never authoritative → conforms; the findings cache stays a view, a missing one is re-derived from the store"
depends_on:
  - plugin/lib/gates.py
  - plugin/lib/core.py
  - plugin/lib/coverage.py
  - plugin/lib/critic_consolidate.py
  - plugin/lib/operator_verification.py
  - plugin/skills/critic/SKILL.md
  - plugin/skills/pr/SKILL.md
last_validated: 2026-11-16
---

## Goals

**Response taken:** Proceed, citing it. The owner asked (2026-11-16) for the Fable final-coherence
pass over PR #1185 and for the result to be made excellent. That pass (one Fable agent, read-only)
returned ten should-fix findings and five nits, no blocking; this plan fixes all fifteen. Findings
1–5 were reproduced by the pass in scratch repos; each chunk re-reproduces its findings red before
fixing.

**Product:** No surface built in the tech-debt cycle misleads its reader: the Critic does not
grade a running suite as a defect, advice does not lead an owner into exposing session files, a
remedy prints once, an off gate does not speak in blocking voice, the PR gate and the release gate
agree, and a retirement is finished.

**Out of scope:** #1184, #1182, #1183, #745 leg 1 (known, tracked). The pass's "not covered" list
(release runbooks, host.py transcript parser) is not reviewed here.

## Verification Strategy

Each fix is red first: a test that fails on develop's tip at d082657e and passes after. Prose
fixes are checked by the repo's cross-file prose tests (budgets, payload budgets, goldens, guards)
plus a falsifying grep whose output goes in the builder's report. Builders run only the tests for
their files and those cross-file prose tests; the full suite runs once, on the integrated branch.

## Build Chunks

### Chunk 01: Suite-state and operator-verification surfaces say one thing once

- **Description:** (1) The Critic protocol learns `running:` and `stale (interrupted):`: a row at
  `plugin/skills/critic/goals-1-3.md`, `review-protocol.md` and `SKILL.md` saying a suite in flight
  is not a finding (wait, or note it); widen the Critic grants from `Bash(prawduct-hook
  test-status)` to `test-status*` in the critic SKILL front matter and `plugin/agents/critic-reviewer.md`.
  (3) A suite refusal prints its remedy once: `gates.tests_are_current`/`run_refusal` return the
  finding only; `test-status` joins finding and remedy; exit 7 in `prawduct-hook`,
  `release_readiness` `unproven-suite` and the transfer note print finding + `suite_remedy()`.
  (4) `check-operator-verification` with the requirement off prints no blocking-voiced advice
  (`_unreadable_queue` derives its tail from the `required` state); the PR skill's exit-3 row names
  all three exit-3 states. (10) The ImportError arm of `check-operator-verification` exits 3, not
  0; its docstring lists every exit.
- **Depends on:** none
- **Deliverables:** the edits above with tests.
- **Tests:** Red first: a running void during `verify-coverage`/release check prints the remedy
  once; gate-off + unreadable queue exits 0 with no "You can stop here"/blocking wording; the
  ImportError arm exits 3; the grants admit `test-status --wait`.
- **Acceptance criteria:** the five pass-reported sites behave as above.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: The .prawduct/ ignore advice has one owner and is safe to follow

- **Description:** (2) `core.describe_ignored_by_rule`: deleting a wholesale `.prawduct/` line is
  followed by `prawduct-hook update-gitignore` in the same sentence (or the replace-lines option
  leads); the docstring's false claim is corrected. (8) `coverage.py` and the PR skill stop
  spelling `.prawduct/*` + `!.prawduct/changes/`; they point at `prawduct-hook update-gitignore
  --dry-run`. (5) `coverage._committed_log_pending_verdict` reads the on-disk log when the log is
  untracked, so `check-change-log-entry` refuses what `check-releasability` refuses. (13) User-facing
  strings name the doctor check, not its ordinal. (14) `contract-ignored-by-rule` is `warn`, and its
  evidence string drops the internal `V2_COMMITTED_PATHS` reference.
- **Depends on:** none
- **Deliverables:** the edits above with tests.
- **Tests:** Red first: following the advice in a `.prawduct/`-ignored repo leaves no session
  file untracked-visible; a wholesale-ignored repo with a pending on-disk legacy entry makes
  `check-change-log-entry` refuse; no user-facing string carries "check #<n>".
- **Acceptance criteria:** the PR gate and the release gate agree on the ignored-log case, and
  one function owns the narrowing advice.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: Review-record seams go through their owners; the chunk-shim retirement finishes

- **Description:** (6) `critic_consolidate.verify_anchor`: no readable cache, no `fact_id`, or
  fact-not-found fall through to `select_branch_review` with `rederived=True`, refusing only when
  it returns none; the cache is read as UTF-8 and an undecodable cache takes the same path.
  (7) Finish the chunk-shim retirement: correct `.prawduct/artifacts/data-model.md`'s review-fact
  `chunk` sentence, drop `begin_review(chunk=…)`, reword the manifest `chunk` comment to name its
  real reader. (9) The head-detach check moves into `critic_consolidate.consolidate`, so the
  SubagentStop and Stop-backstop paths get it, carried in the record's `next_action`. (11) Delete
  the unread manifest key `native_review.text_path`. (12) `critic_mode` renders a re-derived record
  through `branch_review_record`. (15) The briefing says "this branch has no review; the cache holds
  <branch>'s" when `verify_anchor`'s reason is definitive.
- **Depends on:** none
- **Deliverables:** the edits above with tests.
- **Tests:** Red first: a fresh worktree of a reviewed branch (no cache) gets the owner's review,
  not a demotion; a hook-path consolidate on a detached HEAD reports it; the manifest validator
  accepts a manifest without `text_path`; a grep for `chunk=` callers of `begin_review` returns none.
- **Acceptance criteria:** as above.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 04: Cumulative review and change record

- **Description:** Integrate the three branches, run the declared suite once, add the change
  fragment `.prawduct/changes/coherence-pass.md`, and run the cumulative Critic.
- **Depends on:** Chunk 01, Chunk 02, Chunk 03
- **Type:** cumulative-final
- **Done when:**
  1. Suite green on the integrated tree
  2. Cumulative Critic: zero unresolved blocking
