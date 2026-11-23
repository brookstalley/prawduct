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
review rather than the tree's newest. The walks that loop over the link now stop at a fact they
have already visited, since an anchor found by id no longer follows store order. The schema
change is additive: old facts stay valid, and git notes carry the field unchanged. Tests put two
reviews at one tree with the pass anchored to the older one, and pin each walker, the dangling
and malformed cases, and the field written end to end through `critic-begin` and
`critic-consolidate`.

## Consumer note
Your verify-resolutions passes now record which review they verify. If another worktree of your
clone reviewed the same tree, the Stop hook's "run /prawduct:critic final" NOTE now judges the
review your pass actually verified. Facts recorded before this release behave as before.
