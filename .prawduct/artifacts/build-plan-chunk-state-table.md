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
no commit, so a span can never certify it, which keeps #1072 fixed. (That holds only once a path
two chunks list attributes a commit to neither: see Decisions, Chunk 02 review round 2.)

**Out of scope:** #1106 (the briefing's stale-plan predicate; a separate branch calls
`plan_lifecycle.observe` and needs its signature unchanged). The remainder of #1071.

**Level:** Medium. What would raise it: the case table itself, which is Chunk 01's deliverable.

**Decisions made mid-build:** *(appended while building)*
- Chunk 01: the rows failing before Chunk 02 were M2 (#1079) and C2-C6, C10, C13, C14, K2, P4, B5,
  X3 (#1082). C5, C6 and P4 test an invariant that already held, but each carries a span-done
  positive control in the same fixture, so they failed with the rest of #1082.
- *Not settled by the goals:* "the chunk's built commit" is a commit in the FACT's own interval,
  attributed by the proposal's certifying rule (a subject carrying the plan's scope, or a
  Deliverables path only that chunk lists), not `built_report`'s whole-branch walk. The goals inferred
  the walk; it reads nothing once the merge deletes the branch (C14), and its path rule reads a
  Deliverable touched early as built, which would let a span certify an unbuilt chunk (C6).
- *Not settled by the goals:* a span certifies only through a fact that is an edge
  (`coverage_algebra.review_edges`) — the same validity the coverage gate composes with, so chunk
  state never spans an interval the gate rejects (an edge may still certify no chunk).
- *Not settled by the goals:* a dirty-tree fact's uncommitted part certifies only once that tree is
  committed verbatim (C10, C11); a fact with no `base_commit` spans nothing (C12).
- *Not settled by the goals:* fast-forward merge with an anchor equal to its `base_commit` (M5) and
  squash merge (M6) read open after the branch is deleted, as today: M5 cannot be told from a fork
  point on the first-parent history, and a squash leaves the anchor on no ref.
- Chunk 02: #1079's rule is "refuse an anchor equal to its review's `base_commit` only when it is on
  the base's first-parent history" — the goals' first-parent test, kept to the anchor the old rule
  refused, so a fast-forwarded anchor that is NOT its `base_commit` stays done (M4) as before.
- Chunk 02: naming answers first and a span only for a chunk naming left open; a span-certified
  `done` carries a `reason` saying so, since the cited fact does not name it.
- *Not settled by the goals:* `plan retract` may withdraw a span certification only while that
  span certifies the chunk (`retraction_target`); one blocked today cannot be withdrawn in advance.
- *Not settled by the goals:* `data-model.md`'s 2026-10-24 ruling D1 gains a dated extension note
  citing this plan's design decision rather than a rewritten statement; the owner's confirmation
  of option 1 lives with the coordinator, not here.
- Left for the coordinator (outside this delegate's files): `critic_consolidate.uncertified_clause`
  says a whole-plan review that names nothing "certified no chunk" and "omitting it certifies only
  the proposal", both now false when its span certified some; and `plan_lifecycle`'s merge probe
  keeps the old `anchor == base_commit` refusal (its signature and behaviour were out of scope).
- Coordinator, integration: both are fixed in Chunk 03's commit. The first-parent test is one
  function, `plan_status.on_first_parent`, which the `_Reachability` probe and
  `plan_lifecycle._merge_evidence` both call, so the lifecycle reads #1079's case as
  merged-unreleased by the same rule chunk state uses (one owner for the class). The NEXT-ACTION
  clause now says the review "named no chunk" and speaks only of the chunks still open.
- Chunk 02 review round 2: a span credited every chunk whose Deliverables a commit in its interval
  touched, so when two chunks list one path the commit building one certified the other, unbuilt,
  and the boundary `cumulative` re-certified it after any retraction. Now a touched path credits a
  chunk only when that chunk is its one owner among all the plan's chunks (the path itself or a
  directory above it, rows S1-S3); a shared path needs a scoped subject or a naming fact. The
  proposal shares the rule through the same owner, `_deliverable_chunks`, and notes the shared path
  when it is why an open chunk was left out (S4). *Not settled by the goals:* ownership is counted
  over every chunk of the plan, not only the open ones, so a done chunk still makes a path shared;
  the `built` tag keeps the loose rule (S5), because it certifies nothing and arms its one gate
  only early, where crediting both owners errs toward arming.
- Round 2 against this repo's 173 plans (46 with a shared path): no chunk's state changed from
  39dcde20. Only one chunk here is span-certified at all (`build-plan-coverage-honesty.md` 04,
  archived), the same under both rules: this repo's reviews name their chunks, so the span path
  rarely decides.

## Case table

Every situation `plan_status.chunk_states` answers, with the state it must answer. Each row is one
test in `tests/test_chunk_state_table.py`, named `test_<row id>_…`. "Named" is a review fact whose
`chunks` (else `chunk`) lists the chunk; "span" is a clean, in-scope review fact that is an edge in
the coverage algebra's sense (`coverage_algebra.review_edges`: both trees recorded, every judgeable
changed file reviewed) and whose interval carries a commit that builds the chunk — a commit subject
carrying the chunk and the plan's scope, or a path the commit touches that ONLY that chunk's
Deliverables cover (a path two chunks list attributes to neither; the `plan new` stub fragment
touches nothing). A commit is in a fact's interval when it is in
`base_commit..head_commit`, or, for a dirty-tree fact (`head_commit: null`), in
`base_commit..dispatch_commit` or on the first-parent chain from `dispatch_commit` to the first
commit whose tree is the fact's `head_tree` (the reviewed tree, committed verbatim).

