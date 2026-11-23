---
schema: 1
type: fix
scope: review-chain-merge-base
date: 2026-11-23
title: the review chain stops where this branch's work starts
closes: [brookstalley/prawduct#1224]
---
The review chain (`critic_mode.review_chain`) walked tree links back from the newest review with
nothing to stop it at the branch's merge-base. When an earlier branch's last review stood at the
tree this branch starts from, as it does when that branch merged with the base unmoved, this
branch's first review linked to it and the walk went on into the merged work. That branch's
`cumulative` then sat on this branch's chain. So the boundary check and the interval-extension
deferral said this branch's boundary review had already run, and a chunk-less verify pass could
inherit the merged work's chunks.

The walk now runs over this branch's reviews only. A review is on the chain when it is anchored
on the branch range the newest review is chosen from (`merge_base..HEAD` and the merge base) and
does not stand at the merge-base tree. The tree half is needed because the merge base is in that
range: a fast-forwarded earlier branch leaves its last review anchored there. The lineage half
covers a base merged into the branch, which moves the merge base past this branch's earlier
reviews. Those reviews stay on the chain, while the earlier branch's reviews behind them do not.
The review the walk starts from is always on the chain; the bound only limits how far back the
walk goes.

The tree half is waived when the newest review itself stands at the merge-base tree. That is the
state once this branch's work has landed: on a trunk branch after a push, or on a branch whose
PR merged with a merge commit, the merge base is the branch's tip, and its boundary `cumulative`
and the verify pass after it stand at that tree. Without the waiver they fell off the chain, and
the Stop gate asked for a second `cumulative`. The newest review's tree is what tells the two
cases apart. Whether HEAD has moved past the merge base cannot: a first review of uncommitted
work on a branch just cut from a fast-forwarded base has HEAD still at the merge base, yet
stands at a tree past it. Nor can the branch a review was recorded on, since consecutive work on
one trunk branch records every review under the same name.

Production callers walk the chain through one function, `critic_mode.branch_review_chain`, which
pairs the walk with the bound `critic_mode.chain_bound` resolves: the boundary `cumulative`
check, the extension deferral, the verify proposal and the review close. `review_chain` keeps
the bound as a required argument for tests and for the walk itself.

When no merge base places a bound (no base branch, the moving `HEAD~1` fallback, or a branch range
git cannot list), the walk stays unbounded, as before. The stricter reading, the newest review
alone, would cut every verify pass off from the review it verifies. After a boundary `cumulative`
and its verify pass, the boundary would then read as owed again, and the Stop gate would ask for
a second `cumulative` after every pass. History rewritten under a review (a rebase, or an amend of
the commit it anchors on) leaves that review off the chain even if its tree still links, which
errs toward more review.

Tests build the earlier-branch shape, fast-forwarded and merged with a merge commit, on a real
repository, and ask for this branch's boundary review, before and after this branch commits
anything. They also build this branch's work landing, by a push on trunk and by a merge commit,
and ask that its boundary review still stands. They pin each half of the bound, the waiver and
the two rules it was chosen over, the base-merged-in case, an anchored pass whose anchor is
outside the bound, the unresolvable states, every caller passing the bound, and that no
production code walks the chain except through `branch_review_chain`.

## Consumer note
A branch cut right after another branch merged no longer inherits that branch's `cumulative`.
Its own boundary review is now asked for, and a verify pass no longer names the merged branch's
chunks. A branch's own boundary review still counts after its work lands, by a push on trunk or
a merge commit, so the Stop gate does not ask for a second one.
