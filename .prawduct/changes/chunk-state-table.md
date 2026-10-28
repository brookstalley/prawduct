---
schema: 1
type: fix
scope: chunk-state-table
date: 2026-10-27
title: Chunk state answers a whole case table, and a review certifies the chunks its commit subjects name
closes: [brookstalley/prawduct#1079, brookstalley/prawduct#1082, brookstalley/prawduct#1092]
---

Chunk state derived from review facts was 3.8.0-dev's regression cluster. #1065, #1072, #1075,
#1079, #1081 and #1082 were each a different way a chunk read open, or done, when it should not,
and each fix exposed the next. #1092 asked for the derivation to be checked against every case at
once rather than closing two more instances, and this change does that.

### The case table

- `build-plan-chunk-state-table.md` "Case table" lists every situation `plan_status.chunk_states`
  answers, with its expected state. The groups cover anchor placement, after-merge reachability,
  named vs span coverage, the four review modes, the proposal, blocking findings, retraction,
  Deliverables paths, dropped chunks and imports, git failing, and what the git calls cost.
  `tests/test_chunk_state_table.py` pins each row with a test over real git fixtures.

### #1082: a review's span certifies the chunks its commit subjects name

- A chunk is done when a review fact names it, as before. Under the owner's ruling on #1082, it is
  also done when a clean, in-scope review fact that is a coverage edge has, in its own interval and
  on the branch's first-parent history, a commit whose subject carries the plan's scope and the
  chunk: `<type>(<scope>): … (Chunk N)`. The fact need not name the chunk. #1082's repro (a clean
  verify pass over chunk 03's uncommitted tree, committed verbatim as `(Chunk 03)`) now reads done.
- Touching a Deliverables path gives no span credit. In review, file-based credit certified chunks
  that were not the commit's work three ways: a path two chunks list, commits merged in from the
  base, and a commit labelled for another chunk. Reading only the branch's first-parent commits
  keeps a merge of the base out of the interval.
- A dirty-tree fact's uncommitted part counts once that exact tree is committed. Only a fact the
  coverage gate accepts as an edge may span. Naming answers first, and a span-certified `done` says
  so in its reason line. One rule decides whether a fact may certify, for naming and for a span
  alike, and a refused span records why on the chunks it would have carried.
- The review proposal still names a chunk by a Deliverables path its diff touches, but only a path
  that one chunk alone lists. When a shared path is why it named an open chunk nowhere, it says so.
- `plan retract` can withdraw a span certification while that span certifies the chunk, and a
  re-run with `--fact` answers "already".

### #1079: first-parent reachability

- After the merge deletes the branch, an anchor equal to its review's `base_commit` is refused only
  when it is on the base's first-parent history. One reachable only through a `--no-ff` merge's
  second parent is accepted: that is a dirty-tree review's branch HEAD. So is a review run over
  uncommitted work before the branch's first commit, when the commit carrying its reviewed tree
  reached the base only through the merge. When git cannot answer, the anchor is refused and the
  reason names the git failure.
- The first-parent test has one owner, `plan_status.on_first_parent`. `plan_lifecycle`'s merge
  probe calls it too, so `plan status`'s lifecycle line and `plan check-claims` read #1079's case
  as merged-unreleased. A newer review anchored at its own `base_commit` no longer hides an older
  one that proves a fast-forward from the same commit.

### The record

- `record_lint` reads a bare-path `governed_by:` entry (`- .prawduct/artifacts/x.md`) as an entry
  with no dispositions and grades it, where it used to read nothing and report no gap. An item in
  no form it reads is a `governed-by-gap` too.
- The NEXT-ACTION clause for a whole-plan review that named no chunk says it "named no chunk" and
  speaks only of the chunks still open.
- `planning.md` "Chunk state", `data-model.md` (ruling D1 gains a dated extension note citing the
  owner's ruling), `api-contract.md`, `cross-cutting-concerns.md`, `building.md`, the Critic and PR
  skills, and the docstrings describe both ways a chunk becomes done.

## Consumer note
A chunk now reads done in `prawduct-hook plan status` when a clean review's interval holds one of
your branch's commits whose subject carries the plan's scope and the chunk, `<type>(<scope>): …
(Chunk N)`, even if the review did not name it with `--chunks`. Before, such chunks stayed open,
`plan-backfill` refused the plan at release, and `archive-plan` stamped built work as unbuilt. If
your commit subjects do not name chunks that way, keep passing `--chunks`: touching a chunk's
Deliverables files does not count. A chunk reviewed over uncommitted work also stays done after its
branch is merged with a merge commit and deleted. Two merges still leave chunks open once the branch
is deleted, whether or not a review named them: a squash merge (the reviewed commits are on no
ref), and a fast-forward of a chunk whose only review was over uncommitted work (its anchor cannot
be told from the fork point). Nothing here closes them yet; merge with a merge commit, or keep the
branch until the release.

A `governed_by:` entry written as a bare path now reports a `governed-by-gap` warning when its
artifact has `## Direction` norms, the next time a review changes the plan. Write it as
`- artifact: <name>` with a `dispositions:` line per norm.