| Row | Situation | Expected |
|---|---|---|
| **A — anchor placement, branch present** | | |
| A1 | Named fact anchored on the plan's `branch:` | done (that chunk only) |
| A2 | Named fact anchored on no claimed branch; branch present | open, "not on `feature/unit`" |
| A3 | Named fact anchored on a declared `working-branches:` entry | done |
| A4 | Branch only on a remote; anchor on its tracking ref | done |
| A5 | Git cannot list the branches | open, no base fallback |
| A6 | Plan declares no `branch:` | open, says so |
| A7 | Fact records no commit (`head_commit` and `dispatch_commit` null) | open, says so |
| A8 | Dirty-tree named fact (`head_commit: null`), branch present | done, anchored at `dispatch_commit` |
| **M — after the merge** | | |
| M1 | `--no-ff` merge, branch deleted, committed review (#1065) | done |
| M2 | `--no-ff` merge, branch deleted, dirty-tree review at the branch HEAD, so anchor = `base_commit` (#1079) | done: the anchor reaches the base only through the merge |
| M3 | As M2, branch kept | done |
| M4 | Fast-forward merge, branch deleted, committed review | done |
| M5 | Fast-forward merge, branch deleted, anchor = `base_commit` | open, "review's own base commit": on the base's first-parent history it cannot be told from a fork point |
| M6 | Squash merge, branch deleted | open: the reviewed anchor is on no ref |
| M7 | Branch deleted unmerged | open, names the gone branch |
| M8 | Fork-point anchor (a review before the branch's first commit), branch deleted | open, "review's own base commit" |
| M9 | Branch gone, plan's `base:` names no ref | open, says so |
| **C — named vs span coverage** | | |
| C1 | Fact names chunk 01; its span ends before chunk 02's commit | 01 done, 02 open |
| C2 | Unnamed span carries chunks 01 and 02 by scoped subject | both done, citing that fact |
| C3 | Unnamed span carries chunk 02 by a Deliverables path, subject naming no chunk | 02 done |
| C4 | Fact names 01; its span also carries 02's commit | both done |
| C5 | Unnamed `final` span carrying only chunk 01's commit (#1072's invariant) | 01 done, 02 and 03 open |
| C6 | Chunk 03's Deliverable touched before the span starts | 03 open |
| C7 | Chunk carried only by an unscoped subject (`feat(other): … (Chunk 02)`) | open |
| C8 | Span fact that reviewed less than it changed (no edge) | open |
| C9 | Span fact of another scope | open |
| C10 | Dirty-tree span, reviewed tree committed verbatim | the commit's chunk done |
| C11 | Dirty-tree span, tree edited again before commit | open |
| C12 | Span fact with no `base_commit` | open: the interval cannot be placed |
| C13 | #1082 steps 1-7: cumulative names 01, 02; a clean verify-resolutions over chunk 03's uncommitted tree names nothing; committed verbatim as `(Chunk 03)` | all done, 03 citing the verify fact; finished |
| C14 | C13, then `--no-ff` merge and branch deleted | all done; `unbuilt_at_archive` is `None` |
| **K — mode labels do not matter** | | |
| K1 | Named fact in `chunk` / `final` / `cumulative` / `verify-resolutions` | done in each |
| K2 | Unnamed span fact in each of those modes | done in each |
| **P — the proposal at dispatch, then the fact it writes** | | |
| P1 | Mid-plan `final` (#1072) | names only built chunks; unbuilt stay open |
| P2 | Boundary `cumulative`, a chunk built only by subject | names every built chunk; all done |
| P3 | `chunk` review | proposes by its diff; done |
| P4 | Change-record chunk whose fragment is still the `plan new` stub (#1075) | not proposed; open, by proposal and by span |
| P5 | Bare-name Deliverables, `<scope> chunk 01:` subjects (#1081) | proposed; done |
| **B — blocking findings** | | |
| B1 | Named fact with an unresolved blocking finding | open, names the finding |
| B2 | Its blocker resolved by a passing `resolution` fact | done |
| B3 | Blocking count with a finding that has no `fid` | open |
| B4 | Unnamed span with an unresolved blocker | open |
| B5 | Its blocker resolved | done |
| **X — retraction** | | |
| X1 | `chunk-retracted` for (fact, 01) on a fact naming 01, 02 | 01 open with the reason; 02 done |
| X2 | A later fact naming the retracted chunk | done, citing the later fact |
| X3 | A span certification: `plan retract` targets it, and retracting it | `retraction_target` ok; then open with the reason |
| **D / I — declarations and imports** | | |
| D1 | `dropped:` with a reason | dropped; plan finished |
| D2 | `dropped:` entry with no reason | open, says why |
| I1 | Ticked `## Status` box, unmigrated | done, imported |
| I2 | `chunk-imported` fact | done, imported, citing it |
| **S — a Deliverables path several chunks list** | | |
| S1 | Chunk 01's commit touches its own file and a file 01 and 02 both list; unnamed span | 01 done, 02 open |
| S2 | A `(Chunk 02)` scoped commit touching only the shared file | 02 done by subject, 01 open |
| S3 | 01 lists `lib/pkg/`, 02 lists `lib/pkg/b.py`; a commit touches both `a.py` and `b.py` | 01 done by `a.py`, 02 open (the control: a path one chunk owns still certifies) |
| S4 | A `chunk` proposal over only the shared file | proposes neither, and a note says why |
| S5 | The `built` tag over only the shared file | tags both: it certifies nothing |
| **F — git failing on an authority path** | | |
| F1 | The first-parent `rev-list` fails (M2's shape) | open: the anchor is refused |
| F2 | A span's `git log` fails (C2's shape) | open |
| F3 | A dirty-tree span's descendant log fails (C10's shape) | open |
| F4 | A dirty-tree span whose anchor's holding ref is unknown | open |
| **G — what the added git calls cost** | | |
| G1 | Two dirty-tree facts over one interval | one probe and the two interval logs, once |
| G2 | Two facts at one `base_commit` anchor after a `--no-ff` merge | one first-parent `rev-list` |

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
