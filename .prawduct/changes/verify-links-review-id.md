---
schema: 1
type: fix
scope: verify-links-review-id
date: 2026-11-23
title: a verify-resolutions fact names the review it verifies
closes: [brookstalley/prawduct#1220]
---
A `verify-resolutions` pass was linked to the review it verified only by tree: the newest review
anywhere in the clone-wide store whose `head_tree` was the pass's `base_tree`. When two worktrees
of one clone reviewed the same tree, that could be the wrong review. The Stop hook's synthesis
NOTE then fired when no `final` was owed, or stayed quiet when one was. A roll-call without the
gate's composition could also carry the other review's blockers.

Consolidation now records `verifies: <review id>` on the pass's fact: the review the dispatch
anchored to, from the findings cache's pointer or this branch's newest review.
`coverage_algebra.prior_review` is the one owner of "which review does this pass verify". It
follows `verifies` when present and falls back to the tree link for a fact written before the
field. The Stop hook's walk (`gates._critic_session_satisfies_gate`), the review chain
(`critic_mode.review_chain`), the extended line (`plan_status._extended_reviews`) and
`critic_consolidate.carried_blocking` all go through it. A `verifies` naming a review the store
does not hold, for example one not yet ingested from the clone that recorded it, links to no
review rather than the tree's newest. The same goes for a named review whose `head_tree` is not
the pass's `base_tree`, for a value not shaped like a review id, and for a pass with no usable
`base_tree`, anchored or not. A pass that names its review links to that review alone: another
review of the same tree, from either worktree and in any store order, is on the pass's chain
only if the walk from the named review reaches it. So the chain credits no boundary review and
inherits no chunk that the walk does not reach. In one worktree this costs review in both
directions: a pass anchored to a `chunk` re-review of a tree already reviewed as a `cumulative`
asks for a second `cumulative`, and a pass anchored to a boundary `cumulative` of a tree already
reviewed as a `chunk` names and certifies none of that chunk review's chunks; both costs are
accepted because they err toward more review, and lineage cannot be told after a sync, which
trims a fact's `actor`.

The coverage gate does not read the chain. It counts every unresolved blocker recorded at a tree
its composed path stands on, including another review's at the anchor's tree, and none at a tree
a clean spanning review routes the path around. The extension deferral used to ask the chain
whether a blocker was open, so it could say "reviewed with no open blocker … carry on" while the
gate was blocked; it now asks the gate's own count up to the newest review's tree, and falls
back to the chain's own blockers only when the gate cannot compose (an uncovered path is no
answer about blockers).

When the Stop hook's walk ends at a pass naming a review, shaped like a review id, that the
store does not hold, the NOTE names that review (and the pass that recorded it, when that pass is
not the latest review), and gives both
repairs: `prawduct-hook evidence sync` if another clone recorded it, else
`/prawduct:critic final`, since a dropped or unreadable fact never arrives. An anchor found by id
no longer follows store order, so store order no longer ends a walk over the link:
`coverage_algebra.walk_links` steps every walker back along it and ends the walk at a fact it
has already visited, keyed by fact id. The three walkers go through it, so the guard lives in
one place rather than in each walker's loop. A malformed `verifies` value (not shaped like a review id) is
unresolved but never "not yet ingested"; the dispatch-age reader keeps reading only the id's `rev-<stamp>-`
prefix. The schema change is additive: old facts stay valid, and git notes carry the field
unchanged. Tests put two reviews at one tree with the pass anchored to the older one, and pin each
walker, the dangling, mismatched and malformed cases, each Stop-hook message, the deferral against
the gate's count (and its chain fallback when the gate cannot compose), the field written end to
end through `critic-begin` and `critic-consolidate`, and the walkers on `walk_links` reaching
exactly what their own loops reached, on stores read back through the store reader.

`review-cycle.md`'s "never a chunk's first review" line also says not to verify after drift
unrelated to the findings, which `critic-begin` refuses only past the scope-widened threshold.

## Consumer note
Your verify-resolutions passes now record which review they verify. If another worktree of your
clone reviewed the same tree, the Stop hook's "run /prawduct:critic final" NOTE now judges the
review your pass actually verified. If that review is not in your clone's store, the NOTE names
it and gives both repairs: `prawduct-hook evidence sync` if another clone recorded it, else
`/prawduct:critic final`. A fix is no longer told it can ride the next review while the PR
gate still counts an open blocker. Facts recorded before this release behave as before.
