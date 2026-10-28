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
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: chunk state and the lint only read; no reviewer path changes"
      - "authority fails closed; advice fails soft → conforms: an unplaceable anchor, a failed git call, a non-edge fact and a path-only commit each leave the chunk open with its reason (rows F1-F4, M5-M9, C8, C12, C3); the proposal's notes are advice"
      - "local-first: process-spawn, atomic files and git only → conforms: every answer comes from the evidence store and local git; no network, no new dependency"
      - "the plugin writes nothing into a governed repo but its own state → conforms: chunk_states and record_lint write nothing"
      - "written in Python, never specific to Python → conforms: credit reads commit subjects, and the proposal reads paths; neither looks at a file's language"
      - "guides and reviews, never implements → inapplicable because this changes prawduct's own readers, not a product's code"
      - "goals and verification bind; prescribed method is advice → conforms: the build left the plan's inferred whole-branch walk where the code showed it wrong, recorded under Decisions"
      - "every fact has one home → conforms: the chunk-to-commit rule (_subject_chunks, _deliverable_chunks, _log_commits) and the first-parent rule (first_parent_answer) each have one owner; planning.md 'Chunk state' is the rule's prose home and other surfaces point at it"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the evidence store schema-versioned → conforms: no fact shape and no `plan status --json` key changes"
      - "exit codes are the contract; errors attributed, never raised → conforms: no exit code changes; a git failure is named in the open chunk's reason"
      - "additive-first evolution → conforms: `plan retract`'s refusal codes, `plan status` keys and the `governed-by-gap` check name are unchanged; only reason prose and what a span counts move"
  - artifact: data-model
    dispositions:
      - "verdicts come from the append-only fact ledger, no model in a fact's write path → conforms: done is computed from review facts and git; nothing is written"
      - "facts immutable and append-only → conforms: a span certification is withdrawn by a new chunk-retracted fact, never an edit"
      - "derived views never authoritative → conforms; ruling D1 beneath it is extended by the owner's ruling on #1082, which D1's dated note cites"
      - "a governance document reaches a terminal state, never deleted → conforms: the lint stops grading archived plans and deletes nothing"
      - "backlog issue titles conform to the standard → inapplicable because this plan writes no backlog issue"
      - "a fact from a newer schema is a loud block → conforms: no store reader changes how it reads schema"
      - "two stores, two lifetimes → conforms: nothing new is stored"
      - "backlog_service_repo selects the authoritative store → inapplicable because nothing here reads the backlog"
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

