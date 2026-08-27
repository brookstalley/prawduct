---
artifact: build-plan
version: 1
scope: verify-resolutions-exit3
branch: fix/verify-resolutions-exit3-excluded-wip
depends_on:
  - artifact: architecture
  - artifact: api-contract
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; the change is confined to dispatch-time message derivation and opens no mutation site"
      - "authority fails closed; advice fails soft → conforms; the refusal's VERDICT is unchanged (exit 3 stays exit 3 on the same predicate). Only what it reports changes, and the exclusion list is derived from the same `tree_diff` the branch already ran"
      - "local-first; no third-party runtime dependencies → conforms; the excluded set comes from a `git diff` this branch already ran, and no network or dependency is added"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the one new write is a field on a guard-refusal fact in the shared evidence store, which the carve-out already names"
      - "prawduct is written in Python and must never be specific to Python → conforms; the excluded-file set comes from `coverage_algebra.judgeable_files`, the existing path-based predicate, and no new suffix or language literal is introduced"
      - "prawduct guides and reviews; it never implements → conforms; the change is to what a governance refusal REPORTS, which is review-side by construction, and it writes nothing into a governed product"
      - "goals and verification bind; prescribed method is advice → conforms"
      - "every fact has one home → LOAD-BEARING HERE. The bug is a fact with two carriers: which tree a verify-resolutions pass anchored lives in the dispatch code, and three prose sites restate it from memory. The repair moves the answer to the one place that computes it (the refusal names its own anchor) and reduces the prose sites to a checkable discriminator rather than a second assertion"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract; errors attributed → conforms; exit 3 keeps its meaning and its predicate. The prefix vocabulary is reused"
      - "additive-first evolution; `--json` keys never repurposed → conforms; `excluded_wip`, `anchor` and `notes` are new keys on an existing result dict (`notes` already existed on the dispatch result and is now also returned on the refusal one, which is additive at the refusal), `free_files` and `reason` keep their meanings, and a reader that ignores the new keys behaves exactly as before. `excluded_wip` is tri-state by design — a list, or `null` when the uncommitted diff could not be computed — so no reader can render an all-clear off a check that never ran"
      - "whole-surface semver; CLI subcommand surface internal → conforms; `critic-begin` is not in the published-surfaces group"
partition: serial — one small diff over one risk surface (the dispatch refusal); delegation would cost more in integration than it saves
last_validated: 2026-08-26
---

## Requirements Confidence

**Level:** High

**Why:** Every claim in the issue was verified against the source this session, not
inferred: the `committed_differs` anchor at `critic_consolidate.py`, the exit-3 return
that carries neither `notes` nor any exclusion list, the gates.py remedy's condition,
and the `pr/SKILL.md` sentence. The one design fork — whether to widen the interval to
include the working tree instead — is closed by the issue's own "Related" note: that
anchor is #395's fix, and reverting it re-opens the inverse bug.

**Open assumptions / unknowns:** none.

**What would raise confidence:** N/A

## Problem

`verify-resolutions` (and `cumulative`) can anchor at **committed HEAD** while the
builder's judgeable work sits uncommitted. When that interval holds no judgeable file,
dispatch returns **exit 3, "no judgeable file"** — which reads as *nothing to do* but
means *your work is not in the interval I chose*. The excluded files are never named,
the tree that was graded is never named, and the dispatch's own dirty-tree note is
dropped on this path. Three prose sites compound it by promising working-tree coverage
without the condition that makes the promise true.

## Success

Running `/prawduct:critic verify-resolutions` with a committed fix plus uncommitted
judgeable edits exits 3 **and** prints which tree it graded, how many judgeable
uncommitted files it excluded, their names, and the fact that they remain unreviewed —
with that correction as the block's last imperative, not buried above a "nothing to do".
The excluded set is also on the guard-refusal fact, so the guard's yield question stays
answerable. The three prose sites state the condition under which
"commit verbatim, no further pass is owed" actually holds.

## Out of scope

- Changing the anchor so the interval includes the working tree. That is #395's fix
  running backwards; the exit-3 message is the defect, not the anchor.
- Making the refusal *not fire* when judgeable WIP exists. It is still correct — a review
  of the committed interval would not cover those files either. Only its wording was wrong.
- #716 (verify-resolutions signalling reads wider than its delta) — a sibling, filed
  separately, not folded in here.

## Status

- [x] Chunk 01: A refusal names the tree it graded and the judgeable work it excluded

