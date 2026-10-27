---
artifact: build-plan
version: 2
scope: chunk-state-table
branch: fix/1092-chunk-state-table
base: develop
working-branches: []
last_validated: 2026-10-27
depends_on:
  - brookstalley/prawduct#1092
  - brookstalley/prawduct#1079
  - brookstalley/prawduct#1082
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
partition: Chunks 01-02 delegated to one isolated-worktree agent (they share plan_status.py); the coordinator integrates, runs the suite, Critic and PR
---

# Build Plan — Chunk state answers the whole case table (#1092, #1079, #1082)

## Goals

**Response taken:** Proceed, citing #1092, #1079 and #1082. The owner asked on 2026-10-27 for
#1079 and #1082 to land in 3.8.0. #1092 says those two must not be closed as two more instances, so
the coordinator folded it in: the plan checks `plugin/lib/plan_status.py` against the whole case
table at once.

**Problem:** Chunk state derived from review facts is the 3.8.0-dev regression cluster: six bugs in
two days (#1065, #1072, #1075, #1079, #1081, #1082), each a different way a chunk reads open or done
when it should not, and each fix exposing the next. Two are still open:
- #1079: a review of uncommitted work is anchored at its `base_commit`, the branch HEAD the dirty
  tree sat on. After a `--no-ff` merge and branch deletion, the `anchor == fork_point` refusal in
  `_Reachability.__call__` reads that anchor as "on the base before the review ran", so the chunk
  reads open.
- #1082: a chunk becomes done only through a review fact whose `fact_chunks` names it. A clean
  review whose tree span covers the chunk's commit, but which names no chunks, leaves it open.
  `plan-backfill` then refuses the plan and `archive-plan` stamps built work `unbuilt_at_archive`,
  while the coverage gate passes over the same span.

**Success:**
- A case table, committed in this plan (Chunk 01), enumerating every situation the derivation must
  answer, with the expected state for each. At least: anchor reachability before and after merge;
  merge-commit vs squash merge; branch deleted vs present; dirty-tree reviews (`head_commit: null`)
  vs committed; named vs unnamed coverage; `chunk` / `final` / `cumulative` / `verify-resolutions`;
  proposal at final, cumulative and boundary; retraction; dropped chunks; blocking findings
  unresolved vs resolved.
- Every row is pinned by a test, and `plan_status.py` passes the whole table.
- #1079's repro (plan on a branch, chunk review over a dirty tree at the branch HEAD, commit,
  `--no-ff` merge, delete the branch) reads the chunk done.
- #1082's repro (steps 1-7 in the issue) reads chunk 3 done; `plan-backfill` archives the plan and
  `archive-plan` records no unbuilt chunks.
- The previously shipped fixes (#1065, #1072, #1075, #1081) still hold: their tests stay green
  unchanged.

**Design decision (coordinator, for #1082's open fork):** option 1, span-derived. A chunk is done
when a clean review fact's tree span covers the chunk's built commit, whether or not the fact names
it. Reason: the coverage gate already composes by span, and two instruments disagreeing over one
span is the root cause #1092 names; option 2 (make every flow name every chunk) adds one more
place to keep in sync. Naming still works: a fact that names a chunk keeps certifying it as today.
*Inferred:* "the chunk's built commit" is the commit(s) the existing `_walk_branch` /
`built_report` subject-and-deliverable walk already attributes to that chunk. An unbuilt chunk has
no commit, so a span can never certify it, which keeps #1072 fixed.

**Out of scope:** #1106 (the briefing's stale-plan predicate; a separate branch calls
`plan_lifecycle.observe` and needs its signature unchanged). The remainder of #1071.

**Level:** Medium. What would raise it: the case table itself, which is Chunk 01's deliverable.

**Decisions made mid-build:** *(appended while building)*

## Chunks

### Chunk 01: The case table, and a test per row

- **Description:** Enumerate the cases from the Success list (and any the code shows that the list
  missed), each with its expected state, as a table in this plan under "## Case table". Pin each
  row with a test in `tests/` against `plan_status.chunk_states` (git fixtures as the existing
  plan_status tests build them). Rows the current code fails are marked `xfail(strict=True)` with
  the row id, so Chunk 02 flips them.
- **Depends on:** none
- **Deliverables:** "## Case table" in this plan; the per-row tests
- **Tests:** the table's rows
- **Acceptance criteria:** every row has a test; the failing rows are exactly the ones #1079 and
  #1082 describe plus any new ones the table found (each named in "Decisions made mid-build")
- **Done when:**
  1. Acceptance criteria met
  2. Committed

### Chunk 02: plan_status passes the table

- **Description:** Fix `plan_status.py` so every row passes: the #1079 reachability rule (refuse
  an anchor only when it was on the base's first-parent history; accept one reachable only through
  the merge) and #1082's span-derived done. Update every artifact that describes chunk state —
  `plugin/methodology/planning.md` "Chunk state", `api-contract.md`, the cross-cutting-concerns
  row, docstrings — so they describe span coverage. Search for the claim ("names it",
  `critic-begin --chunks`), not just the tokens edited.
- **Depends on:** Chunk 01
- **Deliverables:** `plugin/lib/plan_status.py` and the prose surfaces above
- **Tests:** Chunk 01's table, all rows passing with no xfail; the existing plan_status tests
- **Acceptance criteria:** the Success list
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed

### Chunk 03: change record

- **Type:** cumulative-final
- **Description:** `.prawduct/changes/chunk-state-table.md`: narrative and consumer note,
  `closes: [brookstalley/prawduct#1079, brookstalley/prawduct#1082, brookstalley/prawduct#1092]`.
- **Deliverables:** `.prawduct/changes/chunk-state-table.md`
- **Done when:**
  1. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
