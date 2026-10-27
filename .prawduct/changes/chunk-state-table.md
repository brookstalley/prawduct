---
schema: 1
type: fix
scope: chunk-state-table
date: 2026-10-27
title: Chunk state answers a whole case table, and a review's span certifies the chunks it built
closes: [brookstalley/prawduct#1079, brookstalley/prawduct#1082, brookstalley/prawduct#1092]
---

Chunk state derived from review facts was 3.8.0-dev's regression cluster. #1065, #1072, #1075,
#1079, #1081 and #1082 were each a different way a chunk read open, or done, when it should not,
and each fix exposed the next. #1092 asked for the derivation to be checked against every case at
once rather than closing two more instances, and this change does that.

### Chunk 01: the case table

- `build-plan-chunk-state-table.md` "Case table" lists every situation `plan_status.chunk_states`
  answers, with its expected state. The groups cover anchor placement, after-merge reachability,
  named vs span coverage, the four review modes, proposal, blocking, retraction, dropped chunks and
  imports. `tests/test_chunk_state_table.py` pins each row with a test over real git fixtures.
- The rows that failed before Chunk 02 were exactly #1079's and #1082's, plus the controls that
  share their fixtures.

### Chunk 02: plan_status passes it

- **#1082, span-derived done.** A chunk is now also done when a clean, in-scope review fact that is
  a coverage edge has a commit in its own interval that builds the chunk, whether or not the fact
  names it. A commit builds a chunk when its subject carries the chunk and the plan's scope, or
  when it touches a path only that chunk's Deliverables list (the `plan new` stub excluded). A
  path two chunks list builds neither by path alone, so a neighbour's commit never certifies an
  unbuilt chunk; the review proposal applies the same rule and says when a shared path is why it
  named nothing. A dirty-tree fact's uncommitted part counts once that exact tree is committed.
  Only a fact the coverage gate accepts as an edge may span. Naming still answers first; a span-certified `done` says so in its reason line.
- **#1079, first-parent reachability.** After the merge deletes the branch, an anchor equal to its
  review's `base_commit` is refused only when it is on the base's first-parent history (the fork
  point the base already held). One reachable only through a `--no-ff` merge's second parent is
  accepted: that is a dirty-tree review's branch HEAD. A fast-forward merge of such an anchor and a
  squash merge still read open, failing closed.
- `plan retract` can withdraw a span certification while that span certifies the chunk.
- `planning.md` "Chunk state", `data-model.md` (ruling D1 gains a dated extension note),
  `api-contract.md`, `cross-cutting-concerns.md`, `building.md`, the Critic skill and the docstrings
  describe both ways a chunk becomes done.

### Chunk 03: one owner, and the change record

- The first-parent test is one function, `plan_status.on_first_parent`. Chunk state and
  `plan_lifecycle`'s merge probe both call it, so `plan status`'s lifecycle line and `plan
  check-claims` also read #1079's case as merged-unreleased. Before, the
  lifecycle dropped every anchor equal to its `base_commit`.
- The review's NEXT-ACTION clause for a whole-plan review that named no chunk now says it "named no
  chunk" and speaks only of the chunks still open. "Certified no chunk" was false once a span could
  certify one.

## Consumer note
A chunk now reads done in `prawduct-hook plan status` when a clean review covered a commit that
builds it, even if the review did not name it with `--chunks`. Before, such chunks stayed open, and
`plan-backfill` refused the plan at release or `archive-plan` stamped built work as unbuilt. A chunk
reviewed over uncommitted work also stays done after its branch is merged with a merge commit and
deleted. Two merges still leave chunks open once the branch is deleted, whether or not a review
named them: a squash merge (the reviewed commits are on no ref), and a fast-forward of a chunk
whose only review was over uncommitted work (its anchor cannot be told from the fork point). Nothing here closes
them yet; merge with a merge commit, or keep the branch until the release.