**Owner ruling (2026-10-27, on #1082's fork: https://github.com/brookstalley/prawduct/issues/1082#issuecomment-6456663316):** option 1, narrowed. A chunk is done
when a review fact names it, as before. It is also done when a clean, in-scope review fact that is a
coverage edge has, in its own interval and on the branch's first-parent history, a commit whose
subject carries the plan's scope and the chunk: `<type>(<scope>): … (Chunk N)`. Touching a
Deliverables path gives no span credit; a chunk whose commit does not name it in its subject still
needs `--chunks`. Why narrowed: file-based credit certified chunks that were not the commit's work
three ways in review (a path two chunks list, commits merged in from the base, a commit labelled for
another chunk). "The chunk's built commit" is therefore a first-parent commit in the fact's own
interval whose scoped subject names it; an unbuilt chunk has none, so no span certifies it (#1072).

**Out of scope:** #1106 (the briefing's stale-plan predicate; a separate branch calls
`plan_lifecycle.observe` and needs its signature unchanged). The remainder of #1071.

**Level:** High. The case table showed the derivation's authority rule changing the owner's ruling D1, and three review rounds each found a way span credit certified unbuilt work.

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
  citing the owner's ruling on #1082 (Goals) rather than a rewritten statement.
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
- Round 3, the owner's ruling (https://github.com/brookstalley/prawduct/issues/1082#issuecomment-6456663316): a span credits only first-parent commits of its
  interval whose subject carries the plan's scope and the chunk (`_Spans.carried`). Path credit is
  gone from the span, so rows C3, C6 and S1 became negative rows, and C15 (a commit merged in from
  the base) and C16 (a commit labelled for another chunk) were added, both open.
- Round 3, *not settled by the ruling:* the proposal KEEPS its path half, with the one-owner rule.
  It is a name the dispatch prints and the builder keeps or narrows with `--chunks` before the
  fact is written. The ruling kept naming "as before", and the Stop gate's deferral
  (`critic_mode.extension_deferral_owed`) reads `chunk`-mode proposals, which have no subject walk.
  C15's and C16's shapes can still reach a proposal over a tree diff: there the dispatch shows them.
- Round 3: M10 (a dirty-tree review before the branch's first commit, then a `--no-ff` merge) is
  done. The first-parent test separates it from M8 and M5: the commit carrying the reviewed tree,
  on a first-parent chain from the fork point, reached the base only through the merge's second
  parent (`_Reachability._merged_verbatim`). Where several commits carry that tree, a non-merge one
  is preferred as the branch's commit. `plan_lifecycle`'s merge probe does not take this route; it
  still has the pending-change-record inference for this shape.
- Round 3: one closure, `cannot_certify`, answers "may this fact certify" for both the naming and
  the span loop; a refused span records its reason on the chunks its interval would have carried.
  A first-parent `rev-list` that fails is named in the reason (`first_parent_answer`).
- Round 3, `record_lint`: a bare-path `governed_by:` entry is a supported form, parsed as an entry
  with no dispositions and graded like any other; an item no form reads is a `governed-by-gap`.
  Supported rather than flagged as a form, because a bare path to an artifact with no `## Direction`
  norms is then quiet, where flagging the form would warn on it too. An archived plan is no record
  (`record_lint.is_record`), so the release's archive moves raise nothing; a live plan with bare
  paths reports its real gaps when a review next changes it.
- Round 3 against this repo's 173 plans, vs 369e6f79: one chunk moved,
  `archive/build-plan-coverage-honesty.md` 04, done to open. It was superseded by PR #734 and read
  done only because the review's interval touched its Deliverables.

## Case table

Every situation `plan_status.chunk_states` answers, with the state it must answer. Each row is one
test in `tests/test_chunk_state_table.py`, named `test_<row id>_…`. "Named" is a review fact whose
`chunks` (else `chunk`) lists the chunk; "span" is a clean, in-scope review fact that is an edge in
the coverage algebra's sense (`coverage_algebra.review_edges`: both trees recorded, every judgeable
changed file reviewed) whose interval, read along the branch's first parents, holds a commit whose
subject carries the plan's scope and the chunk. A Deliverables path is no span credit (owner ruling
above). A commit is in a fact's interval when it is on the first-parent chain of
`base_commit..head_commit`, or, for a dirty-tree fact (`head_commit: null`), of
`base_commit..dispatch_commit`, or on the first-parent chain from `dispatch_commit` to the first
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
| M10 | A dirty-tree review before the branch's first commit (anchor = fork point = `base_commit`), committed verbatim, `--no-ff` merge, branch deleted; base moved on or not | done, named and by span: the commit carrying the reviewed tree reached the base only through the merge's second parent |
| **C — named vs span coverage** | | |
| C1 | Fact names chunk 01; its span ends before chunk 02's commit | 01 done, 02 open |
| C2 | Unnamed span carries chunks 01 and 02 by scoped subject | both done, citing that fact |
| C3 | Unnamed span touches chunk 02's Deliverables under a subject naming no chunk | open: a path is no span credit |
| C4 | Fact names 01; its span also carries 02's commit | both done |
| C5 | Unnamed `final` span carrying only chunk 01's commit (#1072's invariant) | 01 done, 02 and 03 open |
| C6 | A `(Chunk 01)` commit before the span starts; in it, a commit touching 01's file with no chunk subject | all open |
| C7 | Chunk carried only by an unscoped subject (`feat(other): … (Chunk 02)`) | open |
| C8 | Span fact that reviewed less than it changed (no edge) | open |
| C9 | Span fact of another scope | open |
| C10 | Dirty-tree span, reviewed tree committed verbatim | the commit's chunk done |
| C11 | Dirty-tree span, tree edited again before commit | open |
| C12 | Span fact with no `base_commit` | open: the interval cannot be placed |
| C13 | #1082 steps 1-7: cumulative names 01, 02; a clean verify-resolutions over chunk 03's uncommitted tree names nothing; committed verbatim as `(Chunk 03)` | all done, 03 citing the verify fact; finished |
| C14 | C13, then `--no-ff` merge and branch deleted | all done; `unbuilt_at_archive` is `None` |
| C15 | A `(Chunk 02)` commit on the base, touching 02's file, merged into the branch inside the interval | 02 open: off the branch's first-parent history; 01 done |
| C16 | A `(Chunk 02)` commit touching chunk 03's file | 02 done, 03 open |
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
| X3 | A span certification: `plan retract` targets it, retracting it, then `--fact` again | `retraction_target` ok; then open with the reason; then `already` |
| **D / I — declarations and imports** | | |
| D1 | `dropped:` with a reason | dropped; plan finished |
| D2 | `dropped:` entry with no reason | open, says why |
| I1 | Ticked `## Status` box, unmigrated | done, imported |
| I2 | `chunk-imported` fact | done, imported, citing it |
| **S — Deliverables paths** | | |
| S1 | An unnamed span touching chunk 01's own file and a file 01 and 02 both list, no chunk subject | both open |
| S2 | A `(Chunk 02)` scoped commit touching only the shared file | 02 done by subject, 01 open |
| S3 | The proposal: 01 lists `lib/pkg/`, 02 lists `lib/pkg/b.py` | a diff of `a.py` proposes 01; of `b.py`, neither |
| S4 | A `chunk` proposal over only the shared file | proposes neither, and a note says why |
| S5 | The `built` tag over only the shared file | tags both: it certifies nothing |
| **F — git failing on an authority path** | | |
| F1 | The first-parent `rev-list` fails (M2's shape) | open: the anchor is refused, and the reason names the git failure |
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
