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
      - "prawduct is written in Python and must never be specific to Python → conforms; the excluded-file set comes from `coverage_algebra.judgeable_files`, the existing path-based predicate, and no new suffix or language literal is introduced"
      - "goals and verification bind; prescribed method is advice → conforms"
      - "every fact has one home → LOAD-BEARING HERE. The bug is a fact with two carriers: which tree a verify-resolutions pass anchored lives in the dispatch code, and three prose sites restate it from memory. The repair moves the answer to the one place that computes it (the refusal names its own anchor) and reduces the prose sites to a checkable discriminator rather than a second assertion"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract; errors attributed → conforms; exit 3 keeps its meaning and its predicate. The prefix vocabulary is reused"
      - "additive-first evolution; `--json` keys never repurposed → conforms; `excluded_wip` and `anchor` are new keys on an existing result dict, `free_files` and `reason` keep their meanings, and a reader that ignores the new keys behaves exactly as before"
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

- [ ] Chunk 01: A refusal names the tree it graded and the judgeable work it excluded

Context: Plan written 2026-08-26 on `fix/verify-resolutions-exit3-excluded-wip`, cut from
a clean `develop`. Baseline suite green (`test-status` exit 0, tree-valid).

---

### Chunk 01: A refusal names the tree it graded and the judgeable work it excluded

**Problem:** as above.

**Acceptance criteria:**

1. Both committed-tree anchors (`cumulative`, and `verify-resolutions` when
   `committed_differs`) compute the judgeable uncommitted files they exclude and carry
   them structurally, not only as prose.
2. The exit-3 result carries the excluded set, the name of the tree it graded, and the
   dispatch `notes` it previously dropped; its `reason` names the anchored tree.
3. The CLI prints the exclusion block **last** when the set is non-empty, and suppresses
   the "Nothing to do" line in that case — a reader acting on the final imperative must
   land on "those files are unreviewed", not on "--force".
4. The guard-refusal evidence fact records the excluded set alongside `free_files`.
5. `gates.py`'s uncovered remedy and `plugin/skills/pr/SKILL.md` Step 2 state the
   condition under which committing verbatim closes the gap, and what happens when it
   does not hold.
6. `begin_review`'s docstring describes the intent-aware verify-resolutions anchor
   instead of the pre-#395 working-tree-only one.
7. Regression tests: the repro from the issue exits 3 **and** names the excluded
   judgeable file; a refusal with no dirty tree still says "Nothing to do"; the
   guard-refusal fact carries the excluded set.

**Done when:** acceptance criteria pass, suite green, `/prawduct:critic` run and blocking
findings resolved.
