---
schema: 1
type: fix
scope: verify-links-review-id
date: 2026-11-23
title: a verify-resolutions fact names the review it verifies
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
inherits no chunk that the walk does not reach. This costs a second `cumulative` when one
worktree's pass anchors to a `chunk` re-review of a tree it had already reviewed as a
`cumulative`; the cost is accepted because it errs toward more review, and lineage cannot be
told after a sync, which trims a fact's `actor`.

The coverage gate does not read the chain. It counts every unresolved blocker recorded at a tree
its composed path stands on, including another review's at the anchor's tree, and none at a tree
a clean spanning review routes the path around. The extension deferral used to ask the chain
whether a blocker was open, so it could say "reviewed with no open blocker … carry on" while the
gate was blocked; it now asks the gate's own count up to the newest review's tree, and does not
defer when that count is unavailable.

When the Stop hook's walk ends at a pass naming a review, shaped like a review id, that the
store does not hold, the NOTE names that review and the pass that recorded it, and gives both
repairs: `prawduct-hook evidence sync` if another clone recorded it, else
`/prawduct:critic final`, since a dropped or unreadable fact never arrives. The walks that loop
over the link stop at a fact they have already visited, since an anchor found by id no longer
follows store order. `review_chain` walks every review it adds, not only the newest each one
links to, so a re-review of an unchanged tree no longer cuts off the predecessors of the review
it repeats. `reviews_linked_from` grows its reached trees to a fixed point, so a pass ingested
ahead of the review whose tree it starts from is still a member. The review id's shape has one
pattern, which the minter's age reader and the link rule share. The schema change is additive:
old facts stay valid, and git notes carry the field unchanged. Tests put two reviews at one tree
with the pass anchored to the older one, and pin each walker, the dangling, mismatched and
malformed cases, each Stop-hook message, the deferral against the gate's count, and the field
written end to end through `critic-begin` and `critic-consolidate`.

`review-cycle.md`'s "never a chunk's first review" line also says not to verify after drift
unrelated to the findings, which `critic-begin` refuses only past the scope-widened threshold.

## Consumer note
Your verify-resolutions passes now record which review they verify. If another worktree of your
clone reviewed the same tree, the Stop hook's "run /prawduct:critic final" NOTE now judges the
review your pass actually verified. If that review is not in your clone's store, the NOTE names
it and gives both repairs: `prawduct-hook evidence sync` if another clone recorded it, else
`/prawduct:critic final`. A fix is no longer told it can ride the next review while the PR
gate still counts an open blocker. Facts recorded before this release behave as before.
