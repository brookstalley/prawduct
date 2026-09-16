---
artifact: build-plan
version: 2
scope: test-evidence-slots
# branch: feature/test-evidence-slots   <- uncomment when the branch is created
partition: serial — the schema design gates both build chunks
program: consumer-overhead-program-2026-09.md (WS6)
depends_on:
  - "build-plan-test-failure-ids.md merged — the slot record must carry its field"
related_issues:
  - "brookstalley/prawduct#653 — single-slot evidence forces re-runs of unchanged trees"
  - "brookstalley/prawduct#679 — a run that cannot record leaves the old green standing"
  - "brookstalley/prawduct#767 — test-status `current` on a stale tree; option (b) per documentation/issues/767-design.md. Option (a) is excluded here by construction"
governed_by:
  - artifact: data-model
    dispositions:
      - "a persisted format is a lock-in decision; consumer queries precede fields → ENGAGED: Chunk 01 is exactly this"
      - "two stores, two lifetimes (committed answers vs per-clone gitignored caches) → ruling needed in Chunk 01: `.test-evidence.json` is per-clone today; a slot cache stays per-clone unless the design argues otherwise. The existing `test-run` kind reserved in `evidence.py` is the shared-store alternative"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → ENGAGED: removes ~7 min re-runs per branch switch / `/clear` (discodon measurement)"
last_validated: 2026-09-16
---

# Build plan — test evidence that remembers more than one tree

## Requirements Confidence

**Level:** Low

**Why:** The success criterion is clear (#653's acceptance). The storage decision is open, and it
is a lock-in: extend the per-clone `.test-evidence.json` to N slots, or use the evidence store's
reserved `test-run` kind (shared, append-only, visible across worktrees).

**Open questions for the owner (Chunk 01 proposes an answer to each):**
- Q1: per-clone slots or shared `test-run` facts? A shared store would let a worktree reuse another
  worktree's green run of an identical tree. It would also make "a run that cannot record"
  (#679) an append failure, not a stale overwrite.
- Q2: slot count or age bound, if per-clone?
- Q3: does a red run for tree T invalidate an earlier green run for the same T? (Proposed: yes, the
  newest run for a tree wins, which closes #679's stale-green case.)
- Q4: which readers move to "any slot matches": `tests_are_current` only, or also
  `suite_vouches_for_tree`? The PR and Stop gates use the stricter one. (Proposed: both, since
  both are tree-keyed questions.)

**What would raise confidence:** Chunk 01's design with Q1–Q4 answered.

## Status

- [ ] Chunk 01: Design — evidence slots keyed by tree, consumer queries first
- [ ] Chunk 02: Build slots; readers consult every slot; a failed record never leaves a stale green
- [ ] Chunk 03: test-status discloses which clause answered (#767 option b)
Context: Drawn 2026-09-16. Starts after test-failure-ids merges.

## Chunk 01: Design — evidence slots keyed by tree, consumer queries first

- **Type:** doc-only
- **Description:** Write `documentation/issues/653-design.md`. Start by enumerating consumer
  queries: `tests_are_current`, `suite_vouches_for_tree`, `test-status`, the release gate's
  `unproven-suite`, the Critic's test-evidence check, and the triage's future "re-runs avoided"
  yield query. Then answer Q1–Q4 and give the record shape, migration from the single-slot file
  (read-compatible, no rewrite on upgrade), and a test plan. Include how #679's failure-to-record
  path cannot leave a stale green standing.
- **Acceptance criteria:** the owner has answered Q1 (the lock-in) on the issue or in the doc.
- **Done when:** doc committed; `/prawduct:critic`; tick; #653 and #679 moved to `stage: ready`.

## Chunk 02: Build slots; readers consult every slot; a failed record never leaves a stale green

- **Description:** Implement Chunk 01's design. Minimum tests, whatever the design picks: switching
  between two branches that each have a recorded green run re-runs nothing (#653's acceptance); a
  red run for tree T supersedes an earlier green for T; a record that fails to write leaves T
  unproven, not green; a v3.5.x single-slot file still reads.
- **Done when:** acceptance passes; `/prawduct:critic`; tick; close #653 and #679.

## Chunk 03: test-status discloses which clause answered (#767 option b)

- **Type:** cumulative-final
- **Description:** Build `documentation/issues/767-design.md` (option b) on top of the slot reader:
  output names the clause that answered and the tree the evidence covers; the three governing call
  sites are corrected. No exit-code change and no new re-run.
- **Done when:** commit; one `/prawduct:critic cumulative`; tick; close #767.