Context: Plan written 2026-08-26 on `fix/verify-resolutions-exit3-excluded-wip`, cut from
a clean `develop`. Baseline suite green (`test-status` exit 0, tree-valid).

Chunk 01 closed 2026-08-26 after three rounds (`cumulative` → two `verify-resolutions`), ending
0 blocking / 0 warning / 0 note. Suite green at 5340; evidence recorded against the reviewed tree.
**The plan is complete. On a gitflow base it stays live past the `develop` merge and is
archived by the `develop`→`main` release (`plan-backfill`) — `skills/pr/SKILL.md` Step 1d and
Merge Flow; archiving at this merge is the mistake.**

What the reviews changed, worth carrying. Round 1 found the fix had shipped the sibling of the bug
it was fixing: the anchor discriminator went out as a commit-SET test in two surfaces at once,
where the code compares TREES — so the corrected prose told a builder on the golden path that they
owed the round this branch exists to remove. The canonical statement existed in `review-cycle.md`
and was never opened. Homed as `learnings.md` "When operator prose restates a PREDICATE, diff your
sentence against the rule's canonical prose statement". Round 1 also found `or []` on a function
documented to return `None` for "could not compute" — inherited from the four lines this change
refactored, and tolerable feeding a boolean but not an all-clear. Three reviewers independently hit
three different carriers of one rule across five files; the round corrected all five and filed #723
for the construction that would collapse them.

Two demoted observations in round 3 were false statements in this plan and the change-log,
corrected here rather than accepted: both records live under `.prawduct/`, which composes as a free
edge, so the correction cost no further round.

---

### Chunk 01: A refusal names the tree it graded and the judgeable work it excluded

**Problem:** as above.

**Acceptance criteria:**

1. Both committed-tree anchors (`cumulative`, and `verify-resolutions` when
   `committed_differs`) compute the judgeable uncommitted files they exclude and carry
   them structurally, not only as prose.
2. The exit-3 result carries the excluded set, the name of the tree it graded, and the
   dispatch `notes` it previously dropped — all of them except the dirty-tree note, whose
   content the refusal block already delivers, so one fact reaches the operator once.
   Its `reason` names the anchored tree.
3. An uncomputable uncommitted diff is reported as UNKNOWN, never as an empty exclusion
   set: `_judgeable_wip` propagates `tree_diff`'s `None`, the result and the fact record
   `null`, and no surface issues an all-clear off a check that did not run.
4. The CLI prints the exclusion (or the UNVERIFIED caveat) **last** and suppresses the
   "Nothing to do" line in both cases — a reader acting on the final imperative must land
   on "those files are unreviewed", not on "--force".
5. The guard-refusal evidence fact records the excluded set alongside `free_files`, and
   `evidence list --kind guard-refusal` — the query that ruling names as the guard's yield
   check — renders it, `excluded=?` included.
6. No surface still teaches the falsified promise. The two that state the anchor *test*
   — `gates.py`'s uncovered remedy and `skills/pr/SKILL.md` Step 2 — state it as committed
   **content** the prior review never saw, and cite `review-cycle.md` rather than
   restating the derivation. The other three carry their own correct fact and need no such
   citation: `gates.py`'s blocking remedy conditions its dirty-tree read on the no-commit
   line above it, `skills/critic/SKILL.md`'s exit-3 rule keys on the refusal block, and
   `methodology/building.md` states the fix ordering and points.
7. `begin_review`'s docstring describes the intent-aware verify-resolutions anchor
   instead of the pre-#395 working-tree-only one.
8. Regression tests: the repro from the issue exits 3 **and** names the excluded
   judgeable file; the excluded file is named exactly once across both streams; a refusal
   with no dirty tree still says "Nothing to do"; an injected `tree_diff` failure reports
   UNKNOWN rather than clean; the guard-refusal fact carries the excluded set; and the
   corrected prose is pinned in `tests/preferences/test_free_interval_prose.py`.
9. No dispatch return drops notes a reader could act on. The refusal path forwards all but
   the dirty-tree note, whose content its own block delivers; `scope-widened` — the one
   error return reached with notes populated by a mode branch — carries them, and the CLI
   prints whatever any non-ok result carries. The remaining error returns fire before the
   mode branches, so what they hold is a deliverable-gap note with no bearing on an
   anchor failure. Round 2's R-13 named this half.

**Done when:** acceptance criteria pass, suite green, `/prawduct:critic` run and blocking
findings resolved.
